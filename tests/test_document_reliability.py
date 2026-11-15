"""No paid calls: exercise the real index and deterministic omission recovery."""
import json
from pathlib import Path

import pytest

from backend import claude_service as service, operations
from backend.document_store import ingest
from backend.retrieval_models import LocalModels
from backend.retrieval_service import Retriever
from test_grounded_chat import calls, evidence, grounded, text


QUESTION = 'According to the project-specific release procedure, who receives the packet and when? Cite your source.'


@pytest.fixture
def release_index(tmp_path, local_models):
    database = tmp_path / 'index.sqlite3'
    ingest(Path('sample_docs'), database, local_models)
    return database


def test_cold_warm_and_project_switching(release_index):
    models = LocalModels()
    assert models.encoder is None and models.reranker is None
    retriever = Retriever(release_index, models)
    first = retriever.search(QUESTION, 303)
    for project_id in (303, 101, 202, 303, 202):
        result = retriever.search(QUESTION, project_id)
        if project_id == 101:
            assert result['status'] == 'insufficient_evidence'
            assert result['evidence'] == []
            continue
        assert result['status'] == 'ok'
        assert all(s['project_id'] in (None, project_id) for s in result['candidates'])
        if project_id in (202, 303):
            owner = 'Elena Vale' if project_id == 202 else 'Owen Reed'
            assert any(owner in s['excerpt'] for s in result['evidence'])
        if project_id == 303:
            assert result['evidence'] == first['evidence']


def test_first_and_repeated_request_without_search_tool(api, provider, monkeypatch, release_index, local_models):
    retriever = Retriever(release_index, local_models)
    monkeypatch.setattr(service, 'get_retriever', lambda: retriever)
    for project_id in (303, 303, 101, 202, 303):
        question = QUESTION if project_id != 101 else 'According to the sample procedure, who receives the Cedar escalation packet?'
        source = retriever.search(question, project_id)['evidence'][0]
        provider.messages.create.side_effect = [text(service.INSUFFICIENT), grounded(source)]
        result = api.post('/ai/chat', json={'message':question, 'project_id':project_id})
        assert result.status_code == 200
        assert source['chunk_id'] in result.json()['answer']
        assert source['excerpt'] in result.json()['answer']
        assert provider.messages.create.call_args.kwargs['messages'][-1]['content'][0]['type'] == 'tool_result'
    assert operations.store().cache_size() == 0


def test_model_query_rewrite_cannot_discard_answerable_evidence(api, provider, monkeypatch, release_index, local_models):
    retriever = Retriever(release_index, local_models)
    monkeypatch.setattr(service, 'get_retriever', lambda: retriever)
    source = retriever.search(QUESTION, 303)['evidence'][0]
    # Valid tool arguments, but a lossy model rewrite that has no relevant evidence.
    assert retriever.search('release packet recipient timeline', 303)['evidence'] == []
    provider.messages.create.side_effect = [calls(('search_documents',
        {'project_id':303, 'query':'release packet recipient timeline'})), grounded(source)]
    answer = api.post('/ai/chat', json={'message':QUESTION, 'project_id':303}).json()['answer']
    assert source['chunk_id'] in answer and 'Owen Reed' in answer and 'six working hours' in answer
    assert provider.messages.create.call_count == 2


@pytest.mark.parametrize('bad', ['id', 'quote', 'prose'])
def test_omission_recovery_still_rejects_invalid_citations(api, provider, evidence, bad):
    invalid = grounded(evidence, source_id='INVENTED') if bad == 'id' else grounded(evidence, quote='Invented quotation')
    if bad == 'prose':
        invalid = text('Unsupported procedure')
    provider.messages.create.side_effect = [text(service.INSUFFICIENT), invalid]
    result = api.post('/ai/chat', json={'message':QUESTION, 'project_id':303})
    assert result.json() == {'answer':service.INSUFFICIENT}
    assert provider.messages.create.call_count == 2
    event = operations.store().events()[-1]
    assert event['document_search'] == 'recovered_omission'
    assert event['document_failure'] == 'citation_validation_rejected'


@pytest.mark.parametrize('failure', ['missing', 'initialization', 'scope', 'tool_error'])
def test_omission_failure_is_distinguished_without_paid_retry(api, provider, monkeypatch, evidence, failure):
    from backend.document_store import RetrievalError
    def search(*args):
        if failure == 'initialization':
            raise RetrievalError('private model path')
        if failure == 'scope':
            return {'status':'ok', 'evidence':[{**evidence, 'project_id':202}]}
        if failure == 'tool_error':
            return {'error':'private tool details'}
        return {'status':'insufficient_evidence', 'reason':'no_relevant_sources', 'evidence':[]}
    monkeypatch.setattr(service, 'search_documents', search)
    provider.messages.create.side_effect = [text(service.INSUFFICIENT)]
    result = api.post('/ai/chat', json={'message':QUESTION, 'project_id':303})
    assert result.json() == {'answer':service.INSUFFICIENT}
    assert provider.messages.create.call_count == 1
    event = operations.store().events()[-1]
    expected = {'missing':'no_relevant_sources', 'initialization':'retrieval_unavailable',
                'scope':'evidence_scope_mismatch', 'tool_error':'tool_execution_error'}[failure]
    assert event['document_failure'] == expected
    assert 'private' not in json.dumps(event)
    assert operations.store().cache_size() == 0


def test_mixed_structured_result_survives_search_omission(api, provider, evidence):
    provider.messages.create.side_effect = [calls(('get_critical_rfis', {'project_id':101})),
        text(service.INSUFFICIENT), grounded(evidence)]
    answer = api.post('/ai/chat', json={'message':'Critical RFIs according to the sample procedure', 'project_id':101}).json()['answer']
    assert evidence['chunk_id'] in answer
    assert provider.messages.create.call_count == 3
    messages = provider.messages.create.call_args.kwargs['messages']
    assert any('Electrical routing conflict' in json.dumps(m['content']) for m in messages if m['role'] == 'user')


def test_actual_missing_release_document_does_not_retry(api, provider, monkeypatch, release_index, local_models):
    monkeypatch.setattr(service, 'get_retriever', lambda: Retriever(release_index, local_models))
    provider.messages.create.side_effect = [text(service.INSUFFICIENT)]
    result = api.post('/ai/chat', json={'message':QUESTION, 'project_id':101})
    assert result.json() == {'answer':service.INSUFFICIENT}
    assert provider.messages.create.call_count == 1
    assert operations.store().events()[-1]['document_failure'] == 'no_relevant_sources'


@pytest.mark.parametrize('project_id', [202, 303])
def test_real_retrieval_with_combined_rfi_question(api, provider, monkeypatch, release_index, local_models, project_id):
    retriever = Retriever(release_index, local_models)
    monkeypatch.setattr(service, 'get_retriever', lambda: retriever)
    question = QUESTION + ' Also list critical RFIs.'
    source = retriever.search(question, project_id)['evidence'][0]
    provider.messages.create.side_effect = [calls(
        ('get_critical_rfis', {'project_id':project_id}),
        ('search_documents', {'project_id':project_id, 'query':'release packet recipient timeline'})), grounded(source)]
    result = api.post('/ai/chat', json={'message':question, 'project_id':project_id})
    assert source['chunk_id'] in result.json()['answer']
    results = provider.messages.create.call_args.kwargs['messages'][-1]['content']
    assert json.loads(results[0]['content'])['critical_rfis']
    assert json.loads(results[1]['content'])['evidence'][0]['project_id'] == project_id


@pytest.mark.parametrize('failure', ['truncated', 'malformed'])
def test_bad_recovery_response_is_provider_error(api, provider, evidence, failure):
    response = text('{"answer":"private incomplete response",')
    if failure == 'truncated':
        response.stop_reason = 'max_tokens'
    provider.messages.create.side_effect = [text(service.INSUFFICIENT), response]
    result = api.post('/ai/chat', json={'message':QUESTION, 'project_id':303})
    assert result.status_code == 502
    assert 'private' not in result.text
    assert provider.messages.create.call_count == 2
    assert operations.store().events()[-1]['outcome'] == 'provider_response_error'

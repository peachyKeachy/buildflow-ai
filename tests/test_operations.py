import pytest


@pytest.mark.parametrize('question,route', [
    ('How many RFIs are open?', 'total'), ('Which RFIs are critical?', 'critical'),
    ('How many RFIs are blocking?', 'blocking'), ('Give me the project RFI counts.', 'counts'),
    (' WHICH   RFIs are CRITICAL for project 101? ', 'critical'),
    ('Which RFIs are critical and what escalation procedure applies?', None),
    ('How many RFIs are open? Also list submittals.', None),
    ('According to the sample procedure, which RFIs are critical?', None),
    ('Why are these RFIs critical?', None), ('How do I cook a steak?', None),
])
def test_conservative_router(question, route):
    from backend.operations import deterministic_route
    assert deterministic_route(question) == route


def test_router_uses_business_rules():
    from backend.operations import deterministic_answer
    from backend.project_service import get_project_by_id
    answer = deterministic_answer('critical', get_project_by_id(101))
    assert 'Electrical routing conflict' in answer and 'Mechanical duct conflict' in answer
    assert '12' in answer and '8' in answer
    assert 'Door hardware clarification' not in answer


def test_cache_normalization_expiration_and_versions(tmp_path):
    from backend.operations import Store, cache_identity
    project = {'id':101, 'rfis':[]}
    store = Store(tmp_path / 'ops.sqlite3')
    key = cache_identity('Which RFIs are critical?', 101, 'critical', project)
    assert key == cache_identity(' WHICH  RFIs are CRITICAL? ', 101, 'critical', project)
    assert key != cache_identity('Which RFIs are critical?', 202, 'critical', project)
    assert key != cache_identity('Which RFIs are critical?', 101, 'critical', {'id':101,'rfis':[{'id':1}]})
    store.put(key, 'verified answer', ttl=10, maximum=2, now=100)
    assert store.get(key, now=105) == 'verified answer'
    assert store.get(key, now=111) is None
    for i in range(5):
        store.put(str(i), 'answer', ttl=10, maximum=2, now=200+i)
    assert store.cache_size() == 2


def test_parallel_cache_access(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from backend.operations import Store
    store = Store(tmp_path / 'ops.sqlite3')
    def use(i):
        store.put(str(i), 'answer', ttl=60, maximum=5)
        store.get(str(i))
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(use, range(24)))
    assert store.cache_size() == 5


def test_actual_usage_cost_categories(monkeypatch):
    import json
    from types import SimpleNamespace as NS
    from backend.operations import usage_record
    prices = {'test-model':{'input':3, 'output':15, 'cache_read':.3, 'cache_write_5m':3.75,'cache_write_1h':6}}
    monkeypatch.setenv('BUILDFLOW_MODEL_PRICING_JSON', json.dumps(prices))
    usage = NS(input_tokens=1000,output_tokens=200,cache_read_input_tokens=300,
        cache_creation_input_tokens=120,cache_creation=NS(ephemeral_5m_input_tokens=100,ephemeral_1h_input_tokens=20))
    record = usage_record('test-model', usage, 20)
    assert record['estimated_usd'] == pytest.approx(.003+.003+.00009+.000375+.00012)
    assert record['input_tokens'] == 1000 and record['latency_ms'] == 20
    assert usage_record('unknown-model', usage, 20)['estimated_usd'] is None
    assert usage_record('test-model', None, 20)['estimated_usd'] is None


def test_api_deterministic_cache_and_data_update(api, provider):
    from backend import operations, project_service
    for question in ('Which RFIs are critical?', ' WHICH   RFIs are CRITICAL? '):
        answer = api.post('/ai/chat', json={'message':question,'project_id':101}).json()['answer']
        assert 'Electrical routing conflict' in answer
    events = operations.store().events()
    assert [e['cache'] for e in events] == ['miss','hit']
    assert all(e['claude_calls'] == 0 for e in events)
    provider.messages.create.assert_not_called()
    project_service.projects[0]['rfis'][0]['is_blocking'] = False
    answer = api.post('/ai/chat', json={'message':'Which RFIs are critical?','project_id':101}).json()['answer']
    assert 'Electrical routing conflict' not in answer
    assert operations.store().events()[-1]['cache'] == 'miss'


def test_project_context_and_scope_before_cache(api, provider):
    for payload in ({'message':'Which RFIs are critical for project 202?', 'project_id':101},
                    {'message':'How do I cook a steak?', 'project_id':101},
                    {'message':'Which RFIs are critical?'},
                    {'message':'Which RFIs are critical?', 'project_id':999}):
        api.post('/ai/chat', json=payload)
    provider.messages.create.assert_not_called()
    from backend.operations import store
    assert store().cache_size() == 0


def test_metrics_never_contain_prompt_or_response(api, provider):
    from types import SimpleNamespace as NS
    from backend.operations import store
    provider.messages.create.side_effect = None
    provider.messages.create.return_value = NS(stop_reason='end_turn', content=[NS(type='text', text='private-response-xyz')],
        usage=NS(input_tokens=123,output_tokens=12,cache_read_input_tokens=0,cache_creation_input_tokens=0))
    api.post('/ai/chat', json={'message':'Explain construction private-prompt-xyz', 'project_id':101})
    events = store().events()
    assert events[-1]['claude_calls'] == 1
    assert events[-1]['calls'][0]['input_tokens'] == 123
    assert 'private-prompt-xyz' not in str(events) and 'private-response-xyz' not in str(events)


def test_api_project_isolation(api, provider):
    from backend import project_service, operations
    project_service.projects.append({'id':202,'name':'Synthetic second project','status':'active','rfis':[]})
    first = api.post('/ai/chat', json={'message':'How many RFIs are blocking?', 'project_id':101}).json()['answer']
    second = api.post('/ai/chat', json={'message':'How many RFIs are blocking?', 'project_id':202}).json()['answer']
    assert '2 blocking' in first and '0 blocking' in second
    assert [e['cache'] for e in operations.store().events()] == ['miss','miss']
    provider.messages.create.assert_not_called()


def test_expired_api_answer(api, monkeypatch):
    from backend import operations
    monkeypatch.setenv('BUILDFLOW_ANSWER_TTL_SECONDS', '1')
    monkeypatch.setattr(operations.time, 'time', lambda:100)
    api.post('/ai/chat', json={'message':'How many RFIs are open?','project_id':101})
    monkeypatch.setattr(operations.time, 'time', lambda:102)
    api.post('/ai/chat', json={'message':'How many RFIs are open?','project_id':101})
    assert [e['cache'] for e in operations.store().events()] == ['miss','miss']


def test_bad_model_response_not_cached(api, provider):
    from types import SimpleNamespace as NS
    from backend import operations
    provider.messages.create.side_effect = None
    provider.messages.create.return_value = NS(stop_reason='end_turn', content=[NS(type='text',text='{"answer":"private-malformed-detail",')])
    for _ in range(2):
        response = api.post('/ai/chat', json={'message':'Explain the coordination context for project 101'})
        assert response.status_code == 502 and 'private-malformed' not in response.text
    assert provider.messages.create.call_count == 2
    assert operations.store().cache_size() == 0
    assert all(e['outcome'] == 'provider_response_error' for e in operations.store().events())


def test_document_revisions_bypass_answer_cache(api, provider, local_models, tmp_path, monkeypatch):
    import shutil
    from pathlib import Path
    from backend import operations, claude_service
    from backend.document_store import ingest
    from backend.retrieval_service import Retriever
    from test_grounded_chat import calls, grounded
    folder = tmp_path / 'docs'
    shutil.copytree(Path('sample_docs'), folder)
    database = tmp_path / 'retrieval.sqlite3'
    ingest(folder, database, local_models)
    retriever = Retriever(database, local_models)
    monkeypatch.setattr(claude_service, 'get_retriever', lambda:retriever)
    revisions = []
    for update in (False, True):
        if update:
            path = folder / '01_rfi_escalation_r2.md'
            path.write_text(path.read_text(encoding='utf-8').replace('Revision: 2','Revision: 3').replace('Mira Chen','Lena Test'), encoding='utf-8')
            ingest(folder, database, local_models, rebuild=True)
        source = retriever.search('Who receives the Cedar escalation packet?',101)['evidence'][0]
        revisions.append(source['revision'])
        provider.messages.create.side_effect = [calls(('search_documents',{'project_id':101,'query':'Who receives the Cedar escalation packet?'})),grounded(source)]
        response = api.post('/ai/chat',json={'message':'According to the sample procedure, who receives the Cedar escalation packet?','project_id':101})
        assert source['chunk_id'] in response.json()['answer']
        assert source['excerpt'] in response.json()['answer']
    assert revisions == [2,3]
    assert provider.messages.create.call_count == 4
    assert operations.store().cache_size() == 0
    assert all(e['cache'] == 'bypass' for e in operations.store().events())
    assert all(e['retrieval_ms'] > 0 and e['rerank_ms'] > 0 for e in operations.store().events())


def test_invalid_citations_and_mixed_questions_never_cached(api, provider, monkeypatch):
    from backend import claude_service, operations
    from test_grounded_chat import calls, grounded
    source = {'chunk_id':'REAL','project_id':None,'sample_data':True,'excerpt':'Fictional sample supporting passage.'}
    monkeypatch.setattr(claude_service, 'search_documents', lambda *args:{'status':'ok','evidence':[source]})
    for _ in range(2):
        provider.messages.create.side_effect = [calls(('get_critical_rfis',{'project_id':101}),
            ('search_documents',{'project_id':101,'query':'escalation procedure'})), grounded(source, source_id='INVENTED')]
        answer = api.post('/ai/chat',json={'message':'Which RFIs are critical and what escalation procedure applies?','project_id':101}).json()['answer']
        assert 'Electrical routing conflict' in answer and 'insufficient' in answer.lower()
        assert 'INVENTED' not in answer
    assert provider.messages.create.call_count == 4
    assert operations.store().cache_size() == 0
    assert all(e['tool_calls'] == 2 and e['outcome'] == 'partial' for e in operations.store().events())


def test_report_and_explicitly_mocked_benchmark():
    from scripts.operations_report import demo
    report = demo()
    assert 'MOCKED' in report['label']
    assert report['before']['claude_calls'] == 20
    assert report['after']['claude_calls'] == 0 and report['after']['answer_cache_hits'] == 9
    assert report['before']['estimated_api_spend_usd'] == pytest.approx(.09)


def test_model_prompt_version_changes_do_not_affect_deterministic_key(monkeypatch):
    from backend import operations
    question, project = 'Which RFIs are critical?', {'id':101,'rfis':[]}
    before = operations.cache_identity(question,101,'critical',project)
    monkeypatch.setenv('BUILDFLOW_MAX_OUTPUT_TOKENS','2400')
    assert operations.cache_identity(question,101,'critical',project) == before
    monkeypatch.setattr(operations,'VERSION','deterministic-v2-validation-v2')
    assert operations.cache_identity(question,101,'critical',project) != before

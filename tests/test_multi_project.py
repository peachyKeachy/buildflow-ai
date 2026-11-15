import pytest


@pytest.mark.parametrize('project_id,name,total,blocking,critical,ids', [
    (101,'Naples Medical Center',3,2,2,[1,3]),
    (202,'Gulfshore Residential Tower',6,3,2,[1,2]),
    (303,'Southwest Logistics Center',5,2,1,[1]),
])
def test_project_endpoints_and_chat(api, provider, project_id, name, total, blocking, critical, ids):
    project = api.get(f'/projects/{project_id}').json()
    assert project['name'] == name and project['status'] == 'active'
    rfis = api.get(f'/projects/{project_id}/rfis').json()
    assert len(rfis) == total and rfis == project['rfis']
    assert api.get(f'/projects/{project_id}/summary').json() == {
        'project_name':name,'total_rfis':total,'blocking_rfis':blocking,'critical_rfis':critical}
    assert [r['id'] for r in api.get(f'/projects/{project_id}/rfis/critical').json()] == ids
    assert len(api.get(f'/projects/{project_id}/rfis/filter?blocking=true').json()) == blocking
    assert api.get(f'/projects/{project_id}/rfis/filter').json() == rfis
    answer = api.post('/ai/chat',json={'message':'Give me the project RFI counts.','project_id':project_id}).json()['answer']
    assert name in answer and f'{total} total RFIs' in answer and f'{critical} critical' in answer
    provider.messages.create.assert_not_called()


def test_original_101_unchanged(api):
    assert api.get('/projects/101').json() == {'id':101,'name':'Naples Medical Center','status':'active','rfis':[
        {'id':1,'title':'Electrical routing conflict','days_open':12,'is_blocking':True},
        {'id':2,'title':'Door hardware clarification','days_open':3,'is_blocking':False},
        {'id':3,'title':'Mechanical duct conflict','days_open':8,'is_blocking':True}]}


def test_all_projects_and_isolated_cache(api):
    from backend.operations import store
    assert [p['id'] for p in api.get('/projects').json()] == [101,202,303]
    answers = []
    for project_id in (101,202,303,101,202,303):
        answers.append(api.post('/ai/chat',json={'message':'Which RFIs are critical?','project_id':project_id}).json()['answer'])
    assert len(set(answers)) == 3
    assert answers[:3] == answers[3:]
    assert [e['cache'] for e in store().events()] == ['miss']*3+['hit']*3


@pytest.mark.parametrize('project_id,doc_id,owner', [(202,'BF-COORD-202','Elena Vale'),(303,'BF-COORD-303','Owen Reed')])
def test_project_evidence_and_citations(api, provider, local_models, tmp_path, monkeypatch, project_id, doc_id, owner):
    from pathlib import Path
    from backend import claude_service
    from backend.document_store import ingest
    from backend.retrieval_service import Retriever
    from test_grounded_chat import calls, grounded
    database = tmp_path / 'index.sqlite3'
    ingest(Path('sample_docs'),database,local_models)
    retriever = Retriever(database,local_models)
    question = 'According to the project-specific release procedure, who receives the packet and when?'
    result = retriever.search(question,project_id)
    assert result['status'] == 'ok'
    assert all(c['project_id'] in (None,project_id) for c in result['candidates'])
    source = next(c for c in result['evidence'] if c['document_id'] == doc_id)
    assert owner in source['excerpt'] and source['sample_data'] and source['revision'] == 1
    monkeypatch.setattr(claude_service,'get_retriever',lambda:retriever)
    provider.messages.create.side_effect = [calls(('search_documents',{'project_id':project_id,'query':question})),grounded(source)]
    answer = api.post('/ai/chat',json={'message':question,'project_id':project_id}).json()['answer']
    assert source['chunk_id'] in answer and source['excerpt'] in answer and 'Synthetic' in answer


@pytest.mark.parametrize('project_id,total', [(202,6),(303,5)])
def test_new_project_create_route_is_isolated(api, project_id, total):
    payload = {'title':'Synthetic test coordination question','days_open':0,'is_blocking':False}
    response = api.post(f'/projects/{project_id}/rfis',json=payload)
    assert response.json() == {'id':total+1, **payload}
    assert api.get(f'/projects/{project_id}/summary').json()['total_rfis'] == total+1
    assert api.get('/projects/101/summary').json()['total_rfis'] == 3


def test_three_way_retrieval_isolation(local_models, tmp_path):
    from pathlib import Path
    from backend.document_store import ingest
    from backend.retrieval_service import Retriever
    database = tmp_path / 'index.sqlite3'
    ingest(Path('sample_docs'),database,local_models)
    retriever = Retriever(database,local_models)
    for project_id in (101,202,303):
        result = retriever.search('Project coordination hold release procedure',project_id)
        assert result['candidates']
        assert all(c['project_id'] in (None,project_id) for c in result['candidates'])
    assert retriever.search('Project coordination procedure',999)['reason'] == 'project_not_found'

import pytest
from backend import project_service
from test_grounded_chat import calls, text, grounded


def test_selected_context_reaches_tools(api, provider):
    provider.messages.create.side_effect = [calls(('get_critical_rfis', {'project_id':101})), text('Critical RFIs: 1 and 3')]
    result = api.post('/ai/chat', json={'message':'Review critical RFIs in detail', 'project_id':101})
    assert result.json() == {'answer':'Critical RFIs: 1 and 3'}
    first = provider.messages.create.call_args_list[0].kwargs['messages'][0]['content']
    assert 'Selected project context: project 101' in first


@pytest.mark.parametrize('value', [0, -1, True, '101', 101.5])
def test_invalid_selected_project(api, provider, value):
    assert api.post('/ai/chat', json={'message':'Review critical RFIs in detail', 'project_id':value}).status_code == 422
    provider.messages.create.assert_not_called()


def test_missing_selected_project(api, provider):
    assert api.post('/ai/chat', json={'message':'Review critical RFIs in detail', 'project_id':999}).status_code == 404
    provider.messages.create.assert_not_called()


def test_conflicting_context_is_clarified(api, provider):
    result = api.post('/ai/chat', json={'message':'Show RFIs for project 202', 'project_id':101})
    assert 'selected project' in result.json()['answer'].lower()
    assert '202' in result.json()['answer'] and '101' in result.json()['answer']
    provider.messages.create.assert_not_called()


def test_no_selection_requests_context(api, provider):
    answer = api.post('/ai/chat', json={'message':'Review critical RFIs in detail'}).json()['answer']
    assert 'project ID' in answer
    provider.messages.create.assert_not_called()


def test_context_changes_do_not_stick(api, provider):
    provider.messages.create.side_effect = [text('First'), text('Second')]
    for project_id in (101, 202):
        assert api.post('/ai/chat', json={'message':'Project overview', 'project_id':project_id}).status_code == 200
        assert f'Selected project context: project {project_id}' in provider.messages.create.call_args.kwargs['messages'][0]['content']


def test_selected_document_context(api, provider, monkeypatch):
    from backend import claude_service as service
    source = {'chunk_id':'BF-RFI-001:r2:urgent-escalation:1', 'title':'Sample escalation',
        'section':'Urgent escalation', 'revision':2, 'project_id':None, 'sample_data':True,
        'excerpt':'The fictional project manager Mira Chen receives the packet.'}
    seen = []
    def search(query, project_id):
        seen.append(project_id)
        return {'status':'ok', 'evidence':[source]}
    monkeypatch.setattr(service, 'search_documents', search)
    provider.messages.create.side_effect = [calls(('search_documents', {'project_id':101,'query':'Cedar packet'})), grounded(source)]
    result = api.post('/ai/chat', json={'message':'Who receives the Cedar escalation packet?', 'project_id':101})
    assert source['chunk_id'] in result.json()['answer'] and seen == [101]


def test_tool_cannot_cross_selected_context(api, provider):
    provider.messages.create.side_effect = [calls(('get_critical_rfis', {'project_id':202}))]
    result = api.post('/ai/chat', json={'message':'Review critical RFIs in detail', 'project_id':101})
    assert 'insufficient' in result.json()['answer'].lower()


def test_selected_context_keeps_citation_validation(api, provider, monkeypatch):
    from backend import claude_service as service
    source = {'chunk_id':'REAL', 'project_id':None,'sample_data':True,'excerpt':'A fictional supporting passage.'}
    monkeypatch.setattr(service, 'search_documents', lambda *args: {'status':'ok','evidence':[source]})
    provider.messages.create.side_effect = [calls(('search_documents', {'project_id':101,'query':'escalation'})), grounded(source, source_id='INVENTED')]
    result = api.post('/ai/chat', json={'message':'What escalation steps are required?', 'project_id':101})
    assert result.json()['answer'] == service.INSUFFICIENT

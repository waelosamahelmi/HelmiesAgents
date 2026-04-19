from __future__ import annotations

from fastapi.testclient import TestClient

from helmiesagents.api.server import create_app
from helmiesagents.config import Settings


def _auth_header(client: TestClient) -> dict[str, str]:
    login = client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
    assert login.status_code == 200
    token = login.json()['access_token']
    return {'Authorization': f'Bearer {token}'}


def test_workforce_suggest_hire_and_manifest(tmp_path):
    settings = Settings(
        db_path=str(tmp_path / 'workforce.db'),
        auth_users_json='[{"username":"admin","password":"admin123","roles":["admin"],"tenant_id":"default"}]',
        jwt_secret='test-secret',
    )
    app = create_app(settings)
    client = TestClient(app)
    headers = _auth_header(client)

    suggest = client.post(
        '/workforce/suggest',
        headers=headers,
        json={
            'name': 'Mia',
            'job_title': 'Senior Marketing Manager',
            'cv_text': '10 years in growth marketing and B2B demand generation',
        },
    )
    assert suggest.status_code == 200
    s = suggest.json()
    assert s['suggested_name']
    assert s['system_prompt']
    assert isinstance(s['recommended_skills'], list) and len(s['recommended_skills']) > 0
    assert 0.0 < s['confidence_score'] <= 1.0
    assert isinstance(s['strengths'], list)
    assert isinstance(s['risk_flags'], list)

    hire = client.post(
        '/workforce/hire',
        headers=headers,
        json={
            'name': s['suggested_name'],
            'job_title': s['job_title'],
            'description': 'Own launch campaigns and partner with sales',
            'system_prompt': s['system_prompt'],
            'cv_text': 'same cv',
            'skills': s['recommended_skills'],
            'slack_channels': ['#marketing'],
        },
    )
    assert hire.status_code == 200
    agent_id = hire.json()['agent_id']
    assert isinstance(agent_id, int)

    agents = client.get('/workforce/agents', headers=headers)
    assert agents.status_code == 200
    rows = agents.json()['agents']
    assert any(a['id'] == agent_id for a in rows)

    manifest = client.post(
        '/workforce/manifest/slack',
        headers=headers,
        json={
            'app_name': 'HelmiesAI-Marketing',
            'bot_display_name': 'Mia Agent',
            'request_url': 'https://example.com/gateway/inbound',
            'redirect_urls': ['https://example.com/slack/oauth/callback'],
            'command_name': '/mia',
        },
    )
    assert manifest.status_code == 200
    m = manifest.json()['manifest']
    assert m['display_information']['name'] == 'HelmiesAI-Marketing'
    assert 'chat:write' in m['oauth_config']['scopes']['bot']
    assert 'commands' in m['oauth_config']['scopes']['bot']
    assert m['features']['slash_commands'][0]['command'] == '/mia'


def test_workforce_task_lifecycle(tmp_path):
    settings = Settings(
        db_path=str(tmp_path / 'workforce2.db'),
        auth_users_json='[{"username":"admin","password":"admin123","roles":["admin"],"tenant_id":"default"}]',
        jwt_secret='test-secret',
    )
    app = create_app(settings)
    client = TestClient(app)
    headers = _auth_header(client)

    # Hire lead agent
    suggest = client.post('/workforce/suggest', headers=headers, json={'job_title': 'Software Engineer', 'cv_text': 'Python APIs'})
    s = suggest.json()
    hire = client.post(
        '/workforce/hire',
        headers=headers,
        json={
            'name': s['suggested_name'],
            'job_title': s['job_title'],
            'description': 'Build platform APIs',
            'system_prompt': s['system_prompt'],
            'cv_text': 'Python APIs',
            'skills': s['recommended_skills'],
            'slack_channels': ['#engineering'],
        },
    )
    lead_id = hire.json()['agent_id']

    # Hire collaborator
    suggest2 = client.post('/workforce/suggest', headers=headers, json={'job_title': 'Designer', 'cv_text': 'UI systems'})
    s2 = suggest2.json()
    hire2 = client.post(
        '/workforce/hire',
        headers=headers,
        json={
            'name': s2['suggested_name'],
            'job_title': s2['job_title'],
            'description': 'Design UX and flows',
            'system_prompt': s2['system_prompt'],
            'cv_text': 'UI systems',
            'skills': s2['recommended_skills'],
            'slack_channels': ['#design'],
        },
    )
    collab_id = hire2.json()['agent_id']

    task = client.post(
        '/workforce/tasks',
        headers=headers,
        json={
            'title': 'Design and build launch dashboard',
            'description': 'Create first version of launch dashboard with KPI cards',
            'assignee_agent_id': lead_id,
            'collaborator_agent_ids': [collab_id],
            'priority': 'high',
        },
    )
    assert task.status_code == 200
    task_id = task.json()['task_id']

    run = client.post('/workforce/tasks/run', headers=headers, json={'task_id': task_id})
    assert run.status_code == 200
    result = run.json()['result']
    assert 'response' in result
    assert 'collaborator_notes' in result
    assert isinstance(result['collaborator_notes'], list)
    assert result.get('thread_id') == f'wf-task-{task_id}'
    assert isinstance(result.get('bus_messages'), list)
    assert len(result['bus_messages']) >= 1

    bus_read = client.post('/workforce/bus/mark-read', headers=headers, json={'thread_id': f'wf-task-{task_id}'})
    assert bus_read.status_code == 200

    bus_list = client.get('/workforce/bus/messages', headers=headers, params={'thread_id': f'wf-task-{task_id}'})
    assert bus_list.status_code == 200
    assert isinstance(bus_list.json()['messages'], list)

    tasks = client.get('/workforce/tasks', headers=headers)
    assert tasks.status_code == 200
    rows = tasks.json()['tasks']
    row = next(r for r in rows if r['id'] == task_id)
    assert row['status'] == 'completed'
    assert row['result'] is not None

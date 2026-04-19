from __future__ import annotations

from fastapi.testclient import TestClient

from helmiesagents.api.server import create_app
from helmiesagents.config import Settings


def _auth_header(client: TestClient) -> dict[str, str]:
    login = client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
    assert login.status_code == 200
    token = login.json()['access_token']
    return {'Authorization': f'Bearer {token}'}


def test_hire_agent_can_persist_model_preferences_and_update_them(tmp_path):
    settings = Settings(
        db_path=str(tmp_path / 'workforce_model_settings.db'),
        auth_users_json='[{"username":"admin","password":"admin123","roles":["admin"],"tenant_id":"default"}]',
        jwt_secret='very-secret-for-tests-1234567890',
    )
    app = create_app(settings)
    client = TestClient(app)
    headers = _auth_header(client)

    suggest = client.post(
        '/workforce/suggest',
        headers=headers,
        json={'job_title': 'Software Engineer', 'cv_text': 'Python APIs and testing'},
    )
    assert suggest.status_code == 200
    s = suggest.json()

    hire = client.post(
        '/workforce/hire',
        headers=headers,
        json={
            'name': s['suggested_name'],
            'job_title': s['job_title'],
            'description': 'Build and maintain backend services',
            'system_prompt': s['system_prompt'],
            'cv_text': 'Python APIs and testing',
            'skills': s['recommended_skills'],
            'slack_channels': ['#engineering'],
            'model_provider': 'openai',
            'model_name': 'gpt-4o-mini',
            'model_base_url': 'https://api.openai.com/v1',
        },
    )
    assert hire.status_code == 200
    agent_id = hire.json()['agent_id']

    agents = client.get('/workforce/agents', headers=headers)
    assert agents.status_code == 200
    agent_row = next(a for a in agents.json()['agents'] if a['id'] == agent_id)
    assert agent_row['model_provider'] == 'openai'
    assert agent_row['model_name'] == 'gpt-4o-mini'
    assert agent_row['model_base_url'] == 'https://api.openai.com/v1'

    update = client.post(
        f'/workforce/agents/{agent_id}/model',
        headers=headers,
        json={
            'model_provider': 'openai',
            'model_name': 'gpt-4.1-mini',
            'model_base_url': 'https://openrouter.ai/api/v1',
        },
    )
    assert update.status_code == 200
    assert update.json()['ok'] is True

    agents_after = client.get('/workforce/agents', headers=headers)
    assert agents_after.status_code == 200
    agent_row_after = next(a for a in agents_after.json()['agents'] if a['id'] == agent_id)
    assert agent_row_after['model_provider'] == 'openai'
    assert agent_row_after['model_name'] == 'gpt-4.1-mini'
    assert agent_row_after['model_base_url'] == 'https://openrouter.ai/api/v1'

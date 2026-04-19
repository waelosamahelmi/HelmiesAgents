from __future__ import annotations

import urllib.parse

from fastapi.testclient import TestClient

from helmiesagents.api.server import create_app
from helmiesagents.config import Settings


def _auth_header(client: TestClient) -> dict[str, str]:
    login = client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
    assert login.status_code == 200
    token = login.json()['access_token']
    return {'Authorization': f'Bearer {token}'}


def test_slack_oauth_wizard_start_and_callback_persist_installation(tmp_path):
    settings = Settings(
        db_path=str(tmp_path / 'slack_oauth.db'),
        auth_users_json='[{"username":"admin","password":"admin123","roles":["admin"],"tenant_id":"default"}]',
        jwt_secret='very-secret-test-key-1234567890',
        slack_client_id='111.222',
        slack_client_secret='secret-xyz',
        slack_signing_secret='signing-xyz',
        slack_oauth_redirect_url='https://example.com/slack/oauth/callback',
    )
    app = create_app(settings)
    client = TestClient(app)
    headers = _auth_header(client)

    start = client.post(
        '/workforce/slack/oauth/start',
        headers=headers,
        json={
            'app_name': 'HelmiesAI Team',
            'request_url': 'https://example.com/gateway/inbound',
            'redirect_urls': ['https://example.com/slack/oauth/callback'],
            'command_name': '/helmies',
        },
    )
    assert start.status_code == 200, start.text
    start_body = start.json()
    assert start_body['state']
    assert 'slack.com/oauth/v2/authorize' in start_body['install_url']

    callback = client.post(
        '/workforce/slack/oauth/callback',
        headers=headers,
        json={
            'state': start_body['state'],
            'code': 'fake-auth-code',
            'team_id': 'T123',
            'team_name': 'Helmies Team',
            'app_id': 'A123',
            'bot_user_id': 'U123',
            'access_token': 'xoxb-fake',
            'scope': 'chat:write,commands',
            'incoming_webhook_url': 'https://hooks.slack.com/services/T123/B123/XXX',
        },
    )
    assert callback.status_code == 200, callback.text
    cb = callback.json()
    assert cb['ok'] is True

    installs = client.get('/workforce/slack/installations', headers=headers)
    assert installs.status_code == 200
    rows = installs.json()['items']
    assert len(rows) >= 1
    assert rows[0]['team_id'] == 'T123'
    assert rows[0]['team_name'] == 'Helmies Team'


def test_slack_oauth_callback_rejects_invalid_state(tmp_path):
    settings = Settings(
        db_path=str(tmp_path / 'slack_oauth_invalid.db'),
        auth_users_json='[{"username":"admin","password":"admin123","roles":["admin"],"tenant_id":"default"}]',
        jwt_secret='very-secret-test-key-1234567890',
    )
    app = create_app(settings)
    client = TestClient(app)
    headers = _auth_header(client)

    callback = client.post(
        '/workforce/slack/oauth/callback',
        headers=headers,
        json={
            'state': 'bad-state',
            'code': 'bad-code',
            'team_id': 'Tbad',
            'access_token': 'xoxb-bad',
        },
    )
    assert callback.status_code == 400
    assert 'invalid' in callback.text.lower() or 'state' in callback.text.lower()

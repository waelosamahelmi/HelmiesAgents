from fastapi.testclient import TestClient

from helmiesagents.api.server import create_app
from helmiesagents.config import Settings


def test_login_and_chat_flow(tmp_path):
    settings = Settings(
        db_path=str(tmp_path / "api.db"),
        auth_users_json='[{"username":"admin","password":"admin123","roles":["admin"],"tenant_id":"default"}]',
        jwt_secret="test-secret",
    )
    app = create_app(settings)
    client = TestClient(app)

    login = client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
    assert login.status_code == 200
    token = login.json()['access_token']

    chat = client.post('/chat', headers={'Authorization': f'Bearer {token}'}, json={'session_id': 's1', 'message': 'what time is it'})
    assert chat.status_code == 200
    assert 'response' in chat.json()

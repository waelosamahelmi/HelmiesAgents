from __future__ import annotations

from fastapi.testclient import TestClient

from helmiesagents.api.server import create_app
from helmiesagents.config import Settings


def _auth_header(client: TestClient) -> dict[str, str]:
    login = client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
    assert login.status_code == 200
    token = login.json()['access_token']
    return {'Authorization': f'Bearer {token}'}


def test_recurring_workforce_schedule_creates_tasks_and_updates_status(tmp_path):
    settings = Settings(
        db_path=str(tmp_path / 'wf_scheduler.db'),
        auth_users_json='[{"username":"admin","password":"admin123","roles":["admin"],"tenant_id":"default"}]',
        jwt_secret='very-secret-test-key-1234567890',
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
            'description': 'Build backend APIs',
            'system_prompt': s['system_prompt'],
            'cv_text': 'Python APIs and testing',
            'skills': s['recommended_skills'],
            'slack_channels': ['#engineering'],
        },
    )
    assert hire.status_code == 200
    assignee_id = hire.json()['agent_id']

    create_schedule = client.post(
        '/workforce/recurring',
        headers=headers,
        json={
            'title': 'Daily quality check',
            'description': 'Review quality metrics and suggest fixes',
            'assignee_agent_id': assignee_id,
            'collaborator_agent_ids': [],
            'priority': 'medium',
            'interval_minutes': 60,
            'auto_run': False,
            'enabled': True,
            'start_immediately': True,
        },
    )
    assert create_schedule.status_code == 200
    schedule_id = create_schedule.json()['recurring_id']

    list_schedules = client.get('/workforce/recurring', headers=headers)
    assert list_schedules.status_code == 200
    rows = list_schedules.json()['items']
    assert any(r['id'] == schedule_id for r in rows)

    run_once = client.post('/workforce/recurring/run_once', headers=headers)
    assert run_once.status_code == 200, run_once.text
    created = run_once.json()['created_task_ids']
    assert isinstance(created, list)
    assert len(created) >= 1

    task_id = created[0]
    tasks = client.get('/workforce/tasks', headers=headers)
    assert tasks.status_code == 200
    task_row = next(t for t in tasks.json()['tasks'] if t['id'] == task_id)
    assert task_row['status'] in {'open', 'in_progress', 'completed'}

    mark_progress = client.post(
        f'/workforce/tasks/{task_id}/status',
        headers=headers,
        json={'status': 'in_progress'},
    )
    assert mark_progress.status_code == 200

    tasks_after = client.get('/workforce/tasks', headers=headers)
    assert tasks_after.status_code == 200
    task_row_after = next(t for t in tasks_after.json()['tasks'] if t['id'] == task_id)
    assert task_row_after['status'] == 'in_progress'

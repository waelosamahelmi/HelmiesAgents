from helmiesagents.memory.store import MemoryStore
from helmiesagents.scim.service import ScimService, ScimUser


def test_scim_user_upsert(tmp_path):
    store = MemoryStore(str(tmp_path / 'scim.db'))
    scim = ScimService(store)
    scim.create_or_update_user(ScimUser(tenant_id='t1', username='alice', password='pw', roles=['admin']))
    users = scim.list_users('t1')
    assert len(users) == 1
    assert users[0]['username'] == 'alice'

from helmiesagents.security.vault import SecretsVault


def test_vault_encrypt_decrypt():
    v = SecretsVault('test-key')
    enc = v.encrypt('hello')
    assert enc != 'hello'
    dec = v.decrypt(enc)
    assert dec == 'hello'

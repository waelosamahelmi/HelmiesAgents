import base64

import jwt
from fastapi.testclient import TestClient

from helmiesagents.api.server import create_app
from helmiesagents.config import Settings


def _sso_settings(tmp_path):
    return Settings(
        db_path=str(tmp_path / "sso.db"),
        jwt_secret="local-jwt-secret-with-safe-minimum-length-32+",
        sso_enabled=True,
        sso_oidc_issuer="https://idp.example.com",
        sso_oidc_audience="helmiesagents",
        sso_oidc_jwt_secret="oidc-shared-secret-with-safe-minimum-length-32+",
        sso_saml_expected_issuer="urn:test:idp",
    )


def test_oidc_sso_login_success(tmp_path):
    settings = _sso_settings(tmp_path)
    app = create_app(settings)
    client = TestClient(app)

    id_token = jwt.encode(
        {
            "sub": "oidc-user-1",
            "iss": settings.sso_oidc_issuer,
            "aud": settings.sso_oidc_audience,
            "roles": ["admin", "viewer"],
            "tenant_id": "tenant-oidc",
        },
        settings.sso_oidc_jwt_secret,
        algorithm="HS256",
    )

    res = client.post("/auth/sso/oidc", json={"id_token": id_token})
    assert res.status_code == 200
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["tenant_id"] == "tenant-oidc"
    assert "admin" in body["roles"]
    assert body["provider"] == "oidc"
    assert body["subject"] == "oidc-user-1"

    token = body["access_token"]
    chat = client.post(
        "/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"session_id": "sso-oidc", "message": "what time is it"},
    )
    assert chat.status_code == 200
    assert chat.json()["tenant_id"] == "tenant-oidc"


def test_oidc_sso_login_rejects_wrong_issuer(tmp_path):
    settings = _sso_settings(tmp_path)
    app = create_app(settings)
    client = TestClient(app)

    id_token = jwt.encode(
        {
            "sub": "oidc-user-2",
            "iss": "https://evil-idp.example.com",
            "aud": settings.sso_oidc_audience,
            "roles": ["viewer"],
            "tenant_id": "tenant-oidc",
        },
        settings.sso_oidc_jwt_secret,
        algorithm="HS256",
    )

    res = client.post("/auth/sso/oidc", json={"id_token": id_token})
    assert res.status_code == 401


def test_saml_sso_login_success(tmp_path):
    settings = _sso_settings(tmp_path)
    app = create_app(settings)
    client = TestClient(app)

    xml = """
    <Assertion>
      <Issuer>urn:test:idp</Issuer>
      <Subject><NameID>saml-user-1</NameID></Subject>
      <AttributeStatement>
        <Attribute Name=\"roles\">
          <AttributeValue>admin</AttributeValue>
          <AttributeValue>viewer</AttributeValue>
        </Attribute>
        <Attribute Name=\"tenant_id\">
          <AttributeValue>tenant-saml</AttributeValue>
        </Attribute>
      </AttributeStatement>
    </Assertion>
    """.strip()
    assertion_b64 = base64.b64encode(xml.encode()).decode()

    res = client.post("/auth/sso/saml", json={"assertion_b64": assertion_b64})
    assert res.status_code == 200
    body = res.json()
    assert body["provider"] == "saml"
    assert body["subject"] == "saml-user-1"
    assert body["tenant_id"] == "tenant-saml"
    assert "admin" in body["roles"]


def test_sso_login_disabled(tmp_path):
    settings = Settings(db_path=str(tmp_path / "sso-disabled.db"), sso_enabled=False)
    app = create_app(settings)
    client = TestClient(app)

    res = client.post("/auth/sso/oidc", json={"id_token": "dummy"})
    assert res.status_code == 400
    assert "disabled" in res.json()["detail"].lower()

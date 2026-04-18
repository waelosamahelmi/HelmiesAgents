from __future__ import annotations

import base64
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

import jwt

from helmiesagents.config import Settings
from helmiesagents.models import RequestContext


@dataclass
class SSOResult:
    provider: str
    subject: str
    tenant_id: str
    roles: list[str]
    attributes: dict[str, Any]


class SSOAuthService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _require_enabled(self) -> None:
        if not self.settings.sso_enabled:
            raise ValueError("SSO is disabled")

    def login_oidc(self, id_token: str) -> SSOResult:
        self._require_enabled()

        if not self.settings.sso_oidc_jwt_secret:
            raise ValueError("OIDC secret not configured")
        if not self.settings.sso_oidc_issuer:
            raise ValueError("OIDC issuer not configured")
        if not self.settings.sso_oidc_audience:
            raise ValueError("OIDC audience not configured")

        payload = jwt.decode(
            id_token,
            self.settings.sso_oidc_jwt_secret,
            algorithms=["HS256"],
            audience=self.settings.sso_oidc_audience,
            issuer=self.settings.sso_oidc_issuer,
            options={"require": ["sub", "iss", "aud"]},
        )

        subject = str(payload.get("sub", ""))
        if not subject:
            raise ValueError("OIDC token missing sub")

        tenant_id = str(payload.get("tenant_id") or payload.get("tid") or "default")
        roles_raw = payload.get("roles", ["viewer"])
        roles = [str(r) for r in roles_raw] if isinstance(roles_raw, list) else ["viewer"]

        return SSOResult(
            provider="oidc",
            subject=subject,
            tenant_id=tenant_id,
            roles=roles,
            attributes=payload,
        )

    def login_saml(self, assertion_b64: str) -> SSOResult:
        self._require_enabled()

        xml = base64.b64decode(assertion_b64).decode("utf-8", errors="replace")
        root = ET.fromstring(xml)

        issuer = (root.findtext(".//Issuer") or "").strip()
        expected_issuer = self.settings.sso_saml_expected_issuer
        if expected_issuer and issuer != expected_issuer:
            raise ValueError("Unexpected SAML issuer")

        subject = (root.findtext(".//Subject/NameID") or "").strip()
        if not subject:
            raise ValueError("SAML assertion missing Subject/NameID")

        attrs: dict[str, list[str]] = {}
        for attr in root.findall(".//Attribute"):
            name = (attr.attrib.get("Name") or "").strip()
            if not name:
                continue
            values = [
                (v.text or "").strip()
                for v in attr.findall("AttributeValue")
                if (v.text or "").strip()
            ]
            attrs[name] = values

        roles = attrs.get("roles") or ["viewer"]
        tenant_id = (attrs.get("tenant_id") or ["default"])[0]

        return SSOResult(
            provider="saml",
            subject=subject,
            tenant_id=tenant_id,
            roles=roles,
            attributes={"issuer": issuer, "attributes": attrs},
        )

    def to_context(self, result: SSOResult) -> RequestContext:
        return RequestContext(
            tenant_id=result.tenant_id,
            user_id=result.subject,
            roles=result.roles,
            auto_approve=False,
        )

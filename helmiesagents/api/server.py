from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from helmiesagents.approvals.manager import ApprovalManager
from helmiesagents.benchmark.harness import BenchmarkHarness, BenchmarkScenario
from helmiesagents.config import Settings
from helmiesagents.core.agent import HelmiesAgent
from helmiesagents.enterprise.compliance import export_audit_logs
from helmiesagents.gateways.discord import DiscordAdapter
from helmiesagents.gateways.router import GatewayEvent, GatewayRouter
from helmiesagents.gateways.slack import SlackAdapter
from helmiesagents.gateways.telegram import TelegramAdapter
from helmiesagents.gateways.whatsapp import WhatsAppAdapter
from helmiesagents.marketplace.skills import SkillPackage, export_skill_package, import_skill_package
from helmiesagents.memory.store import MemoryStore
from helmiesagents.models import RequestContext, is_admin
from helmiesagents.scim.service import ScimService, ScimUser
from helmiesagents.security.auth import AuthService
from helmiesagents.security.policy import PolicyEngine
from helmiesagents.security.sso import SSOAuthService
from helmiesagents.security.vault import SecretsVault
from helmiesagents.tools.builtin import install_builtin_tools
from helmiesagents.tools.registry import ToolRegistry
from helmiesagents.workflow.engine import WorkflowEngine
from helmiesagents.workforce import WorkforceService


class LoginRequest(BaseModel):
    username: str
    password: str


class OIDCLoginRequest(BaseModel):
    id_token: str


class SAMLLoginRequest(BaseModel):
    assertion_b64: str


class ChatRequest(BaseModel):
    session_id: str = "default"
    message: str


class SkillRequest(BaseModel):
    name: str
    description: str
    content: str


class WorkflowRequest(BaseModel):
    workflow_path: str
    session_id: str = "workflow"


class GatewaySendRequest(BaseModel):
    platform: str
    channel_id: str
    text: str


class ApprovalDecisionRequest(BaseModel):
    approval_id: int
    approve: bool


class BenchmarkRequest(BaseModel):
    suite_name: str = "default"
    scenarios: list[dict[str, Any]] = []


class BenchmarkGateRequest(BaseModel):
    suite_name: str
    min_score: float | None = None


class ScimCreateUserRequest(BaseModel):
    tenant_id: str
    username: str
    password: str
    roles: list[str]


class SecretRequest(BaseModel):
    key: str
    value: str


class WorkforceSuggestRequest(BaseModel):
    name: str | None = None
    job_title: str
    cv_text: str = ""


class WorkforceHireRequest(BaseModel):
    name: str
    job_title: str
    description: str
    system_prompt: str
    cv_text: str = ""
    skills: list[str] = []
    slack_channels: list[str] = []


class WorkforceTaskRequest(BaseModel):
    title: str
    description: str
    assignee_agent_id: int | None = None
    collaborator_agent_ids: list[int] = []
    priority: str = "medium"


class WorkforceTaskRunRequest(BaseModel):
    task_id: int


class SlackManifestRequest(BaseModel):
    app_name: str
    bot_display_name: str
    request_url: str
    redirect_urls: list[str] = []


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.ensure_dirs()

    memory = MemoryStore(settings.db_path)
    registry = ToolRegistry()
    install_builtin_tools(registry, memory)
    agent = HelmiesAgent(settings=settings, memory=memory, tools=registry)
    workflow_engine = WorkflowEngine(agent=agent, memory=memory, settings=settings)
    gateway_router = GatewayRouter(agent=agent)
    policy = PolicyEngine(policy_file=settings.policy_dsl_file)
    approval_manager = ApprovalManager(memory=memory, policy=policy)
    benchmark = BenchmarkHarness(agent=agent, memory=memory)
    auth = AuthService(settings)
    sso = SSOAuthService(settings)
    scim = ScimService(memory=memory)
    workforce = WorkforceService(memory=memory)

    vault = SecretsVault(settings.vault_key) if settings.vault_key else None

    app = FastAPI(title="HelmiesAgents API", version="0.2.0")

    def get_ctx(authorization: str | None) -> RequestContext:
        if not authorization:
            return RequestContext()
        if not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        token = authorization.split(" ", 1)[1]
        try:
            return auth.decode_token(token)
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {e}") from e

    def get_ctx_from_ws_token(token: str | None) -> RequestContext:
        if not token:
            return RequestContext()
        try:
            return auth.decode_token(token)
        except Exception:
            return RequestContext()

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "ok": True,
            "provider": agent.provider.name,
            "tools": registry.list_tools(),
        }

    @app.post("/auth/login")
    def login(req: LoginRequest) -> dict[str, Any]:
        ctx = auth.authenticate(req.username, req.password)
        if not ctx:
            raise HTTPException(status_code=401, detail="invalid credentials")
        token = auth.create_token(ctx)
        return {"access_token": token, "token_type": "bearer", "tenant_id": ctx.tenant_id, "roles": ctx.roles}

    @app.post("/auth/sso/oidc")
    def login_sso_oidc(req: OIDCLoginRequest) -> dict[str, Any]:
        try:
            sso_result = sso.login_oidc(req.id_token)
        except Exception as e:
            if "disabled" in str(e).lower():
                raise HTTPException(status_code=400, detail=str(e)) from e
            raise HTTPException(status_code=401, detail=f"invalid oidc login: {e}") from e

        ctx = sso.to_context(sso_result)
        token = auth.create_token(ctx)
        return {
            "access_token": token,
            "token_type": "bearer",
            "tenant_id": ctx.tenant_id,
            "roles": ctx.roles,
            "provider": sso_result.provider,
            "subject": sso_result.subject,
        }

    @app.post("/auth/sso/saml")
    def login_sso_saml(req: SAMLLoginRequest) -> dict[str, Any]:
        try:
            sso_result = sso.login_saml(req.assertion_b64)
        except Exception as e:
            if "disabled" in str(e).lower():
                raise HTTPException(status_code=400, detail=str(e)) from e
            raise HTTPException(status_code=401, detail=f"invalid saml login: {e}") from e

        ctx = sso.to_context(sso_result)
        token = auth.create_token(ctx)
        return {
            "access_token": token,
            "token_type": "bearer",
            "tenant_id": ctx.tenant_id,
            "roles": ctx.roles,
            "provider": sso_result.provider,
            "subject": sso_result.subject,
        }

    @app.post("/chat")
    def chat(req: ChatRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = get_ctx(authorization)
        res = agent.chat(session_id=req.session_id, user_message=req.message, ctx=ctx)
        return {
            "response": res.text,
            "plan": res.plan,
            "tools_executed": res.tools_executed,
            "quality": res.quality,
            "tenant_id": ctx.tenant_id,
        }

    @app.websocket("/chat/ws")
    async def chat_ws(ws: WebSocket) -> None:
        await ws.accept()
        try:
            payload = await ws.receive_json()
            token = payload.get("token")
            session_id = payload.get("session_id", "default")
            message = payload.get("message", "")

            ctx = get_ctx_from_ws_token(token)

            if not isinstance(message, str) or not message.strip():
                await ws.send_json({"type": "error", "message": "message must be a non-empty string"})
                await ws.close(code=1003)
                return

            for event in agent.stream_chat(session_id=session_id, user_message=message, ctx=ctx):
                await ws.send_json({"type": event.type, **event.data})

            await ws.send_json({"type": "done"})
            await ws.close(code=1000)
        except WebSocketDisconnect:
            return
        except Exception as e:
            await ws.send_json({"type": "error", "message": str(e)})
            await ws.close(code=1011)

    @app.get("/execution/budget/effective")
    def execution_budget_effective(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = get_ctx(authorization)
        return {
            "tenant_id": ctx.tenant_id,
            "user_id": ctx.user_id,
            "roles": ctx.roles,
            "budget": agent.get_effective_budget(ctx),
        }

    @app.get("/memory/search")
    def memory_search(q: str, limit: int = 10, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = get_ctx(authorization)
        hits = memory.search_messages(ctx.tenant_id, q, limit=limit)
        return {"hits": [h.__dict__ for h in hits]}

    @app.get("/skills")
    def list_skills(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = get_ctx(authorization)
        return {"skills": memory.list_skills(ctx.tenant_id)}

    @app.post("/skills")
    def save_skill(req: SkillRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = get_ctx(authorization)
        memory.save_skill(ctx.tenant_id, req.name, req.description, req.content)
        return {"ok": True}

    @app.post("/skills/export")
    def export_skill(name: str, out_path: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = get_ctx(authorization)
        sk = memory.get_skill(ctx.tenant_id, name)
        if not sk:
            raise HTTPException(status_code=404, detail="skill not found")
        pkg = SkillPackage(name=sk["name"], version="1.0.0", description=sk["description"], content=sk["content"])
        export_skill_package(out_path, pkg)
        return {"ok": True, "path": out_path}

    @app.post("/skills/import")
    def import_skill(path: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = get_ctx(authorization)
        pkg = import_skill_package(path)
        memory.save_skill(ctx.tenant_id, pkg.name, pkg.description, pkg.content)
        return {"ok": True, "name": pkg.name}

    @app.post("/workflow/run")
    def run_workflow(req: WorkflowRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = get_ctx(authorization)
        result = workflow_engine.run(workflow_path=req.workflow_path, session_id=req.session_id, ctx=ctx)
        return {
            "run_id": result.run_id,
            "name": result.name,
            "status": result.status,
            "outputs": result.outputs,
        }

    @app.post("/workflow/run_async")
    async def run_workflow_async(req: WorkflowRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = get_ctx(authorization)
        job_id = await workflow_engine.run_async(workflow_path=req.workflow_path, session_id=req.session_id, ctx=ctx)
        return {"job_id": job_id}

    @app.get("/workflow/job/{job_id}")
    def workflow_job(job_id: str) -> dict[str, Any]:
        job = workflow_engine.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        return job.__dict__

    @app.post("/workflow/job/{job_id}/cancel")
    def workflow_job_cancel(job_id: str) -> dict[str, Any]:
        ok = workflow_engine.cancel_job(job_id)
        return {"ok": ok}

    @app.get("/workflow/jobs")
    def workflow_jobs(limit: int = 100, status: str | None = None) -> dict[str, Any]:
        jobs = workflow_engine.list_jobs(limit=limit, status=status)
        return {"jobs": [j.__dict__ for j in jobs], "backend": workflow_engine.queue_backend}

    @app.post("/workflow/worker/run_once")
    def workflow_worker_run_once(worker_id: str = "api-manual") -> dict[str, Any]:
        processed = workflow_engine.process_queue_once(worker_id=worker_id)
        return {"processed": processed, "backend": workflow_engine.queue_backend}

    @app.get("/workflow/runs")
    def list_workflow_runs(limit: int = 100, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = get_ctx(authorization)
        return {"runs": memory.list_workflow_runs(ctx.tenant_id, limit=limit)}

    @app.get("/workflow/runs/{run_id}")
    def get_workflow_run(run_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = get_ctx(authorization)
        row = memory.get_workflow_run(run_id)
        if not row:
            raise HTTPException(status_code=404, detail="run not found")
        if row["tenant_id"] != ctx.tenant_id:
            raise HTTPException(status_code=403, detail="forbidden")
        return row

    @app.post("/gateway/send")
    def gateway_send(req: GatewaySendRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = get_ctx(authorization)
        if not is_admin(ctx):
            raise HTTPException(status_code=403, detail="admin required")

        platform = req.platform.lower()
        if platform == "slack":
            adapter = SlackAdapter(settings.slack_bot_token)
        elif platform == "telegram":
            adapter = TelegramAdapter(settings.telegram_bot_token)
        elif platform == "discord":
            adapter = DiscordAdapter(settings.discord_bot_token)
        elif platform == "whatsapp":
            adapter = WhatsAppAdapter(settings.whatsapp_api_url, settings.whatsapp_token)
        else:
            raise HTTPException(status_code=400, detail="unsupported platform")

        result = adapter.send_message(req.channel_id, req.text)
        return {"ok": True, "result": result}

    @app.post("/gateway/inbound")
    def gateway_inbound(event: GatewaySendRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = get_ctx(authorization)
        out = gateway_router.handle_event(
            GatewayEvent(
                platform=event.platform,
                channel_id=event.channel_id,
                user_id=ctx.user_id,
                text=event.text,
            ),
            ctx=ctx,
        )
        return out

    @app.post("/approvals/check")
    def approvals_check(tool: str, args: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = get_ctx(authorization)
        outcome = approval_manager.check_or_create(ctx, tool, args)
        return outcome.__dict__

    @app.post("/approvals/decide")
    def approvals_decide(req: ApprovalDecisionRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = get_ctx(authorization)
        if not is_admin(ctx):
            raise HTTPException(status_code=403, detail="admin required")
        memory.set_approval_status(req.approval_id, "approved" if req.approve else "rejected")
        return {"ok": True}

    @app.post("/benchmark/run")
    def benchmark_run(req: BenchmarkRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = get_ctx(authorization)

        if req.scenarios:
            scenarios = [BenchmarkScenario(name=s["name"], prompt=s["prompt"], must_contain=s.get("must_contain", [])) for s in req.scenarios]
            summary = benchmark.run_suite(ctx, req.suite_name, scenarios)
            return summary.__dict__

        if settings.eval_suites_file:
            summary = benchmark.run_named_suite(
                ctx,
                suite_name=req.suite_name,
                suites_file=settings.eval_suites_file,
            )
            return summary.__dict__

        raise HTTPException(
            status_code=400,
            detail="No scenarios provided and HELMIES_EVAL_SUITES_FILE is not configured",
        )

    @app.get("/benchmark/suites")
    def benchmark_suites() -> dict[str, Any]:
        if not settings.eval_suites_file:
            return {"suites": []}
        return {"suites": benchmark.list_suites(settings.eval_suites_file)}

    @app.post("/benchmark/gate")
    def benchmark_gate(req: BenchmarkGateRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = get_ctx(authorization)
        if not settings.eval_suites_file:
            raise HTTPException(status_code=400, detail="HELMIES_EVAL_SUITES_FILE is not configured")

        threshold = req.min_score if req.min_score is not None else settings.eval_min_score
        summary = benchmark.run_named_suite(
            ctx,
            suite_name=req.suite_name,
            suites_file=settings.eval_suites_file,
            min_score_override=threshold,
        )
        return {
            "ok": bool(summary.gate_passed),
            "threshold": threshold,
            "summary": summary.__dict__,
        }

    @app.get("/benchmark/results")
    def benchmark_results(suite_name: str | None = None, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = get_ctx(authorization)
        return {"results": memory.list_benchmark_results(ctx.tenant_id, suite_name=suite_name)}

    @app.get("/audit/logs")
    def audit_logs(limit: int = 200, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = get_ctx(authorization)
        if not is_admin(ctx):
            raise HTTPException(status_code=403, detail="admin required")
        return {"logs": memory.list_audit(ctx.tenant_id, limit=limit)}

    @app.post("/audit/export")
    def audit_export(out_path: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = get_ctx(authorization)
        if not is_admin(ctx):
            raise HTTPException(status_code=403, detail="admin required")
        return export_audit_logs(memory, ctx.tenant_id, out_path)

    @app.post("/scim/users")
    def scim_users_create(req: ScimCreateUserRequest, x_scim_token: str | None = Header(default=None)) -> dict[str, Any]:
        if x_scim_token != settings.scim_token:
            raise HTTPException(status_code=401, detail="invalid scim token")
        scim.create_or_update_user(
            ScimUser(
                tenant_id=req.tenant_id,
                username=req.username,
                password=req.password,
                roles=req.roles,
            )
        )
        return {"ok": True}

    @app.get("/scim/users")
    def scim_users_list(tenant_id: str, x_scim_token: str | None = Header(default=None)) -> dict[str, Any]:
        if x_scim_token != settings.scim_token:
            raise HTTPException(status_code=401, detail="invalid scim token")
        return {"users": scim.list_users(tenant_id)}

    @app.post("/vault/secrets")
    def vault_set(req: SecretRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = get_ctx(authorization)
        if not is_admin(ctx):
            raise HTTPException(status_code=403, detail="admin required")
        if not vault:
            raise HTTPException(status_code=400, detail="vault is not enabled; set HELMIES_VAULT_KEY")

        enc = vault.encrypt(req.value)
        with memory._connect() as conn:
            conn.execute(
                """
                INSERT INTO vault_secrets(tenant_id, key, value_enc, created_at, updated_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(tenant_id, key) DO UPDATE SET
                    value_enc=excluded.value_enc,
                    updated_at=excluded.updated_at
                """,
                (ctx.tenant_id, req.key, enc, "now", "now"),
            )
        return {"ok": True}

    @app.get("/vault/secrets/{key}")
    def vault_get(key: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = get_ctx(authorization)
        if not is_admin(ctx):
            raise HTTPException(status_code=403, detail="admin required")
        if not vault:
            raise HTTPException(status_code=400, detail="vault is not enabled; set HELMIES_VAULT_KEY")
        with memory._connect() as conn:
            row = conn.execute(
                "SELECT value_enc FROM vault_secrets WHERE tenant_id=? AND key=?",
                (ctx.tenant_id, key),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="secret not found")
        return {"key": key, "value": vault.decrypt(row["value_enc"])}

    @app.post("/workforce/suggest")
    def workforce_suggest(req: WorkforceSuggestRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        _ = get_ctx(authorization)
        suggestion = workforce.suggest_profile(name=req.name, job_title=req.job_title, cv_text=req.cv_text)
        return {
            "suggested_name": suggestion.suggested_name,
            "job_title": suggestion.job_title,
            "summary": suggestion.summary,
            "system_prompt": suggestion.system_prompt,
            "recommended_skills": suggestion.recommended_skills,
        }

    @app.post("/workforce/hire")
    def workforce_hire(req: WorkforceHireRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = get_ctx(authorization)
        if not is_admin(ctx):
            raise HTTPException(status_code=403, detail="admin required")

        agent_id = workforce.hire_agent(
            tenant_id=ctx.tenant_id,
            name=req.name,
            job_title=req.job_title,
            description=req.description,
            system_prompt=req.system_prompt,
            cv_text=req.cv_text,
            skills=req.skills,
            slack_channels=req.slack_channels,
        )
        memory.log_audit(
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            event_type="workforce_hire",
            payload_json=json.dumps({"agent_id": agent_id, "name": req.name, "job_title": req.job_title}),
        )
        return {"ok": True, "agent_id": agent_id}

    @app.get("/workforce/agents")
    def workforce_agents(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = get_ctx(authorization)
        return {"agents": workforce.list_agents(ctx.tenant_id)}

    @app.post("/workforce/manifest/slack")
    def workforce_manifest_slack(req: SlackManifestRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = get_ctx(authorization)
        if not is_admin(ctx):
            raise HTTPException(status_code=403, detail="admin required")
        manifest = workforce.build_slack_manifest(
            app_name=req.app_name,
            bot_display_name=req.bot_display_name,
            request_url=req.request_url,
            redirect_urls=req.redirect_urls,
        )
        return {"manifest": manifest}

    @app.post("/workforce/tasks")
    def workforce_create_task(req: WorkforceTaskRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = get_ctx(authorization)
        task_id = workforce.create_task(
            tenant_id=ctx.tenant_id,
            created_by=ctx.user_id,
            title=req.title,
            description=req.description,
            assignee_agent_id=req.assignee_agent_id,
            collaborator_agent_ids=req.collaborator_agent_ids,
            priority=req.priority,
        )
        return {"ok": True, "task_id": task_id}

    @app.get("/workforce/tasks")
    def workforce_tasks(status: str | None = None, limit: int = 200, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = get_ctx(authorization)
        return {"tasks": workforce.list_tasks(tenant_id=ctx.tenant_id, status=status, limit=limit)}

    @app.post("/workforce/tasks/run")
    def workforce_run_task(req: WorkforceTaskRunRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        ctx = get_ctx(authorization)
        if not is_admin(ctx):
            raise HTTPException(status_code=403, detail="admin required")
        result = workforce.run_task(
            agent=agent,
            tenant_id=ctx.tenant_id,
            task_id=req.task_id,
            actor_user_id=ctx.user_id,
        )
        return {"ok": True, "result": result}

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return Path(Path(__file__).resolve().parent.parent / "web" / "index.html").read_text()

    return app

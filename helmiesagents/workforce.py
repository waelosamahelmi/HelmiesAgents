from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from helmiesagents.core.agent import HelmiesAgent
from helmiesagents.memory.store import MemoryStore
from helmiesagents.models import RequestContext


_DEFAULT_ROLE_SKILLS: dict[str, list[str]] = {
    "marketing": ["content strategy", "campaign planning", "analytics"],
    "sales": ["lead qualification", "outreach", "crm hygiene"],
    "developer": ["python", "testing", "code review"],
    "designer": ["ux", "ui", "prototyping"],
    "operations": ["incident response", "runbooks", "automation"],
    "support": ["customer communication", "triage", "knowledge base"],
}

_DEFAULT_ROLE_PROMPTS: dict[str, str] = {
    "marketing": "You are a senior marketing strategist focused on measurable growth and clear messaging.",
    "sales": "You are a top-performing B2B account executive focused on conversion and relationship quality.",
    "developer": "You are a senior software engineer who ships reliable code with tests and clear tradeoff analysis.",
    "designer": "You are a product designer who balances usability, accessibility, and brand consistency.",
    "operations": "You are an operations lead focused on reliability, process clarity, and root-cause elimination.",
    "support": "You are a support specialist who resolves issues quickly and improves documentation quality.",
}


@dataclass
class WorkforceProfileSuggestion:
    suggested_name: str
    job_title: str
    summary: str
    system_prompt: str
    recommended_skills: list[str]


class WorkforceService:
    def __init__(self, memory: MemoryStore) -> None:
        self.memory = memory

    @staticmethod
    def _normalize_role(job_title: str) -> str:
        jt = (job_title or "").strip().lower()
        if any(k in jt for k in ["market", "growth", "brand"]):
            return "marketing"
        if any(k in jt for k in ["sales", "account", "bizdev", "business development"]):
            return "sales"
        if any(k in jt for k in ["engineer", "developer", "backend", "frontend", "full stack", "software"]):
            return "developer"
        if any(k in jt for k in ["design", "ux", "ui", "product design"]):
            return "designer"
        if any(k in jt for k in ["ops", "operation", "sre", "devops"]):
            return "operations"
        if any(k in jt for k in ["support", "customer success", "customer service"]):
            return "support"
        return "operations"

    def suggest_profile(self, *, name: str | None, job_title: str, cv_text: str = "") -> WorkforceProfileSuggestion:
        role = self._normalize_role(job_title)
        base_prompt = _DEFAULT_ROLE_PROMPTS[role]
        skills = _DEFAULT_ROLE_SKILLS[role]

        cv_trimmed = (cv_text or "").strip()
        cv_context = cv_trimmed[:1200] if cv_trimmed else "No CV provided."
        suggested_name = (name or f"{job_title.strip()} Agent").strip()

        system_prompt = (
            f"{base_prompt}\n"
            "Operate as a reliable teammate in a multi-agent company setup.\n"
            "Coordinate with peer agents, keep outputs concise, and escalate risks early.\n"
            f"Candidate context:\n{cv_context}"
        )
        summary = f"Suggested profile for {job_title} based on role heuristics and CV context."

        return WorkforceProfileSuggestion(
            suggested_name=suggested_name,
            job_title=job_title.strip() or "Generalist",
            summary=summary,
            system_prompt=system_prompt,
            recommended_skills=skills,
        )

    def hire_agent(
        self,
        *,
        tenant_id: str,
        name: str,
        job_title: str,
        description: str,
        system_prompt: str,
        cv_text: str,
        skills: list[str],
        slack_channels: list[str] | None = None,
    ) -> int:
        return self.memory.create_workforce_agent(
            tenant_id=tenant_id,
            name=name,
            job_title=job_title,
            description=description,
            system_prompt=system_prompt,
            cv_text=cv_text,
            skills=skills,
            status="hired",
            slack_channels=slack_channels or [],
        )

    @staticmethod
    def build_slack_manifest(*, app_name: str, bot_display_name: str, request_url: str, redirect_urls: list[str] | None = None) -> dict[str, Any]:
        redirects = redirect_urls or []
        return {
            "display_information": {
                "name": app_name,
                "description": "HelmiesAI workforce agent",
                "background_color": "#111827",
            },
            "features": {
                "bot_user": {
                    "display_name": bot_display_name,
                    "always_online": True,
                }
            },
            "oauth_config": {
                "redirect_urls": redirects,
                "scopes": {
                    "bot": [
                        "app_mentions:read",
                        "channels:history",
                        "channels:read",
                        "chat:write",
                        "groups:history",
                        "im:history",
                        "im:read",
                        "im:write",
                        "mpim:history",
                        "users:read",
                    ]
                },
            },
            "settings": {
                "event_subscriptions": {
                    "request_url": request_url,
                    "bot_events": ["app_mention", "message.channels", "message.im"],
                },
                "org_deploy_enabled": False,
                "socket_mode_enabled": False,
                "token_rotation_enabled": True,
            },
        }

    def create_task(
        self,
        *,
        tenant_id: str,
        created_by: str,
        title: str,
        description: str,
        assignee_agent_id: int | None,
        collaborator_agent_ids: list[int] | None = None,
        priority: str = "medium",
    ) -> int:
        return self.memory.create_workforce_task(
            tenant_id=tenant_id,
            created_by=created_by,
            title=title,
            description=description,
            assignee_agent_id=assignee_agent_id,
            collaborator_agent_ids=collaborator_agent_ids or [],
            priority=priority,
            status="open",
        )

    def list_agents(self, tenant_id: str) -> list[dict[str, Any]]:
        return self.memory.list_workforce_agents(tenant_id)

    def list_tasks(self, tenant_id: str, status: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        return self.memory.list_workforce_tasks(tenant_id=tenant_id, status=status, limit=limit)

    def run_task(
        self,
        *,
        agent: HelmiesAgent,
        tenant_id: str,
        task_id: int,
        actor_user_id: str,
    ) -> dict[str, Any]:
        task = self.memory.get_workforce_task(tenant_id, task_id)
        if not task:
            raise ValueError("task not found")

        assignee_id = task.get("assignee_agent_id")
        assigned_agent = self.memory.get_workforce_agent(tenant_id, int(assignee_id)) if assignee_id else None
        collaborators: list[dict[str, Any]] = []
        for cid in task.get("collaborator_agent_ids") or []:
            c = self.memory.get_workforce_agent(tenant_id, int(cid))
            if c:
                collaborators.append(c)

        if assigned_agent:
            leader_block = (
                f"Lead agent: {assigned_agent.get('name')} ({assigned_agent.get('job_title')})\n"
                f"Role prompt: {assigned_agent.get('system_prompt')}\n"
                f"Skills: {', '.join(assigned_agent.get('skills', []))}\n"
            )
        else:
            leader_block = "Lead agent: Unassigned. Execute as general operations lead.\n"

        collab_lines = []
        for c in collaborators:
            collab_lines.append(
                f"- {c.get('name')} ({c.get('job_title')}): skills={', '.join(c.get('skills', []))}"
            )
        collab_block = "\n".join(collab_lines) if collab_lines else "- none"

        collaborator_notes: list[dict[str, Any]] = []
        for c in collaborators:
            c_prompt = (
                "You are a specialist collaborator in a HelmiesAI agent team.\n"
                f"Task title: {task.get('title')}\n"
                f"Task description: {task.get('description')}\n"
                f"Your role: {c.get('job_title')}\n"
                f"Your skills: {', '.join(c.get('skills', []))}\n"
                "Provide concise recommendations and risks from your specialty."
            )
            c_res = agent.chat(
                session_id=f"workforce-task-{task_id}-collab-{c.get('id')}",
                user_message=c_prompt,
                ctx=RequestContext(tenant_id=tenant_id, user_id=actor_user_id, roles=["admin"]),
            )
            collaborator_notes.append(
                {
                    "agent_id": c.get("id"),
                    "name": c.get("name"),
                    "job_title": c.get("job_title"),
                    "note": c_res.text,
                    "tools_executed": c_res.tools_executed,
                }
            )

        notes_block = "\n".join([f"- {n['name']} ({n['job_title']}): {n['note']}" for n in collaborator_notes]) or "- none"
        prompt = (
            "You are executing a workforce task for HelmiesAI.\n"
            f"Task title: {task.get('title')}\n"
            f"Task description: {task.get('description')}\n\n"
            f"{leader_block}\n"
            "Collaborating agents:\n"
            f"{collab_block}\n\n"
            "Collaborator findings:\n"
            f"{notes_block}\n\n"
            "Synthesize a final execution summary and concrete next actions."
        )

        self.memory.update_workforce_task(tenant_id=tenant_id, task_id=task_id, status="in_progress")
        res = agent.chat(
            session_id=f"workforce-task-{task_id}",
            user_message=prompt,
            ctx=RequestContext(tenant_id=tenant_id, user_id=actor_user_id, roles=["admin"]),
        )

        result = {
            "response": res.text,
            "tools_executed": res.tools_executed,
            "quality": res.quality,
            "assignee_agent_id": assignee_id,
            "collaborator_agent_ids": task.get("collaborator_agent_ids") or [],
            "collaborator_notes": collaborator_notes,
        }
        self.memory.update_workforce_task(tenant_id=tenant_id, task_id=task_id, status="completed", result=result)
        self.memory.log_audit(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            event_type="workforce_task_run",
            payload_json=json.dumps({"task_id": task_id, "assignee_agent_id": assignee_id}),
        )
        return result

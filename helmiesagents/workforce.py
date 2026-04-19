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
    "hr": ["hiring operations", "candidate screening", "policy communication"],
    "finance": ["budget analysis", "forecasting", "variance reporting"],
    "product": ["roadmapping", "product discovery", "stakeholder alignment"],
}

_DEFAULT_ROLE_PROMPTS: dict[str, str] = {
    "marketing": "You are a senior marketing strategist focused on measurable growth and clear messaging.",
    "sales": "You are a top-performing B2B account executive focused on conversion and relationship quality.",
    "developer": "You are a senior software engineer who ships reliable code with tests and clear tradeoff analysis.",
    "designer": "You are a product designer who balances usability, accessibility, and brand consistency.",
    "operations": "You are an operations lead focused on reliability, process clarity, and root-cause elimination.",
    "support": "You are a support specialist who resolves issues quickly and improves documentation quality.",
    "hr": "You are an HR lead focused on talent quality, process fairness, and fast hiring execution.",
    "finance": "You are a finance controller focused on forecasting accuracy, cash discipline, and clear reporting.",
    "product": "You are a product manager who turns strategy into execution with crisp prioritization and measurable outcomes.",
}


@dataclass
class WorkforceProfileSuggestion:
    suggested_name: str
    job_title: str
    summary: str
    system_prompt: str
    recommended_skills: list[str]
    confidence_score: float
    strengths: list[str]
    risk_flags: list[str]


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
        if any(k in jt for k in ["hr", "human resources", "recruit", "talent"]):
            return "hr"
        if any(k in jt for k in ["finance", "accounting", "controller", "cfo"]):
            return "finance"
        if any(k in jt for k in ["product manager", "product lead", "pm"]):
            return "product"
        return "operations"

    def suggest_profile(self, *, name: str | None, job_title: str, cv_text: str = "") -> WorkforceProfileSuggestion:
        role = self._normalize_role(job_title)
        base_prompt = _DEFAULT_ROLE_PROMPTS[role]
        skills = _DEFAULT_ROLE_SKILLS[role]

        cv_trimmed = (cv_text or "").strip()
        cv_lower = cv_trimmed.lower()
        cv_context = cv_trimmed[:1200] if cv_trimmed else "No CV provided."
        suggested_name = (name or f"{job_title.strip()} Agent").strip()

        role_keywords: dict[str, list[str]] = {
            "marketing": ["campaign", "seo", "growth", "brand", "funnel", "analytics"],
            "sales": ["quota", "pipeline", "prospecting", "crm", "closing", "negotiation"],
            "developer": ["python", "typescript", "api", "testing", "architecture", "ci/cd"],
            "designer": ["figma", "ux", "prototype", "design system", "accessibility"],
            "operations": ["incident", "on-call", "automation", "runbook", "sre"],
            "support": ["ticket", "sla", "customer", "kb", "troubleshoot"],
            "hr": ["hiring", "talent", "interview", "onboarding", "policy"],
            "finance": ["budget", "forecast", "variance", "cashflow", "p&l"],
            "product": ["roadmap", "discovery", "prioritization", "kpi", "stakeholder"],
        }
        matched = [k for k in role_keywords.get(role, []) if k in cv_lower]

        strengths = [f"CV mentions relevant keyword: {k}" for k in matched[:6]]
        risk_flags: list[str] = []
        if not cv_trimmed:
            risk_flags.append("No CV text provided; recommendation confidence reduced")
        if cv_trimmed and len(cv_trimmed) < 120:
            risk_flags.append("Very short CV text; limited evidence for seniority")
        if cv_trimmed and len(matched) <= 1:
            risk_flags.append("Few role-specific signals detected in CV")

        confidence = 0.45
        confidence += min(0.35, 0.05 * len(matched))
        if cv_trimmed and len(cv_trimmed) > 300:
            confidence += 0.1
        if risk_flags:
            confidence -= min(0.2, 0.05 * len(risk_flags))
        confidence = max(0.1, min(0.98, confidence))

        system_prompt = (
            f"{base_prompt}\n"
            "Operate as a reliable teammate in a multi-agent company setup.\n"
            "Coordinate with peer agents, keep outputs concise, and escalate risks early.\n"
            "You must collaborate asynchronously through the workforce bus and publish concise handoff notes.\n"
            f"Candidate context:\n{cv_context}"
        )
        summary = f"Suggested profile for {job_title} based on role heuristics, CV signals, and team-collaboration requirements."

        return WorkforceProfileSuggestion(
            suggested_name=suggested_name,
            job_title=job_title.strip() or "Generalist",
            summary=summary,
            system_prompt=system_prompt,
            recommended_skills=skills,
            confidence_score=round(confidence, 3),
            strengths=strengths,
            risk_flags=risk_flags,
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
        model_provider: str | None = None,
        model_name: str | None = None,
        model_base_url: str | None = None,
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
            model_provider=model_provider,
            model_name=model_name,
            model_base_url=model_base_url,
        )

    @staticmethod
    def build_slack_manifest(
        *,
        app_name: str,
        bot_display_name: str,
        request_url: str,
        redirect_urls: list[str] | None = None,
        command_name: str = "/helmies",
    ) -> dict[str, Any]:
        redirects = redirect_urls or []
        command = (command_name or "/helmies").strip() or "/helmies"
        if not command.startswith("/"):
            command = f"/{command}"

        return {
            "display_information": {
                "name": app_name,
                "description": "HelmiesAI workforce agent",
                "background_color": "#111827",
            },
            "features": {
                "app_home": {
                    "home_tab_enabled": True,
                    "messages_tab_enabled": True,
                    "messages_tab_read_only_enabled": False,
                },
                "bot_user": {
                    "display_name": bot_display_name,
                    "always_online": True,
                },
                "slash_commands": [
                    {
                        "command": command,
                        "url": request_url,
                        "description": "Route tasks to HelmiesAI workforce agents",
                        "usage_hint": "ask <agent> <task>",
                        "should_escape": False,
                    }
                ],
            },
            "oauth_config": {
                "redirect_urls": redirects,
                "scopes": {
                    "bot": [
                        "app_mentions:read",
                        "channels:history",
                        "channels:read",
                        "chat:write",
                        "chat:write.public",
                        "commands",
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
                "interactivity": {
                    "is_enabled": True,
                    "request_url": request_url,
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

    @staticmethod
    def _apply_agent_model_overrides(prompt: str, agent_row: dict[str, Any] | None) -> str:
        if not agent_row:
            return prompt

        provider = (agent_row.get("model_provider") or "").strip()
        model_name = (agent_row.get("model_name") or "").strip()
        base_url = (agent_row.get("model_base_url") or "").strip()

        if not provider and not model_name and not base_url:
            return prompt

        lines = ["Execution model preferences for this hired agent persona:"]
        if provider:
            lines.append(f"- provider: {provider}")
        if model_name:
            lines.append(f"- model: {model_name}")
        if base_url:
            lines.append(f"- base_url: {base_url}")
        lines.append(
            "Treat these as strict execution constraints when producing your response and planning tool usage."
        )
        return prompt + "\n\n" + "\n".join(lines)

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

        thread_id = f"wf-task-{task_id}"
        self.memory.add_workforce_bus_message(
            tenant_id=tenant_id,
            thread_id=thread_id,
            from_agent_id=None,
            to_agent_id=task.get("assignee_agent_id"),
            message=f"Task opened: {task.get('title')} — {task.get('description')}",
            metadata={"kind": "task_open", "task_id": task_id},
        )

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
            c_prompt = self._apply_agent_model_overrides(c_prompt, c)
            c_res = agent.chat(
                session_id=f"workforce-task-{task_id}-collab-{c.get('id')}",
                user_message=c_prompt,
                ctx=RequestContext(tenant_id=tenant_id, user_id=actor_user_id, roles=["admin"]),
            )
            note_payload = {
                "agent_id": c.get("id"),
                "name": c.get("name"),
                "job_title": c.get("job_title"),
                "note": c_res.text,
                "tools_executed": c_res.tools_executed,
            }
            collaborator_notes.append(note_payload)
            self.memory.add_workforce_bus_message(
                tenant_id=tenant_id,
                thread_id=thread_id,
                from_agent_id=int(c.get("id")),
                to_agent_id=assignee_id,
                message=c_res.text,
                metadata={"kind": "collaborator_note", "task_id": task_id, "agent_name": c.get("name")},
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

        prompt = self._apply_agent_model_overrides(prompt, assigned_agent)

        self.memory.update_workforce_task(tenant_id=tenant_id, task_id=task_id, status="in_progress")
        res = agent.chat(
            session_id=f"workforce-task-{task_id}",
            user_message=prompt,
            ctx=RequestContext(tenant_id=tenant_id, user_id=actor_user_id, roles=["admin"]),
        )

        self.memory.add_workforce_bus_message(
            tenant_id=tenant_id,
            thread_id=thread_id,
            from_agent_id=assignee_id,
            to_agent_id=None,
            message=res.text,
            metadata={"kind": "assignee_final", "task_id": task_id},
        )

        bus_messages = self.memory.list_workforce_bus_messages(tenant_id=tenant_id, thread_id=thread_id, limit=500)
        result = {
            "response": res.text,
            "tools_executed": res.tools_executed,
            "quality": res.quality,
            "assignee_agent_id": assignee_id,
            "collaborator_agent_ids": task.get("collaborator_agent_ids") or [],
            "collaborator_notes": collaborator_notes,
            "thread_id": thread_id,
            "bus_messages": bus_messages,
        }
        self.memory.update_workforce_task(tenant_id=tenant_id, task_id=task_id, status="completed", result=result)
        self.memory.mark_workforce_bus_read(tenant_id=tenant_id, thread_id=thread_id, to_agent_id=assignee_id)
        self.memory.log_audit(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            event_type="workforce_task_run",
            payload_json=json.dumps({"task_id": task_id, "assignee_agent_id": assignee_id, "thread_id": thread_id}),
        )
        return result

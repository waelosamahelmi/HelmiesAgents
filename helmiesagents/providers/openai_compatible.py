from __future__ import annotations

from collections.abc import Iterable
import json

import httpx


class OpenAICompatibleProvider:
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.name = "openai-compatible"
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def _payload(self, system_prompt: str, user_prompt: str, model_override: str | None = None, *, stream: bool = False) -> dict:
        return {
            "model": model_override or self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "stream": stream,
        }

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model_override: str | None = None,
        base_url_override: str | None = None,
    ) -> str:
        effective_base_url = (base_url_override or self.base_url).rstrip("/")
        url = f"{effective_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = self._payload(system_prompt, user_prompt, model_override=model_override, stream=False)
        with httpx.Client(timeout=90) as client:
            res = client.post(url, headers=headers, json=payload)
            res.raise_for_status()
            data = res.json()
        return data["choices"][0]["message"]["content"]

    def stream_generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model_override: str | None = None,
        base_url_override: str | None = None,
    ) -> Iterable[str]:
        effective_base_url = (base_url_override or self.base_url).rstrip("/")
        url = f"{effective_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = self._payload(system_prompt, user_prompt, model_override=model_override, stream=True)

        with httpx.Client(timeout=90) as client:
            with client.stream("POST", url, headers=headers, json=payload) as res:
                res.raise_for_status()
                for line in res.iter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data = line[6:]
                    else:
                        data = line

                    if data.strip() == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data)
                    except Exception:
                        continue

                    delta = (
                        chunk.get("choices", [{}])[0]
                        .get("delta", {})
                        .get("content")
                    )
                    if delta:
                        yield delta

from __future__ import annotations

import httpx


class OpenAICompatibleProvider:
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.name = "openai-compatible"
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def generate(self, system_prompt: str, user_prompt: str, model_override: str | None = None) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_override or self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        with httpx.Client(timeout=90) as client:
            res = client.post(url, headers=headers, json=payload)
            res.raise_for_status()
            data = res.json()
        return data["choices"][0]["message"]["content"]

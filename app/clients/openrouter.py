from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx


class OpenRouterAPIError(RuntimeError):
    pass


class OpenRouterClient:
    def __init__(self, base_url: str, api_key: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(5)

    async def get_embeddings(self, texts: list[str], model: str) -> list[list[float]]:
        data = await self._request("POST", "/embeddings", json={"input": texts, "model": model})
        items = sorted(data.get("data", []), key=lambda d: d.get("index", 0))
        return [item["embedding"] for item in items]

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 2000,
    ) -> str:
        data = await self._request(
            "POST",
            "/chat/completions",
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        content = data["choices"][0]["message"]["content"]
        return content

    def parse_json_response(self, text: str) -> dict[str, Any]:
        cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`")
        return json.loads(cleaned)

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://perenoska.app",
            "X-Title": "Perenoska",
        }
        async with self._semaphore:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method,
                    f"{self.base_url}{path}",
                    headers=headers,
                    **kwargs,
                )
        if response.status_code >= 400:
            raise OpenRouterAPIError(
                f"OpenRouter API error {response.status_code}: {response.text}"
            )
        return response.json()

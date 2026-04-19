"""
Unified LLM client with role-based model routing.

  Coordinator / complex reasoning  → GPT-4o-mini
  Sales / Inventory / Production   → DeepSeek-V3
  Market Signal                    → DeepSeek-V3
"""

from __future__ import annotations
import os
from typing import Any
from dotenv import load_dotenv

load_dotenv()

_ROLE_TO_MODEL: dict[str, str] = {
    "coordinator": "gpt-4o-mini",
    "editor": "gpt-4o-mini",
    "sales_north": "deepseek-chat",
    "sales_east": "deepseek-chat",
    "sales_south": "deepseek-chat",
    "inventory": "deepseek-chat",
    "production": "deepseek-chat",
    "market_signal": "deepseek-chat",
}

_OPENAI_MODELS = {"gpt-4o-mini", "gpt-4o", "gpt-4-turbo"}
_DEEPSEEK_MODELS = {"deepseek-chat", "deepseek-reasoner"}


def _make_client(model: str):
    from openai import OpenAI  # lazy import

    if model in _DEEPSEEK_MODELS:
        return OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        ), model
    else:
        return OpenAI(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        ), model


class LLMClient:
    """
    Role-aware LLM wrapper.  Usage:

        client = LLMClient(role="coordinator")
        reply = client.chat([{"role": "user", "content": "..."}])
    """

    def __init__(self, role: str, temperature: float = 0.2):
        self.role = role
        self.temperature = temperature
        self.model = _ROLE_TO_MODEL.get(role, "deepseek-chat")
        self._client, self._model = _make_client(self.model)

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        response_format: dict | None = None,
        max_tokens: int = 2048,
    ) -> str:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        resp = self._client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

    def chat_json(self, messages: list[dict[str, str]], **kwargs) -> str:
        return self.chat(
            messages,
            response_format={"type": "json_object"},
            **kwargs,
        )


def get_client(role: str, temperature: float = 0.2) -> LLMClient:
    return LLMClient(role=role, temperature=temperature)

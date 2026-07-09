from collections.abc import Iterator
import json
from typing import Any

from app.config import settings


class LLMUnavailableError(RuntimeError):
    pass


class GroqClient:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else settings.groq_api_key
        self.model = model or settings.groq_model
        self._client = None

    def complete(self, messages: list[dict[str, str]], temperature: float = 0.1) -> str:
        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""

    def complete_json(self, messages: list[dict[str, str]], temperature: float = 0.0) -> dict[str, Any]:
        content = self.complete(messages=messages, temperature=temperature)
        return parse_json_object(content)

    def stream(self, messages: list[dict[str, str]], temperature: float = 0.1) -> Iterator[str]:
        client = self._get_client()
        stream = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    def _get_client(self):
        if not self.api_key:
            raise LLMUnavailableError("GROQ_API_KEY is not configured.")
        if self._client is None:
            try:
                from groq import Groq
            except ImportError as exc:
                raise LLMUnavailableError("The groq package is not installed.") from exc
            self._client = Groq(api_key=self.api_key)
        return self._client


def parse_json_object(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            return json.loads(content[start : end + 1])
        raise


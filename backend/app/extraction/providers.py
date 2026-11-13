"""LLM providers behind one interface.

Each provider only has to turn (system prompt, user prompt, JSON Schema) into a JSON
string. Parsing, validation, retries, and fallback live in `extract()`, so every
provider is held to exactly the same rules. SDKs are imported lazily so tests and
installs without a given SDK still work.
"""

import json
import logging
import os
from typing import Protocol

from pydantic import ValidationError

from app.extraction.prompt import SYSTEM_PROMPT, ExtractionContext, build_user_prompt
from app.extraction.schema import JSON_SCHEMA, ExtractionResult

log = logging.getLogger(__name__)

MAX_OUTPUT_TOKENS = 8000


class ProviderError(Exception):
    """A provider could not produce a valid result."""


class Provider(Protocol):
    name: str

    def complete_json(self, system: str, user: str, schema: dict) -> str: ...


def _require_env(var: str) -> str:
    value = os.getenv(var)
    if not value:
        raise ProviderError(f"{var} is not set")
    return value


class ClaudeProvider:
    """Anthropic. Uses a forced tool call so the reply must match the schema."""

    name = "claude"

    def __init__(self, client=None, model: str | None = None):
        self.model = model or _require_env("CLAUDE_MODEL")
        if client is None:
            import anthropic

            client = anthropic.Anthropic(api_key=_require_env("ANTHROPIC_API_KEY"))
        self.client = client

    def complete_json(self, system: str, user: str, schema: dict) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=MAX_OUTPUT_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
            tools=[{"name": "record_deadlines", "description": "Record the extracted deadlines.", "input_schema": schema}],
            tool_choice={"type": "tool", "name": "record_deadlines"},
        )
        for block in response.content:
            if getattr(block, "type", None) == "tool_use":
                return json.dumps(block.input)
        raise ProviderError("Claude returned no tool call")


class OpenAIProvider:
    """OpenAI. Uses strict JSON Schema structured output."""

    name = "openai"

    def __init__(self, client=None, model: str | None = None):
        self.model = model or _require_env("OPENAI_MODEL")
        if client is None:
            import openai

            client = openai.OpenAI(api_key=_require_env("OPENAI_API_KEY"))
        self.client = client

    def complete_json(self, system: str, user: str, schema: dict) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "deadlines", "schema": schema, "strict": True},
            },
        )
        message = response.choices[0].message
        if getattr(message, "refusal", None):
            raise ProviderError(f"OpenAI refused: {message.refusal}")
        if not message.content:
            raise ProviderError("OpenAI returned an empty message")
        return message.content


class GeminiProvider:
    """Google Gemini. Uses JSON mode with a JSON Schema."""

    name = "gemini"

    def __init__(self, client=None, model: str | None = None):
        self.model = model or _require_env("GEMINI_MODEL")
        if client is None:
            from google import genai

            client = genai.Client(api_key=_require_env("GEMINI_API_KEY"))
        self.client = client

    def complete_json(self, system: str, user: str, schema: dict) -> str:
        from google.genai import types

        response = self.client.models.generate_content(
            model=self.model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_json_schema=schema,
            ),
        )
        if not response.text:
            raise ProviderError("Gemini returned no text")
        return response.text


PROVIDERS = {"claude": ClaudeProvider, "openai": OpenAIProvider, "gemini": GeminiProvider}


def make_provider(name: str) -> Provider:
    try:
        return PROVIDERS[name]()
    except KeyError:
        raise ProviderError(f"unknown provider: {name}") from None


def provider_order(preferred: str | None = None) -> list[str]:
    """LLM_PROVIDERS=claude,openai,gemini sets the fallback order. `preferred` goes first."""
    order = [p.strip() for p in os.getenv("LLM_PROVIDERS", "claude,openai,gemini").split(",") if p.strip()]
    if preferred:
        order = [preferred] + [p for p in order if p != preferred]
    return order


def _run_one(provider: Provider, system: str, user: str) -> ExtractionResult:
    """One provider, one retry if the JSON does not validate."""
    last_error: Exception | None = None
    for _ in range(2):
        raw = provider.complete_json(system, user, JSON_SCHEMA)
        try:
            return ExtractionResult.model_validate_json(raw)
        except ValidationError as exc:
            last_error = exc
    raise ProviderError(f"{provider.name} returned invalid JSON twice: {last_error}")


def extract(
    syllabus_text: str,
    ctx: ExtractionContext,
    providers: list[Provider] | None = None,
    preferred: str | None = None,
) -> tuple[ExtractionResult, str]:
    """Try providers in order. Returns the result and the name of the provider that produced it."""
    user = build_user_prompt(syllabus_text, ctx)
    errors: list[str] = []
    if providers is None:
        providers = []
        for name in provider_order(preferred):
            try:
                providers.append(make_provider(name))
            except ProviderError as exc:
                errors.append(f"{name}: {exc}")
    for provider in providers:
        try:
            return _run_one(provider, SYSTEM_PROMPT, user), provider.name
        except Exception as exc:  # network errors, refusals, bad JSON: fall through to the next one
            log.warning("provider %s failed: %s", provider.name, exc)
            errors.append(f"{provider.name}: {exc}")
    raise ProviderError("all providers failed; " + "; ".join(errors))

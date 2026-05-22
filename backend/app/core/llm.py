"""LLM client wrapper using OpenAI-compatible API (DeepSeek, Claude, GPT via relay)."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.core.config import settings

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)

# Provider registry — one cached client per provider.
_clients: dict[str, AsyncOpenAI] = {}

PROVIDER_CONFIGS: dict[str, dict[str, str]] = {
    "deepseek": {
        "api_key_field": "llm_api_key",
        "base_url_field": "llm_base_url",
        "model_field": "llm_model",
    },
    "claude": {
        "api_key_field": "relay_claude_api_key",
        "base_url_field": "relay_base_url",
        "model_field": "relay_claude_model",
    },
    "gpt": {
        "api_key_field": "relay_gpt_api_key",
        "base_url_field": "relay_base_url",
        "model_field": "relay_gpt_model",
    },
}

FALLBACK_PROVIDER = "deepseek"


def get_client(provider: str | None = None) -> AsyncOpenAI:
    """Return a cached AsyncOpenAI client for the given provider."""
    provider = provider or settings.default_llm_provider
    if provider in _clients:
        return _clients[provider]

    cfg = PROVIDER_CONFIGS.get(provider)
    if not cfg:
        raise ValueError(f"Unknown LLM provider: {provider!r}. Choose from {list(PROVIDER_CONFIGS)}")

    api_key = getattr(settings, cfg["api_key_field"])
    base_url = getattr(settings, cfg["base_url_field"])

    if not api_key:
        raise ValueError(
            f"LLM provider '{provider}' has no API key configured "
            f"(env var: {cfg['api_key_field'].upper()})"
        )

    client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=60.0)
    _clients[provider] = client
    return client


def _model_for(provider: str | None) -> str:
    """Resolve the model name for a provider."""
    provider = provider or settings.default_llm_provider
    cfg = PROVIDER_CONFIGS[provider]
    return getattr(settings, cfg["model_field"])


async def call_llm(
    system: str,
    user_message: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> str:
    """Single-turn LLM call. Falls back to FALLBACK_PROVIDER on failure if using a relay."""
    provider = provider or settings.default_llm_provider
    try:
        client = get_client(provider)
        resp = await client.chat.completions.create(
            model=model or _model_for(provider),
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
        )
        return resp.choices[0].message.content or ""
    except Exception as exc:
        if provider != FALLBACK_PROVIDER:
            logger.warning("Provider '%s' failed (%s), falling back to '%s'", provider, exc, FALLBACK_PROVIDER)
            client = get_client(FALLBACK_PROVIDER)
            resp = await client.chat.completions.create(
                model=model or _model_for(FALLBACK_PROVIDER),
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_message},
                ],
            )
            return resp.choices[0].message.content or ""
        raise


def _fix_stringified_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Some models return list/dict fields as JSON strings. Parse them back."""
    for key, value in data.items():
        if isinstance(value, str):
            if value == "null":
                data[key] = None
            elif value.startswith(("[", "{")):
                try:
                    data[key] = json.loads(value)
                except (json.JSONDecodeError, ValueError):
                    pass
        elif isinstance(value, dict):
            data[key] = _fix_stringified_fields(value)
    return data


def _robust_json_loads(s: str) -> dict[str, Any]:
    """Parse JSON robustly — handle trailing garbage from some models."""
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    # Try to find the outermost {} or [] and parse just that
    start = s.find("{")
    if start == -1:
        start = s.find("[")
    if start == -1:
        raise ValueError(f"No JSON object found in: {s[:200]}")
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(s)):
        c = s[i]
        if escape:
            escape = False
            continue
        if c == "\\":
            escape = True
            continue
        if c == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c in "{[":
            depth += 1
        elif c in "}]":
            depth -= 1
            if depth == 0:
                return json.loads(s[start:i + 1])
    raise ValueError(f"Unbalanced JSON in: {s[:200]}")


async def call_llm_structured(
    system: str,
    user_message: str,
    output_schema: type[T],
    *,
    provider: str | None = None,
    model: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.2,
) -> T:
    """Get structured output by forcing a function call matching the Pydantic schema.

    Falls back to FALLBACK_PROVIDER on failure if using a relay provider.
    """
    provider = provider or settings.default_llm_provider
    schema = output_schema.model_json_schema()
    func_name = f"output_{output_schema.__name__}"
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_message},
    ]
    tools = [{
        "type": "function",
        "function": {
            "name": func_name,
            "description": f"Output structured data as {output_schema.__name__}",
            "parameters": schema,
        },
    }]
    tool_choice = {"type": "function", "function": {"name": func_name}}

    try:
        client = get_client(provider)
        resp = await client.chat.completions.create(
            model=model or _model_for(provider),
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
        )
    except Exception as exc:
        if provider != FALLBACK_PROVIDER:
            logger.warning("Provider '%s' structured call failed (%s), falling back to '%s'", provider, exc, FALLBACK_PROVIDER)
            client = get_client(FALLBACK_PROVIDER)
            resp = await client.chat.completions.create(
                model=model or _model_for(FALLBACK_PROVIDER),
                max_tokens=max_tokens,
                temperature=temperature,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
            )
        else:
            raise

    msg = resp.choices[0].message
    if msg.tool_calls:
        args_str = msg.tool_calls[0].function.arguments
        data = _robust_json_loads(args_str)
        data = _fix_stringified_fields(data)
        return output_schema.model_validate(data)

    # Fallback: try parsing the text content as JSON
    if msg.content:
        data = _robust_json_loads(msg.content)
        data = _fix_stringified_fields(data)
        return output_schema.model_validate(data)

    raise ValueError(f"LLM did not return expected function call '{func_name}'")


async def call_llm_chat(
    system: str,
    messages: list[dict[str, Any]],
    *,
    provider: str | None = None,
    model: str | None = None,
    max_tokens: int = 2048,
    temperature: float = 0.5,
) -> str:
    provider = provider or settings.default_llm_provider
    full_messages = [{"role": "system", "content": system}] + messages
    try:
        client = get_client(provider)
        resp = await client.chat.completions.create(
            model=model or _model_for(provider),
            max_tokens=max_tokens,
            temperature=temperature,
            messages=full_messages,
        )
        return resp.choices[0].message.content or ""
    except Exception as exc:
        if provider != FALLBACK_PROVIDER:
            logger.warning("Provider '%s' chat failed (%s), falling back to '%s'", provider, exc, FALLBACK_PROVIDER)
            client = get_client(FALLBACK_PROVIDER)
            resp = await client.chat.completions.create(
                model=model or _model_for(FALLBACK_PROVIDER),
                max_tokens=max_tokens,
                temperature=temperature,
                messages=full_messages,
            )
            return resp.choices[0].message.content or ""
        raise


async def stream_llm_chat(
    system: str,
    messages: list[dict[str, Any]],
    *,
    provider: str | None = None,
    model: str | None = None,
    max_tokens: int = 2048,
    temperature: float = 0.5,
) -> AsyncIterator[str]:
    """Yield content chunks as the LLM generates them.

    Caller is responsible for accumulating the full text if needed for storage.
    Note: streaming does NOT fall back on failure — the caller handles errors.
    """
    provider = provider or settings.default_llm_provider
    client = get_client(provider)
    full_messages = [{"role": "system", "content": system}] + messages
    stream = await client.chat.completions.create(
        model=model or _model_for(provider),
        max_tokens=max_tokens,
        temperature=temperature,
        messages=full_messages,
        stream=True,
    )
    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content


async def stream_llm(
    system: str,
    user_message: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> AsyncIterator[str]:
    """Single-turn streaming wrapper."""
    async for chunk in stream_llm_chat(
        system=system,
        messages=[{"role": "user", "content": user_message}],
        provider=provider,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    ):
        yield chunk

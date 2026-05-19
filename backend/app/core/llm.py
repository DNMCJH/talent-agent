"""LLM client wrapper using OpenAI-compatible API (DeepSeek, OpenAI, etc.)."""

from __future__ import annotations

import json
from typing import Any, TypeVar

from openai import OpenAI
from pydantic import BaseModel

from app.core.config import settings

T = TypeVar("T", bound=BaseModel)

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    return _client


async def call_llm(
    system: str,
    user_message: str,
    *,
    model: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> str:
    client = get_client()
    resp = client.chat.completions.create(
        model=model or settings.llm_model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
    )
    return resp.choices[0].message.content or ""


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
    model: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.2,
) -> T:
    """Get structured output by forcing a function call matching the Pydantic schema."""
    client = get_client()
    schema = output_schema.model_json_schema()
    func_name = f"output_{output_schema.__name__}"

    resp = client.chat.completions.create(
        model=model or settings.llm_model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
        tools=[{
            "type": "function",
            "function": {
                "name": func_name,
                "description": f"Output structured data as {output_schema.__name__}",
                "parameters": schema,
            },
        }],
        tool_choice={"type": "function", "function": {"name": func_name}},
    )

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
    model: str | None = None,
    max_tokens: int = 2048,
    temperature: float = 0.5,
) -> str:
    client = get_client()
    full_messages = [{"role": "system", "content": system}] + messages
    resp = client.chat.completions.create(
        model=model or settings.llm_model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=full_messages,
    )
    return resp.choices[0].message.content or ""

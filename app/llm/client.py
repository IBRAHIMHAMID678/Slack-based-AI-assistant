"""Unified LLM client with provider failover, retry backoff, and mock execution.

Routes tasks to primary (Groq) or fallback (OpenRouter) providers with
exponential backoff, JSON schema validation, and deterministic mock mode.
"""

import json
import random
import time
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.config import settings
from app.errors import AllProvidersFailed, LLMProviderError, SchemaValidationError
from app.llm.routing import ROUTING_TABLE, TaskRoute
from app.logging import get_logger

logger = get_logger("llm_client")


def load_fixture_response(task: str) -> dict[str, Any]:
    """Load deterministic JSON response from tests/fixtures/llm/ for mock mode."""
    fixture_dir = Path(settings.base_dir) / "tests" / "fixtures" / "llm"
    fixture_map = {
        "intake_extract": fixture_dir / "intake_brightline.json",
        "writer_section": fixture_dir / "writer_brightline.json",
        "critic_review": fixture_dir / "critic_pass.json",
        "section_router": fixture_dir / "writer_brightline.json",
        "query_rewrite": fixture_dir / "intake_brightline.json",
    }
    file_path = fixture_map.get(task, fixture_dir / "intake_brightline.json")
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"status": "mock_success", "task": task}


async def call_groq(
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    api_key: str,
) -> str:
    """Execute raw chat completion via Groq REST API."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            raise LLMProviderError("groq", response.status_code, response.text)
        data = response.json()
        return data["choices"][0]["message"]["content"]


async def call_openrouter(
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    api_key: str,
) -> str:
    """Execute raw chat completion via OpenRouter REST API."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            raise LLMProviderError("openrouter", response.status_code, response.text)
        data = response.json()
        return data["choices"][0]["message"]["content"]


async def execute_with_backoff(
    provider: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
) -> str:
    """Execute provider call with 3 retry attempts and exponential backoff."""
    delays = [1.0, 2.0, 4.0]
    api_key = settings.GROQ_API_KEY if provider == "groq" else settings.OPENROUTER_API_KEY

    for attempt, base_delay in enumerate(delays, start=1):
        try:
            if provider == "groq":
                return await call_groq(model, messages, temperature, api_key)
            else:
                return await call_openrouter(model, messages, temperature, api_key)
        except Exception as exc:
            jitter = random.uniform(0.1, 0.5)
            delay = base_delay + jitter
            logger.warning(
                "llm_provider_retry",
                provider=provider,
                model=model,
                attempt=attempt,
                error=str(exc),
                backoff_seconds=round(delay, 2),
            )
            if attempt == len(delays):
                raise
            time.sleep(delay)
    raise AllProvidersFailed(f"Provider {provider} failed all retry attempts.")


async def complete(
    task: str,
    messages: list[dict[str, str]],
    schema: type[BaseModel] | None = None,
) -> Any:
    """Execute model routing, failover, JSON decoding, and Pydantic validation."""
    if settings.is_mock_mode:
        raw_dict = load_fixture_response(task)
        if schema:
            return schema.model_validate(raw_dict)
        return raw_dict

    route: TaskRoute = ROUTING_TABLE.get(
        task,
        ROUTING_TABLE["intake_extract"],
    )

    content_str = ""
    try:
        content_str = await execute_with_backoff(
            provider=route.primary_provider,
            model=route.primary_model,
            messages=messages,
            temperature=route.temperature,
        )
    except Exception as exc:
        logger.warning(
            "provider_failover",
            primary=route.primary_provider,
            fallback=route.fallback_provider,
            error=str(exc),
        )
        try:
            content_str = await execute_with_backoff(
                provider=route.fallback_provider,
                model=route.fallback_model,
                messages=messages,
                temperature=route.temperature,
            )
        except Exception as failover_exc:
            logger.error("all_providers_exhausted", error=str(failover_exc))
            raise AllProvidersFailed("All configured LLM providers in failover chain failed.")

    # Parse and validate JSON
    try:
        parsed_json = json.loads(content_str)
        if schema:
            return schema.model_validate(parsed_json)
        return parsed_json
    except (json.JSONDecodeError, ValidationError) as parse_exc:
        logger.warning("schema_validation_error_repompting", error=str(parse_exc))
        # Re-prompt once with the exact error message
        repair_messages = list(messages) + [
            {"role": "assistant", "content": content_str},
            {
                "role": "user",
                "content": f"The response was invalid JSON: {parse_exc}. Return valid JSON only.",
            },
        ]
        repaired_content = await execute_with_backoff(
            provider=route.primary_provider,
            model=route.primary_model,
            messages=repair_messages,
            temperature=0.1,
        )
        try:
            repaired_json = json.loads(repaired_content)
            if schema:
                return schema.model_validate(repaired_json)
            return repaired_json
        except Exception as final_exc:
            raise SchemaValidationError(f"Failed schema validation after reprompt: {final_exc}")

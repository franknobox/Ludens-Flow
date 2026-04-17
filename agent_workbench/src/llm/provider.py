from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional


@dataclass
class LLMConfig:
    provider: str
    model: str
    api_key: str
    base_url: Optional[str] = None
    temperature: float = 0.2


def load_config() -> LLMConfig:
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL") or None
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.2"))

    if not api_key:
        raise RuntimeError("Missing env var: LLM_API_KEY")

    return LLMConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
    )


def generate(
    system: str,
    user: str | list,
    cfg: LLMConfig,
    history: Optional[list] = None,
    tools: Optional[list] = None,
) -> Any:
    """
    Unified call entrypoint. Future provider swaps should only touch this file.
    """
    if cfg.provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url, timeout=120.0)

        messages: List[Dict[str, Any]] = [{"role": "system", "content": system}]
        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": user})

        kwargs = {
            "model": cfg.model,
            "messages": messages,
        }

        if tools:
            kwargs["tools"] = tools

        if cfg.temperature is not None and not any(
            marker in cfg.model.lower() for marker in ["k2.5", "o1", "o3", "reasoning"]
        ):
            kwargs["temperature"] = cfg.temperature

        try:
            resp = client.chat.completions.create(**kwargs)
        except Exception as e:
            err_msg = str(e).lower()
            if "temperature" in err_msg or "top_p" in err_msg:
                kwargs.pop("temperature", None)
                kwargs.pop("top_p", None)
                resp = client.chat.completions.create(**kwargs)
            else:
                raise e

        message = resp.choices[0].message

        if hasattr(message, "tool_calls") and message.tool_calls:
            return message

        return (message.content or "").strip()

    raise RuntimeError(f"Unsupported LLM_PROVIDER: {cfg.provider}")


def generate_stream(
    system: str,
    user: str | list,
    cfg: LLMConfig,
    history: Optional[list] = None,
) -> Iterator[str]:
    """
    Streaming text entrypoint for plain assistant replies.
    Tool-calling is intentionally excluded from this minimal streaming path.
    """
    if cfg.provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url, timeout=120.0)

        messages: List[Dict[str, Any]] = [{"role": "system", "content": system}]
        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": user})

        kwargs = {
            "model": cfg.model,
            "messages": messages,
            "stream": True,
        }

        if cfg.temperature is not None and not any(
            marker in cfg.model.lower() for marker in ["k2.5", "o1", "o3", "reasoning"]
        ):
            kwargs["temperature"] = cfg.temperature

        try:
            stream = client.chat.completions.create(**kwargs)
        except Exception as e:
            err_msg = str(e).lower()
            if "temperature" in err_msg or "top_p" in err_msg:
                kwargs.pop("temperature", None)
                kwargs.pop("top_p", None)
                stream = client.chat.completions.create(**kwargs)
            else:
                raise e

        for chunk in stream:
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            text = getattr(delta, "content", None)
            if text:
                yield text
        return

    raise RuntimeError(f"Unsupported LLM_PROVIDER: {cfg.provider}")

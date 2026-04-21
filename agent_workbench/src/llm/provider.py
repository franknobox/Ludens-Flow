"""
文件功能：统一封装 LLM provider 配置、请求生成与流式输出调用。
核心内容：支持多种 OpenAI 兼容 provider 的默认配置、密钥解析和容错处理。
核心内容：提供 build_config/load_config/generate/generate_stream 四类基础能力。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional


@dataclass
class LLMConfig:
    provider: str
    model: str
    api_key: Optional[str]
    base_url: Optional[str] = None
    temperature: float = 0.2


_OPENAI_COMPATIBLE_PROVIDERS = {
    "openai",
    "openai_compatible",
    "openrouter",
    "deepseek",
    "ollama",
    "groq",
    "together",
    "xai",
}


def _provider_requires_api_key(provider: str) -> bool:
    return provider not in {"ollama"}


def _provider_default_base_url(provider: str) -> Optional[str]:
    if provider == "ollama":
        return "http://localhost:11434/v1"
    if provider == "openrouter":
        return "https://openrouter.ai/api/v1"
    if provider == "deepseek":
        return "https://api.deepseek.com/v1"
    if provider in {"groq", "together", "xai"}:
        return None
    return None


def _provider_key_env_candidates(provider: str) -> List[str]:
    mapping = {
        "openai": ["OPENAI_API_KEY", "LLM_API_KEY"],
        "openai_compatible": ["LLM_API_KEY"],
        "openrouter": ["OPENROUTER_API_KEY", "LLM_API_KEY"],
        "deepseek": ["DEEPSEEK_API_KEY", "LLM_API_KEY"],
        "ollama": ["OLLAMA_API_KEY", "LLM_API_KEY"],
        "groq": ["GROQ_API_KEY", "LLM_API_KEY"],
        "together": ["TOGETHER_API_KEY", "LLM_API_KEY"],
        "xai": ["XAI_API_KEY", "LLM_API_KEY"],
    }
    return mapping.get(provider, ["LLM_API_KEY"])


def _resolve_api_key(provider: str, explicit: Optional[str] = None) -> Optional[str]:
    if explicit:
        return explicit
    for env_key in _provider_key_env_candidates(provider):
        value = (os.getenv(env_key) or "").strip()
        if value:
            return value
    return None


def _coerce_temperature(value: Any, default: float = 0.2) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_config(
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: Optional[float] = None,
    strict: bool = True,
) -> LLMConfig:
    resolved_provider = (provider or os.getenv("LLM_PROVIDER", "openai")).strip().lower()
    resolved_model = (model or os.getenv("LLM_MODEL", "gpt-4o-mini")).strip()
    resolved_base_url = (
        base_url
        or os.getenv("LLM_BASE_URL")
        or _provider_default_base_url(resolved_provider)
        or None
    )
    resolved_temperature = _coerce_temperature(
        temperature if temperature is not None else os.getenv("LLM_TEMPERATURE", "0.2")
    )
    resolved_api_key = _resolve_api_key(resolved_provider, api_key)

    if strict and _provider_requires_api_key(resolved_provider) and not resolved_api_key:
        candidate_keys = ", ".join(_provider_key_env_candidates(resolved_provider))
        raise RuntimeError(
            f"Missing API key for provider '{resolved_provider}'. Expected one of: {candidate_keys}"
        )

    # OpenAI client requires a key argument even for local ollama-like endpoints.
    if resolved_provider == "ollama" and not resolved_api_key:
        resolved_api_key = "ollama"

    return LLMConfig(
        provider=resolved_provider,
        model=resolved_model,
        api_key=resolved_api_key,
        base_url=resolved_base_url,
        temperature=resolved_temperature,
    )


def load_config() -> LLMConfig:
    return build_config()


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
    if cfg.provider in _OPENAI_COMPATIBLE_PROVIDERS:
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

    raise RuntimeError(
        f"Unsupported LLM_PROVIDER: {cfg.provider}. "
        "Use an OpenAI-compatible provider or configure LLM_BASE_URL."
    )


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
    if cfg.provider in _OPENAI_COMPATIBLE_PROVIDERS:
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

    raise RuntimeError(
        f"Unsupported LLM_PROVIDER: {cfg.provider}. "
        "Use an OpenAI-compatible provider or configure LLM_BASE_URL."
    )

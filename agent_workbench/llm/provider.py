from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Optional

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

def generate(system: str, user: str, cfg: LLMConfig) -> str:
    """
    统一调用入口：未来更换provider只改这里。
    目前先实现 openai（也兼容OpenAI-style接口：只要配base_url）。
    """
    if cfg.provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
        resp = client.chat.completions.create(
            model=cfg.model,
            temperature=cfg.temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return (resp.choices[0].message.content or "").strip()

    raise RuntimeError(f"Unsupported LLM_PROVIDER: {cfg.provider}")

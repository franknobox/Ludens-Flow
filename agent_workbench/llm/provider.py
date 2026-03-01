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

def generate(system: str, user: str, cfg: LLMConfig, history: Optional[list] = None) -> str:
    """
    统一调用入口：未来更换provider只改这里。
    目前先实现 openai（也兼容OpenAI-style接口：只要配base_url）。
    """
    if cfg.provider == "openai":
        from openai import OpenAI

        # 默认 120 秒超时，防止遇到后端（例如 Moonshot Kimi）网络波动挂起不返回。
        client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url, timeout=120.0)
        
        messages = [{"role": "system", "content": system}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user})
        
        # 构建基础请求载荷
        kwargs = {
            "model": cfg.model,
            "messages": messages,
        }
        
        # O1/O3 等推理模型以及 kimi k2.5 拒绝手动设置采样参数，提前过滤以防触发不必要的 400 重传延迟
        if cfg.temperature is not None and not any(m in cfg.model.lower() for m in ["k2.5", "o1", "o3", "reasoning"]):
            kwargs["temperature"] = cfg.temperature
            
        try:
            resp = client.chat.completions.create(**kwargs)
        except Exception as e:
            err_msg = str(e).lower()
            # 兼容 Kimi k2.5 / OpenAI o1 等自带固化推理参数、禁止强行设置采样率的模型
            # 最安全的后撤步是：当遭遇 API 阻断，抹除掉任何自定义的 temperature/top_p，依赖接口本身的默认值。
            if "temperature" in err_msg or "only 1" in err_msg or "only allowed" in err_msg or "invalid" in err_msg:
                kwargs.pop("temperature", None)
                resp = client.chat.completions.create(**kwargs)
            else:
                raise e
                
        return (resp.choices[0].message.content or "").strip()

    raise RuntimeError(f"Unsupported LLM_PROVIDER: {cfg.provider}")

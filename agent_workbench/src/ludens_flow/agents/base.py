import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from ludens_flow.state import LudensState
from llm.provider import LLMConfig, generate

logger = logging.getLogger(__name__)


@dataclass
class CommitSpec:
    """Agent 交给 Graph 的落盘描述。"""
    artifact_name: str      # 目标工件名
    content: str            # 最终内容
    reason: str             # 写入原因

@dataclass
class AgentResult:
    """Agent 标准返回结构。"""
    assistant_message: str                           # 给用户的自然语言回复
    state_updates: Dict[str, Any] = field(default_factory=dict)  # 要合并回 LudensState 的增量更新
    commit: Optional[CommitSpec] = None              # 定稿阶段的落盘描述
    events: List[str] = field(default_factory=list)  # 供 Router 消费的事件
    profile_updates: List[str] = field(default_factory=list)  # 待写入用户画像的条目


class BaseAgent(ABC):
    """所有 Agent 的公共基类。约定 discuss 负责对话，commit 负责定稿。"""
    name: str = "BaseAgent"
    system_prompt: str = ""

    def _build_tool_continuation_prompt(self, original_user_prompt: Union[str, list]) -> str:
        """Preserve the original output contract after tool calls."""
        if isinstance(original_user_prompt, str):
            prompt = original_user_prompt.strip()
        else:
            prompt = "Please continue the user's original request."

        return (
            "Please continue and produce the final answer for the original request. "
            "You must still follow the original instructions and output format exactly. "
            "If the original request requires JSON, output only the final JSON object with no extra text.\n\n"
            f"Original request:\n{prompt}"
        )
    
    def _response_to_text(self, response: Any) -> str:
        """Best-effort normalization for provider responses."""
        if response is None:
            return ""
        if isinstance(response, str):
            return response.strip()

        content = getattr(response, "content", None)
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                    continue
                text = getattr(item, "text", None)
                if isinstance(text, str):
                    parts.append(text)
                    continue
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            return "\n".join(p for p in parts if p).strip()

        return str(response).strip()
    
    def _filter_profile_updates(self, updates: List[str]) -> List[str]:
        """Drop verbose/context-like payloads before they are merged into USER_PROFILE."""
        import re

        cleaned: List[str] = []
        seen = set()
        for item in updates or []:
            text = str(item).strip()
            if not text:
                continue
            lower = text.lower()
            if any(marker in lower for marker in ["用户画像：", "===profile_instruction===", '"reply"', '"state_updates"', '"events"']):
                continue
            normalized = re.sub(r"^\s*\[PROFILE_UPDATE\]\s*", "", text, flags=re.IGNORECASE)
            if len(normalized) > 160 or "\n" in normalized or "{" in normalized or "[" in normalized:
                continue
            if not re.match(r"^[^:\n]{1,50}\s*:\s*.+$", normalized):
                continue
            if text not in seen:
                seen.add(text)
                cleaned.append(text)
        return cleaned

    def _json_like_load(self, s: str) -> Any:
        import ast
        import json
        import re

        try:
            return json.loads(s)
        except Exception:
            pass

        s2 = re.sub(r"/\*.*?\*/", "", s, flags=re.DOTALL)
        s2 = re.sub(r"//.*?$", "", s2, flags=re.MULTILINE)
        s2 = re.sub(r",\s*([}\]])", r"\1", s2)
        try:
            return json.loads(s2)
        except Exception:
            pass

        try:
            val = ast.literal_eval(s)
            if isinstance(val, (dict, list)):
                return val
        except Exception:
            pass

        m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", s)
        if not m:
            return None

        chunk = m.group(1)
        try:
            return json.loads(chunk)
        except Exception:
            try:
                val = ast.literal_eval(chunk)
                if isinstance(val, (dict, list)):
                    return val
            except Exception:
                pass
        return None

    def _normalize_profile_updates(self, parsed_obj: dict) -> dict:
        import json
        import re

        if not isinstance(parsed_obj, dict) or "profile_updates" not in parsed_obj:
            return parsed_obj

        pu = parsed_obj.get("profile_updates")
        if pu is None:
            parsed_obj["profile_updates"] = []
            return parsed_obj

        if isinstance(pu, list):
            parsed_obj["profile_updates"] = self._filter_profile_updates([str(x) for x in pu])
            return parsed_obj

        if isinstance(pu, str):
            try:
                pu_parsed = json.loads(pu)
                if isinstance(pu_parsed, list):
                    parsed_obj["profile_updates"] = self._filter_profile_updates([str(x) for x in pu_parsed])
                    return parsed_obj
            except Exception:
                pass

            lines = []
            for line in pu.splitlines():
                mline = re.match(r"^\s*\[PROFILE_UPDATE\]\s*(.*)$", line, flags=re.IGNORECASE)
                if mline:
                    lines.append(mline.group(1).strip())
                else:
                    s = line.strip()
                    if s:
                        lines.append(s)
            parsed_obj["profile_updates"] = self._filter_profile_updates(lines)
            return parsed_obj

        parsed_obj["profile_updates"] = self._filter_profile_updates([str(pu)])
        return parsed_obj

    def _safe_load_json_string(self, raw_val: str) -> Optional[str]:
        import ast
        import json

        try:
            val = json.loads(raw_val)
            if isinstance(val, str):
                return val
        except Exception:
            pass

        try:
            val = ast.literal_eval(raw_val)
            if isinstance(val, str):
                return val
        except Exception:
            pass

        s = raw_val[1:-1] if len(raw_val) >= 2 and raw_val[0] == '"' and raw_val[-1] == '"' else raw_val
        return s.replace('\\"', '"').replace("\\\\", "\\").replace("\\n", "\n").replace("\\r", "\r").replace("\\t", "\t")

    # def _extract_balanced_json(self, text: str, start_idx: int) -> Optional[tuple[str, int]]:
    #     """Return a balanced JSON-like object/array substring starting at start_idx."""
    #     open_ch = text[start_idx]
    #     if open_ch == "{":
    #         close_ch = "}"
    #     elif open_ch == "[":
    #         close_ch = "]"
    #     else:
    #         return None

    #     depth = 0
    #     in_str = False
    #     escaped = False
    #     i = start_idx
    #     while i < len(text):
    #         ch = text[i]
    #         if escaped:
    #             escaped = False
    #         elif ch == "\\":
    #             escaped = True
    #         elif ch == '"':
    #             in_str = not in_str
    #         elif not in_str:
    #             if ch == open_ch:
    #                 depth += 1
    #             elif ch == close_ch:
    #                 depth -= 1
    #                 if depth == 0:
    #                     return text[start_idx:i + 1], i + 1
    #         i += 1
    #     return None

    def _salvage_structured_fields(self, text_value: str) -> Optional[dict]:
        import re

        if not text_value:
            return None

        def _extract_json_value(key: str):
            pattern = re.compile(rf'"{re.escape(key)}"\s*:\s*', re.IGNORECASE)
            match = pattern.search(text_value)
            if not match:
                return None
            idx = match.end()
            while idx < len(text_value) and text_value[idx].isspace():
                idx += 1
            if idx >= len(text_value):
                return None

            opener = text_value[idx]
            if opener == '"':
                i = idx + 1
                escaped = False
                while i < len(text_value):
                    ch = text_value[i]
                    if escaped:
                        escaped = False
                    elif ch == "\\":
                        escaped = True
                    elif ch == '"':
                        raw_val = text_value[idx:i + 1]
                        return self._safe_load_json_string(raw_val)
                    i += 1
                return self._safe_load_json_string(text_value[idx:])

            if opener in "[{":
                candidate = self._extract_balanced_json(text_value, idx)
                if candidate:
                    raw_val, _ = candidate
                    return self._json_like_load(raw_val)
                return None

            tail = re.match(r"(null|true|false|-?\d+(?:\.\d+)?)", text_value[idx:], re.IGNORECASE)
            return self._json_like_load(tail.group(1)) if tail else None

        reply = _extract_json_value("reply")
        state_updates = _extract_json_value("state_updates")
        profile_updates = _extract_json_value("profile_updates")
        events = _extract_json_value("events")

        if reply is None and state_updates is None and profile_updates is None and events is None:
            return None

        result = {
            "reply": reply if isinstance(reply, str) else "",
            "state_updates": state_updates if isinstance(state_updates, dict) else {},
            "profile_updates": profile_updates if isinstance(profile_updates, list) else ([] if profile_updates is None else [str(profile_updates)]),
            "events": events if isinstance(events, list) else [],
        }
        result["profile_updates"] = self._filter_profile_updates([str(x) for x in result["profile_updates"]])
        return result

    def _call(self, user_prompt: Union[str, list], cfg: Optional[LLMConfig] = None, history: Optional[List[Dict[str, Any]]] = None, tools: Optional[list] = None, user_persona: Optional[str] = None) -> str:
        """统一 LLM 调用入口，处理配置和多轮 tool calling。"""
        from llm.provider import load_config
        if cfg is None:
            try:
                cfg = load_config()
            except Exception:
                pass
                
        if history is None:
            history = []
        else:
            # 避免直接改调用方传入的 history。
            history = list(history)
            
        max_tool_iterations = 5
        iterations = 0
        original_user_prompt = user_prompt
        
        # LLM 在回答时能把用户画像作为独立的上下文参考
        if user_persona:
            history.append({"role": "user", "content": user_persona})


        # 首轮模型调用。
        response = generate(system=self.system_prompt, user=user_prompt, cfg=cfg, history=history, tools=tools)
        
        while hasattr(response, "tool_calls") and response.tool_calls and iterations < max_tool_iterations:
            iterations += 1
            
            # 首轮工具调用时，把原始用户输入补进 history，后续改用中性续写提示。
            if iterations == 1:
               history.append({"role": "user", "content": user_prompt})
               user_prompt = self._build_tool_continuation_prompt(original_user_prompt)
            
            assistant_msg = {
                "role": "assistant", 
                "content": response.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in response.tool_calls
                ]
            }
            history.append(assistant_msg)
            
            # 执行模型请求的工具。
            for tool_call in response.tool_calls:
                tool_name = tool_call.function.name
                tool_args_str = tool_call.function.arguments
                
                try:
                    import json
                    args = json.loads(tool_args_str)
                    
                    if tool_name == "web_search":
                        from ludens_flow.tools.search import web_search
                        query = args.get("query", "")
                        logger.info(f"Agent executing tool: {tool_name} with query: '{query}'")
                        tool_result = web_search(query)
                    else:
                        tool_result = f"Error: Tool '{tool_name}' not found."
                        
                except Exception as e:
                    tool_result = f"Error executing tool {tool_name}: {e}"
                
                # 把工具结果回灌给模型。
                history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(tool_result)
                })
                
            # 继续请求模型生成最终回复。
            response = generate(system=self.system_prompt, user=user_prompt, cfg=cfg, history=history, tools=tools)

        if hasattr(response, "tool_calls"):
            logger.warning(f"Agent exceeded maximum tool iterations ({max_tool_iterations}). Forcing exit.")
            return self._response_to_text(response)
             
        # 普通文本响应。
        return self._response_to_text(response)

    def extract_profile_updates(self, assistant_text: str) -> List[str]:
        """提取 [PROFILE_UPDATE] 行，并标准化为字符串列表。"""
        import re, json
        if not assistant_text:
            return []
        lines = assistant_text.splitlines()
        updates: List[str] = []
        pattern = re.compile(r"^\s*\[PROFILE_UPDATE\]\s*(.*)$", re.IGNORECASE)
        for line in lines:
            m = pattern.match(line)
            if not m:
                continue
            payload = m.group(1).strip()
            if not payload:
                continue
            # 支持把 JSON payload 拆成多条更新。
            if (payload.startswith("{") and payload.endswith("}")) or (payload.startswith("[") and payload.endswith("]")):
                try:
                    parsed = json.loads(payload)
                    # dict 展开为 key/value，list 展开为逐条字符串。
                    if isinstance(parsed, dict):
                        for k, v in parsed.items():
                            updates.append(f"{k}: {v}")
                    elif isinstance(parsed, list):
                        for item in parsed:
                            updates.append(str(item))
                except Exception:
                    # 解析失败时保留原始文本。
                    updates.append(payload)
            else:
                updates.append(payload)

        # 去重并保持顺序。
        seen = set()
        result = []
        for u in updates:
            key = u.strip()
            if key and key not in seen:
                seen.add(key)
                result.append(key)
        return result
    
    def parse_structured_response(self, assistant_text: str) -> tuple[Optional[dict], str]:
        import json, re
        if not assistant_text or not assistant_text.strip():
            return None, ""
        text = assistant_text.strip()

        # 合法JSON
        try:
            parsed = json.loads(text)
            if isinstance(parsed, (dict, list)):
                if isinstance(parsed, dict):
                    parsed = self._normalize_profile_updates(parsed)
                return parsed, ""
        except Exception:
            pass
        
        # 正则提取
        m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
        if m:
            chunk = m.group(1)
            parsed = self._json_like_load(chunk)
            if parsed is not None:
                if isinstance(parsed, dict):
                    parsed = self._normalize_profile_updates(parsed)
                remaining = text.replace(chunk, "").strip()
                return parsed, remaining

        # 兜底方案
        salvaged = self._salvage_structured_fields(text)
        if salvaged is not None:
            return salvaged, ""

        return None, text


    @abstractmethod
    def discuss(self, state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None, user_persona: Optional[str] = None) -> AgentResult:
        """讨论阶段入口。"""
        ...

    @abstractmethod
    def commit(self, state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None, user_persona: Optional[str] = None) -> AgentResult:
        """定稿阶段入口。"""
        ...

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
               user_prompt = "Please continue."
            
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
             return (response.content or "").strip()
             
        # 普通文本响应。
        return str(response)

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

        # 1) 优先处理 ```json ``` 的代码块
        m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
        if m:
            try:
                return json.loads(m.group(1)), (text[:m.start()] + text[m.end():]).strip()
            except Exception:
                pass

        # 2) 处理自定义标记（例如 <<TAG>> ... <<END>>）
        m = re.search(r"<<[^>]+>>\s*(\{.*?\})\s*<<END_[^>]+>>", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1)), (text[:m.start()] + text[m.end():]).strip()
            except Exception:
                pass

        # 3) 花括号平衡查找第一个完整 JSON 对象
        start = text.find("{")
        while start != -1:
            depth = 0
            for i in range(start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = text[start:i+1]
                        try:
                            parsed = json.loads(candidate)
                            remaining = (text[:start] + text[i+1:]).strip()
                            return parsed, remaining
                        except Exception:
                            break
            start = text.find("{", start + 1)
        return None, text


    @abstractmethod
    def discuss(self, state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None, user_persona: Optional[str] = None) -> AgentResult:
        """讨论阶段入口。"""
        ...

    @abstractmethod
    def commit(self, state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None, user_persona: Optional[str] = None) -> AgentResult:
        """定稿阶段入口。"""
        ...

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from ludens_flow.state import LudensState
from llm.provider import LLMConfig, generate

logger = logging.getLogger(__name__)


@dataclass
class CommitSpec:
    """Agent 向外界抛出写文件的具体配方凭证"""
    artifact_name: str      # 要写入的核心工件名字，例如 "GDD"
    content: str            # 将要写入的内容文本
    reason: str             # 写该版文件的起因，例如 "User confirmed commit"

@dataclass
class AgentResult:
    """每个 Agent 通用的标准返回字典包装接口"""
    assistant_message: str                           # 要显示给用户的自然语言回复
    state_updates: Dict[str, Any] = field(default_factory=dict)  # 需要合并给 `LudensState` 的增量属性
    commit: Optional[CommitSpec] = None              # 当处于 COMMIT 节点时的写入凭证 
    events: List[str] = field(default_factory=list)  # 追加事件，比如触发自动路由的 ["*_COMMITTED"] 等


class BaseAgent(ABC):
    """
    BaseAgent 的全新两段式架构：
    1. discuss() -> AgentResult: 不直接落盘核心文档，只存草稿 (state.drafts) / 发起对话
    2. commit()  -> AgentResult: 当用户要求定稿时调用，生成带有 CommitSpec 凭据的结果交给外界写入
    """
    name: str = "BaseAgent"
    system_prompt: str = ""

    def _call(self, user_prompt: Union[str, list], cfg: Optional[LLMConfig] = None, history: Optional[List[Dict[str, Any]]] = None, tools: Optional[list] = None) -> str:
        """统一 LLM 调用入口。支持自动多轮 Tool Calling 处理。"""
        from llm.provider import load_config
        if cfg is None:
            try:
                cfg = load_config()
            except Exception:
                pass
                
        if history is None:
            history = []
        else:
            # Create a shallow copy so we don't mutate the caller's history
            history = list(history)
            
        max_tool_iterations = 5
        iterations = 0
        
        # Initial call
        response = generate(system=self.system_prompt, user=user_prompt, cfg=cfg, history=history, tools=tools)
        
        while hasattr(response, "tool_calls") and response.tool_calls and iterations < max_tool_iterations:
            iterations += 1
            
            # Need to append the assistant's request to call the tool to the history
            # The 'generate' function appends the exact user_prompt at the end of history,
            # so to continue the conversation robustly when tool calling, we must assimilate
            # the original user_prompt into history, and send a blank user_prompt for subsequent calls
            if iterations == 1:
               history.append({"role": "user", "content": user_prompt})
               user_prompt = "Please continue." # Provide a neutral continuation prompt
            
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
            
            # Execute all requested tools
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
                
                # Append tool result to history
                history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(tool_result)
                })
                
            # Request LLM to continue with tool results
            response = generate(system=self.system_prompt, user=user_prompt, cfg=cfg, history=history, tools=tools)

        if hasattr(response, "tool_calls"):
             logger.warning(f"Agent exceeded maximum tool iterations ({max_tool_iterations}). Forcing exit.")
             return (response.content or "").strip()
             
        # Normal string response
        return str(response)

    @abstractmethod
    def discuss(self, state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None) -> AgentResult:
        """
        供 Router 分派在 *_DISCUSS 节点使用的入口。
        应该读取用户的意图并利用 LLM 作答；必要时把临时构思丢进 state_updates 的 drafts 字段里。
        """
        ...

    @abstractmethod
    def commit(self, state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None) -> AgentResult:
        """
        供 Router 分派在 *_COMMIT 节点使用的入口。
        此时直接将草稿转化成完整的标记语言，或通过 LLM 生成终版内容，将它包装进 CommitSpec 内返回。
        注意：Agent 绝对不能在此处动用 open/writeFile！
        """
        ...

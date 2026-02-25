import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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

    def _call(self, user_prompt: str, cfg: Optional[LLMConfig] = None, history: Optional[List[Dict[str, str]]] = None) -> str:
        """统一 LLM 调用入口。未来如果换框架，只需修改此处。"""
        # 注意: 正常运行时如果没有传入 cfg, 需要自己实例化。为解耦我们目前允许传 None。
        from llm.provider import load_config
        if cfg is None:
            # 安全后备方案
            try:
                cfg = load_config()
            except Exception:
                # 若无法加载 (例如测试无 key), 这里会直接挂掉
                pass
        return generate(system=self.system_prompt, user=user_prompt, cfg=cfg, history=history)

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

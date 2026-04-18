import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union

from ludens_flow.schemas import extract_structured_json_object
from ludens_flow.state import LudensState
from ludens_flow.tools.registry import dispatch_tool_call, merge_tool_schemas
from llm.provider import LLMConfig, generate, generate_stream

logger = logging.getLogger(__name__)


@dataclass
class CommitSpec:
    """Commit description passed from an Agent back to the graph."""

    artifact_name: str
    content: str
    reason: str


@dataclass
class AgentResult:
    """Standard result contract returned by an Agent step."""

    assistant_message: str
    state_updates: Dict[str, Any] = field(default_factory=dict)
    commit: Optional[CommitSpec] = None
    events: List[str] = field(default_factory=list)
    profile_updates: List[str] = field(default_factory=list)


class BaseAgent(ABC):
    """Shared base class for all agents."""

    name: str = "BaseAgent"
    system_prompt: str = ""
    _STREAM_BREAK_PATTERN = re.compile(r"(.+?(?:\n\n|[。！？!?]\s*|\n))", re.DOTALL)

    def _compose_user_prompt(
        self,
        instruction_text: str,
        user_input: Union[str, list],
        *,
        input_label: str = "当前用户输入",
    ) -> Union[str, list]:
        """Build a text or multimodal user prompt without degrading image inputs."""
        prefix = instruction_text.strip()
        if isinstance(user_input, list):
            has_attached_file = any(
                isinstance(item, dict)
                and item.get("type") == "text"
                and "[Attached File]" in str(item.get("text", ""))
                for item in user_input
            )
            if has_attached_file:
                attachment_rule = (
                    "Important attachment handling rules:\n"
                    "- The user's current input already includes attached file content below.\n"
                    "- Do not say you cannot see the file if attached file content is present.\n"
                    "- Read the attached file content first, then answer from that content.\n"
                    "- If exactly one file is attached, phrases like 'the file' or 'this file' refer to that file by default.\n"
                    "- When answering, cite the file name explicitly.\n"
                )
                prefix = f"{prefix}\n\n{attachment_rule}".strip() if prefix else attachment_rule
            parts: list[dict[str, Any]] = []
            if prefix:
                parts.append(
                    {
                        "type": "text",
                        "text": f"{prefix}\n\n{input_label}：",
                    }
                )
            parts.extend(user_input)
            return parts

        clean_input = str(user_input or "").strip()
        if prefix and clean_input:
            return f"{prefix}\n\n{input_label}：{clean_input}"
        if prefix:
            return prefix
        return clean_input

    def _call(
        self,
        user_prompt: Union[str, list],
        cfg: Optional[LLMConfig] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        tools: Optional[list] = None,
        user_persona: Optional[str] = None,
        project_id: Optional[str] = None,
        stream_handler: Optional[Callable[[str], None]] = None,
        tool_event_handler: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> str:
        """Shared LLM call entrypoint with optional tool-calling loop."""
        from llm.provider import load_config

        if cfg is None:
            try:
                cfg = load_config()
            except Exception:
                pass

        if history is None:
            history = []
        else:
            history = list(history)

        max_tool_iterations = 5
        iterations = 0

        if user_persona:
            history.append({"role": "user", "content": user_persona})

        active_tools = merge_tool_schemas(tools)

        if stream_handler and not active_tools:
            return self._call_streaming(
                user_prompt,
                cfg,
                history=history,
                stream_handler=stream_handler,
            )

        response = generate(
            system=self.system_prompt,
            user=user_prompt,
            cfg=cfg,
            history=history,
            tools=active_tools,
        )

        while (
            hasattr(response, "tool_calls")
            and response.tool_calls
            and iterations < max_tool_iterations
        ):
            iterations += 1

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
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in response.tool_calls
                ],
            }
            history.append(assistant_msg)

            for tool_call in response.tool_calls:
                tool_name = tool_call.function.name
                tool_args_str = tool_call.function.arguments

                try:
                    args = json.loads(tool_args_str)
                    logger.info("Agent executing tool: %s", tool_name)
                    if tool_event_handler:
                        tool_event_handler(
                            {
                                "type": "tool_started",
                                "tool_name": tool_name,
                                "args": args,
                            }
                        )
                    tool_result = dispatch_tool_call(
                        tool_name,
                        args,
                        project_id=project_id,
                    )
                    if tool_event_handler:
                        tool_event_handler(
                            {
                                "type": "tool_completed",
                                "tool_name": tool_name,
                                "args": args,
                                "result": str(tool_result),
                            }
                        )
                except Exception as exc:
                    if tool_event_handler:
                        tool_event_handler(
                            {
                                "type": "tool_failed",
                                "tool_name": tool_name,
                                "args": (
                                    args if "args" in locals() and isinstance(args, dict) else {}
                                ),
                                "error": str(exc),
                            }
                        )
                    tool_result = f"Error executing tool {tool_name}: {exc}"

                history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(tool_result),
                    }
                )

            response = generate(
                system=self.system_prompt,
                user=user_prompt,
                cfg=cfg,
                history=history,
                tools=active_tools,
            )

        if hasattr(response, "tool_calls"):
            logger.warning(
                "Agent exceeded maximum tool iterations (%s). Forcing exit.",
                max_tool_iterations,
            )
            return (response.content or "").strip()

        return str(response)

    def _call_streaming(
        self,
        user_prompt: Union[str, list],
        cfg: LLMConfig,
        *,
        history: List[Dict[str, Any]],
        stream_handler: Callable[[str], None],
    ) -> str:
        full_parts: List[str] = []
        buffer = ""

        for delta in generate_stream(
            system=self.system_prompt,
            user=user_prompt,
            cfg=cfg,
            history=history,
        ):
            if not delta:
                continue
            full_parts.append(delta)
            buffer += delta

            while True:
                match = self._STREAM_BREAK_PATTERN.match(buffer)
                if match:
                    segment = match.group(1)
                    if segment.strip():
                        stream_handler(segment)
                    buffer = buffer[len(segment) :]
                    continue

                flush_index = self._find_soft_break(buffer)
                if flush_index is None:
                    break
                segment = buffer[:flush_index]
                if segment.strip():
                    stream_handler(segment)
                buffer = buffer[flush_index:]

            if len(buffer) >= 120:
                segment = buffer
                if segment.strip():
                    stream_handler(segment)
                buffer = ""

        if buffer.strip():
            stream_handler(buffer)

        return "".join(full_parts).strip()

    def _find_soft_break(self, text: str) -> Optional[int]:
        if len(text) < 60:
            return None

        candidates = [
            text.rfind("，"),
            text.rfind(", "),
            text.rfind("；"),
            text.rfind("; "),
            text.rfind("："),
            text.rfind(": "),
        ]
        soft_break = max(candidates)
        if soft_break < 0:
            return None
        return soft_break + 1

    def extract_profile_updates(self, assistant_text: str) -> List[str]:
        """Extract [PROFILE_UPDATE] lines as normalized strings."""
        if not assistant_text:
            return []

        lines = assistant_text.splitlines()
        updates: List[str] = []
        pattern = re.compile(r"^\s*\[PROFILE_UPDATE\]\s*(.*)$", re.IGNORECASE)

        for line in lines:
            match = pattern.match(line)
            if not match:
                continue

            payload = match.group(1).strip()
            if not payload:
                continue

            if (payload.startswith("{") and payload.endswith("}")) or (
                payload.startswith("[") and payload.endswith("]")
            ):
                try:
                    parsed = json.loads(payload)
                    if isinstance(parsed, dict):
                        for key, value in parsed.items():
                            updates.append(f"{key}: {value}")
                    elif isinstance(parsed, list):
                        for item in parsed:
                            updates.append(str(item))
                except Exception:
                    updates.append(payload)
            else:
                updates.append(payload)

        seen = set()
        result = []
        for item in updates:
            key = item.strip()
            if key and key not in seen:
                seen.add(key)
                result.append(key)
        return result

    def parse_structured_response(
        self, assistant_text: str
    ) -> tuple[Optional[dict], str]:
        return extract_structured_json_object(assistant_text)

    @abstractmethod
    def discuss(
        self,
        state: LudensState,
        user_input: str,
        cfg: Optional[LLMConfig] = None,
        user_persona: Optional[str] = None,
        stream_handler: Optional[Callable[[str], None]] = None,
        tool_event_handler: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> AgentResult:
        """Discussion-phase entrypoint."""
        ...

    @abstractmethod
    def commit(
        self,
        state: LudensState,
        user_input: str,
        cfg: Optional[LLMConfig] = None,
        user_persona: Optional[str] = None,
        tool_event_handler: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> AgentResult:
        """Commit-phase entrypoint."""
        ...

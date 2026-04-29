"""
文件功能：结构化协议子模块（__init__.py），定义并解析关键输出协议。
核心内容：统一处理 discuss/review 等阶段的 JSON 结构化内容抽取。
核心内容：为 Agent 与 graph 提供稳定协议边界，降低输出漂移风险。
"""

from ludens_flow.core.schemas.discuss import (
    DISCUSS_RESPONSE_SCHEMA_TEXT,
    DiscussPayload,
    normalize_discuss_payload,
    parse_discuss_payload,
)
from ludens_flow.core.schemas.json_objects import extract_structured_json_object
from ludens_flow.core.schemas.copywriting import (
    COPYWRITING_RESPONSE_SCHEMA_TEXT,
    DesignCopywritingCandidate,
    DesignCopywritingContext,
    DesignCopywritingContextItem,
    DesignCopywritingRequest,
    DesignCopywritingResponse,
    normalize_design_copywriting_request,
    normalize_design_copywriting_response,
    parse_design_copywriting_response,
)
from ludens_flow.core.schemas.review_gate import (
    REVIEW_GATE_SCHEMA_TEXT,
    ReviewGatePayload,
    normalize_review_gate_payload,
    parse_review_gate_payload,
)

__all__ = [
    "DISCUSS_RESPONSE_SCHEMA_TEXT",
    "DiscussPayload",
    "normalize_discuss_payload",
    "parse_discuss_payload",
    "extract_structured_json_object",
    "COPYWRITING_RESPONSE_SCHEMA_TEXT",
    "DesignCopywritingCandidate",
    "DesignCopywritingContext",
    "DesignCopywritingContextItem",
    "DesignCopywritingRequest",
    "DesignCopywritingResponse",
    "normalize_design_copywriting_request",
    "normalize_design_copywriting_response",
    "parse_design_copywriting_response",
    "REVIEW_GATE_SCHEMA_TEXT",
    "ReviewGatePayload",
    "normalize_review_gate_payload",
    "parse_review_gate_payload",
]

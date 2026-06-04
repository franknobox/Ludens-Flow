from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from llm.modelrouter import resolve_model_config
from llm.provider import generate as generate_llm
from ludens_flow.core.paths import get_project_dir, get_project_settings, resolve_project_id

RUNTIME_CONFIG_FILE_NAME = "game_model_runtime.json"
RUNTIME_SCHEMA_VERSION = 1

ALLOWED_MODALITIES = {"image", "audio", "video"}


RUNTIME_MODELS: list[dict[str, Any]] = [
    {
        "id": "gpt-5.4-mini",
        "name": "GPT-5.4 Mini",
        "provider": "OpenAI",
        "categories": ["npc", "quest_behavior"],
        "runtime_role": "low_latency_dialogue",
        "status": "available",
        "strengths": ["low_latency", "cost_control", "tool_calling"],
    },
    {
        "id": "o3-mini",
        "name": "o3-mini",
        "provider": "OpenAI",
        "categories": ["quest_behavior", "world_model"],
        "runtime_role": "logic_planner",
        "status": "available",
        "strengths": ["structured_reasoning", "behavior_tree", "quest_logic"],
    },
    {
        "id": "gemini-3.1-pro",
        "name": "Gemini 3.1 Pro",
        "provider": "Google",
        "categories": ["multimodal"],
        "runtime_role": "multimodal_analyzer",
        "status": "available",
        "strengths": ["image_understanding", "audio_understanding", "video_understanding"],
    },
    {
        "id": "world-model-preview",
        "name": "World Model Runtime",
        "provider": "Ludens-Flow",
        "categories": ["world_model"],
        "runtime_role": "simulation_preview",
        "status": "coming_soon",
        "strengths": ["state_prediction", "economy_simulation", "npc_society"],
    },
]


DEFAULT_RUNTIME_SCENES: list[dict[str, Any]] = [
    {
        "id": "npc-dialogue-runtime",
        "name": "NPC 运行时对话",
        "category": "npc",
        "modelId": "gpt-5.4-mini",
        "systemPrompt": "你是游戏运行时 NPC 对话 Agent。必须遵守角色人设、场景状态和安全边界，输出短句并附带可选动作标签。",
        "temperature": 0.7,
        "maxTokens": 180,
        "tools": ["npc_memory_read", "quest_state_query", "dialogue_policy_check"],
        "testInput": "玩家询问：你刚才看见谁进了黑木林？",
        "runtimeStage": "ready",
        "description": "面向 NPC 对话、任务提示和剧情回顾的低延迟调用配置。",
        "outputContract": {
            "type": "dialogue_turn",
            "fields": ["speaker", "text", "emotion", "suggested_animation", "quest_flags"],
        },
    },
    {
        "id": "character-behavior-tree",
        "name": "AI 生成角色行为树",
        "category": "quest_behavior",
        "modelId": "o3-mini",
        "systemPrompt": "你是角色 AI 设计器。根据角色目标、感知输入和战斗规则，输出可导入 Unity 的行为树 JSON。",
        "temperature": 0.25,
        "maxTokens": 900,
        "tools": ["navmesh_query", "combat_rule_query", "blackboard_schema"],
        "testInput": "角色：黑木林巡逻兵；目标：发现玩家后呼叫同伴并保命；约束：不能离开巡逻区。",
        "runtimeStage": "ready",
        "description": "把自然语言角色需求转成行为树节点、黑板变量、转移条件和 Unity Runner 绑定。",
        "outputContract": {
            "type": "behavior_tree",
            "fields": ["blackboard", "tree.nodes", "tree.transitions", "unity_mapping"],
        },
    },
    {
        "id": "questline-generator",
        "name": "AI 生成任务 / 任务线",
        "category": "quest_behavior",
        "modelId": "o3-mini",
        "systemPrompt": "你是任务系统设计器。根据区域、玩家等级和剧情节拍，输出任务线 JSON、目标依赖和服务端事件约定。",
        "temperature": 0.35,
        "maxTokens": 1100,
        "tools": ["map_state_query", "reward_table_query", "quest_flag_schema"],
        "testInput": "区域：黑木林；玩家等级：20；剧情：兽人部落集结；生成 4 段任务线。",
        "runtimeStage": "ready",
        "description": "生成可运行的任务线结构，包括目标、依赖、奖励、失败状态和运行时变量。",
        "outputContract": {
            "type": "questline",
            "fields": ["quests", "objectives", "rewards", "runtime_variables", "server_contract"],
        },
    },
    {
        "id": "multimodal-runtime",
        "name": "多模态运行时分析",
        "category": "multimodal",
        "modelId": "gemini-3.1-pro",
        "systemPrompt": "你是游戏运行时多模态分析 Agent。读取玩家截图、语音、视频片段，输出可复现问题、情绪线索和调试建议。",
        "temperature": 0.2,
        "maxTokens": 700,
        "tools": ["asset_upload", "playtest_event_query", "privacy_policy_check"],
        "testInput": "上传战斗截图、15 秒语音反馈和 30 秒录像，分析玩家找不到补给按钮的原因。",
        "runtimeStage": "ready",
        "description": "覆盖图片、语音和视频输入的权限、压缩、上传、分析和成本限制。",
        "modalities": ["image", "audio", "video"],
        "outputContract": {
            "type": "multimodal_report",
            "fields": ["observations", "evidence", "severity", "next_debug_steps"],
        },
    },
    {
        "id": "world-model-coming-soon",
        "name": "世界模型 Coming Soon",
        "category": "world_model",
        "modelId": "world-model-preview",
        "systemPrompt": "世界模型将在未来接入长线状态仿真、经济生态推演和 NPC 社会网络模拟。",
        "temperature": 0.1,
        "maxTokens": 800,
        "tools": ["economy_logs_query", "world_state_snapshot", "simulation_sandbox"],
        "testInput": "输入 30 天经济日志、资源产销和 NPC 派系关系，预测未来状态变化。",
        "runtimeStage": "coming_soon",
        "description": "当前提供接口预留、配置预览和验收里程碑，不开放运行时调用。",
        "outputContract": {
            "type": "world_model_preview",
            "fields": ["state_snapshot", "prediction", "interventions", "confidence"],
        },
    },
]


WORLD_MODEL_PLAN: dict[str, Any] = {
    "status": "coming_soon",
    "available": False,
    "milestones": [
        {
            "id": "state-schema",
            "name": "世界状态 Schema",
            "deliverable": "定义经济、派系、NPC 关系、区域事件和资源流转的统一状态结构。",
        },
        {
            "id": "simulation-sandbox",
            "name": "仿真沙盒",
            "deliverable": "支持离线导入日志、运行多轮预测、比较干预策略。",
        },
        {
            "id": "runtime-debug",
            "name": "运行时调试闭环",
            "deliverable": "把预测结果回写到工作台，支持人工审阅后同步到游戏工程。",
        },
    ],
    "guardrails": [
        "世界模型只读取经过脱敏和聚合的运行时日志。",
        "预测结果默认不自动写入线上状态，需要人工确认。",
        "长周期仿真必须设置 token、时间和样本数量上限。",
    ],
}


RUNTIME_PIPELINE: dict[str, Any] = {
    "id": "config-test-export-debug",
    "steps": [
        "工作台内配置 Agent / Prompt / Tool",
        "用结构化测试输入生成运行时工件",
        "导出 Unity 骨架、REST 合约和 runtime_config.json",
        "游戏工程接入后回传日志并迭代调试",
    ],
}


def _trim_text(value: Any, fallback: str = "", *, limit: int = 2000) -> str:
    text = str(value or fallback or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:limit]


def _as_list(value: Any, *, fallback: list[str] | None = None, limit: int = 8) -> list[str]:
    if isinstance(value, str):
        raw_items = re.split(r"[,，/、|]+", value)
    elif isinstance(value, list):
        raw_items = value
    else:
        raw_items = fallback or []

    items: list[str] = []
    for item in raw_items:
        text = _trim_text(item, limit=80)
        if text and text not in items:
            items.append(text)
        if len(items) >= limit:
            break
    return items


def _class_name(raw: str, fallback: str) -> str:
    ascii_only = re.sub(r"[^0-9A-Za-z]+", " ", raw or "").title().replace(" ", "")
    if not ascii_only:
        ascii_only = fallback
    if ascii_only[0].isdigit():
        ascii_only = f"Ludens{ascii_only}"
    return ascii_only[:64]


def _resolve(project_id: str | None = None) -> str:
    resolved = resolve_project_id(project_id)
    if not resolved:
        raise ValueError("Project id is required.")
    return resolved


def _runtime_file(project_id: str) -> Path:
    return get_project_dir(project_id) / RUNTIME_CONFIG_FILE_NAME


def _normalize_scene(raw: dict[str, Any]) -> dict[str, Any]:
    scene = dict(raw or {})
    scene_id = _trim_text(scene.get("id"), "runtime-scene", limit=80)
    return {
        "id": re.sub(r"[^a-zA-Z0-9_.-]+", "-", scene_id).strip("-") or "runtime-scene",
        "name": _trim_text(scene.get("name"), scene_id, limit=80),
        "category": _trim_text(scene.get("category"), "npc", limit=40),
        "modelId": _trim_text(scene.get("modelId") or scene.get("model_id"), "gpt-5.4-mini", limit=80),
        "systemPrompt": _trim_text(
            scene.get("systemPrompt") or scene.get("system_prompt"),
            "你是游戏运行时 Agent。",
            limit=4000,
        ),
        "temperature": float(scene.get("temperature", 0.4)),
        "maxTokens": int(scene.get("maxTokens") or scene.get("max_tokens") or 500),
        "tools": _as_list(scene.get("tools"), limit=12),
        "testInput": _trim_text(scene.get("testInput") or scene.get("test_input"), "", limit=2000),
        "runtimeStage": _trim_text(
            scene.get("runtimeStage") or scene.get("runtime_stage"),
            "ready",
            limit=40,
        ),
        "description": _trim_text(scene.get("description"), "", limit=500),
        "modalities": _as_list(scene.get("modalities"), fallback=[]),
        "outputContract": deepcopy(scene.get("outputContract") or scene.get("output_contract") or {}),
    }


def _default_scenes() -> list[dict[str, Any]]:
    return [_normalize_scene(scene) for scene in DEFAULT_RUNTIME_SCENES]


def _load_saved_scenes(project_id: str) -> list[dict[str, Any]] | None:
    config_file = _runtime_file(project_id)
    if not config_file.exists():
        return None
    try:
        payload = json.loads(config_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    scenes = payload.get("scenes")
    if not isinstance(scenes, list):
        return None
    normalized = [_normalize_scene(scene) for scene in scenes if isinstance(scene, dict)]
    return normalized or None


def save_runtime_scenes(
    scenes: list[dict[str, Any]],
    *,
    project_id: str | None = None,
) -> dict[str, Any]:
    resolved = _resolve(project_id)
    normalized = [_normalize_scene(scene) for scene in scenes]
    payload = {
        "schema_version": RUNTIME_SCHEMA_VERSION,
        "project_id": resolved,
        "scenes": normalized,
    }
    config_file = _runtime_file(resolved)
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return build_runtime_state(project_id=resolved, scenes=normalized)


def build_runtime_state(
    *,
    project_id: str | None = None,
    scenes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    resolved = _resolve(project_id)
    runtime_scenes = (
        [_normalize_scene(scene) for scene in scenes]
        if scenes is not None
        else _load_saved_scenes(resolved) or _default_scenes()
    )
    try:
        project_settings = get_project_settings(project_id=resolved)
    except Exception:
        project_settings = {}

    target_engine = project_settings.get("target_engine") or "generic"
    return {
        "schema_version": RUNTIME_SCHEMA_VERSION,
        "project_id": resolved,
        "module_status": "runtime_ready",
        "target_engine": target_engine,
        "models": deepcopy(RUNTIME_MODELS),
        "scenes": runtime_scenes,
        "runtime_pipeline": deepcopy(RUNTIME_PIPELINE),
        "world_model": deepcopy(WORLD_MODEL_PLAN),
        "guardrails": {
            "cost": {
                "default_max_input_tokens": 12000,
                "default_max_output_tokens": 1200,
                "cache_reusable_context": True,
            },
            "context": {
                "runtime_memory_scope": "project_and_actor",
                "strip_debug_only_notes": True,
            },
            "permissions": [
                "tool_allowlist_required",
                "player_data_minimization",
                "human_review_for_state_writes",
            ],
        },
    }


def _scene_by_id(scene_id: str | None, *, project_id: str | None = None) -> dict[str, Any]:
    state = build_runtime_state(project_id=project_id)
    requested = _trim_text(scene_id, limit=120)
    for scene in state["scenes"]:
        if scene["id"] == requested:
            return scene
    return state["scenes"][0]


def generate_behavior_tree(request: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(request or {})
    scene = payload.get("scene") if isinstance(payload.get("scene"), dict) else None
    scene = _normalize_scene(scene) if scene else _scene_by_id(payload.get("scene_id"))
    character_name = _trim_text(payload.get("character_name"), "运行时角色", limit=80)
    goal = _trim_text(
        payload.get("goal"),
        "根据玩家距离、血量和任务状态选择巡逻、交互、追击或撤退。",
        limit=500,
    )
    context = _trim_text(payload.get("context"), scene.get("testInput", ""), limit=800)
    traits = _as_list(payload.get("traits"), fallback=["谨慎", "可被任务状态影响"], limit=5)
    class_name = _class_name(character_name, "GeneratedCharacterBehavior")

    nodes = [
        {
            "id": "root_selector",
            "type": "selector",
            "name": "Root Decision",
            "children": ["survival_sequence", "engage_sequence", "quest_sequence", "idle_sequence"],
        },
        {
            "id": "survival_sequence",
            "type": "sequence",
            "name": "Survive When Threatened",
            "children": ["check_low_health", "retreat_to_cover", "request_backup"],
        },
        {
            "id": "check_low_health",
            "type": "condition",
            "name": "Health Below Safe Threshold",
            "reads": ["SelfHealth", "ThreatLevel"],
            "expression": "SelfHealth < 35 or ThreatLevel >= 0.8",
        },
        {
            "id": "retreat_to_cover",
            "type": "action",
            "name": "Retreat To Cover",
            "writes": ["CurrentIntent", "MoveTarget"],
            "tool": "navmesh_query",
        },
        {
            "id": "request_backup",
            "type": "action",
            "name": "Request Backup",
            "writes": ["LastBark", "AlertRadius"],
            "tool": "combat_rule_query",
        },
        {
            "id": "engage_sequence",
            "type": "sequence",
            "name": "Engage Visible Player",
            "children": ["check_target_visible", "warn_target", "advance_or_attack"],
        },
        {
            "id": "check_target_visible",
            "type": "condition",
            "name": "Target Visible",
            "reads": ["TargetActor", "PerceptionState"],
            "expression": "TargetActor != null and PerceptionState == 'visible'",
        },
        {
            "id": "warn_target",
            "type": "action",
            "name": "Warn Target",
            "writes": ["LastBark", "CurrentIntent"],
            "prompt": f"用符合 {character_name} 的语气发出短警告。",
        },
        {
            "id": "advance_or_attack",
            "type": "action",
            "name": "Advance Or Attack",
            "reads": ["DistanceToTarget"],
            "writes": ["CombatAction"],
            "tool": "combat_rule_query",
        },
        {
            "id": "quest_sequence",
            "type": "sequence",
            "name": "Quest Sensitive Interaction",
            "children": ["check_quest_flag", "offer_context_hint"],
        },
        {
            "id": "check_quest_flag",
            "type": "condition",
            "name": "Relevant Quest Active",
            "reads": ["QuestFlags"],
            "expression": "QuestFlags contains scene.required_flag",
        },
        {
            "id": "offer_context_hint",
            "type": "action",
            "name": "Offer Context Hint",
            "writes": ["DialogueIntent"],
            "tool": "quest_state_query",
        },
        {
            "id": "idle_sequence",
            "type": "sequence",
            "name": "Patrol And Observe",
            "children": ["patrol_route", "scan_surroundings"],
        },
        {
            "id": "patrol_route",
            "type": "action",
            "name": "Patrol Route",
            "writes": ["MoveTarget", "CurrentIntent"],
            "tool": "navmesh_query",
        },
        {
            "id": "scan_surroundings",
            "type": "action",
            "name": "Scan Surroundings",
            "writes": ["PerceptionState"],
        },
    ]

    return {
        "artifact_type": "behavior_tree",
        "scene_id": scene["id"],
        "character": {
            "name": character_name,
            "goal": goal,
            "traits": traits,
            "context": context,
        },
        "blackboard": [
            {"key": "TargetActor", "type": "Actor", "source": "perception"},
            {"key": "SelfHealth", "type": "float", "source": "character_stats"},
            {"key": "ThreatLevel", "type": "float", "source": "combat_director"},
            {"key": "QuestFlags", "type": "string[]", "source": "quest_system"},
            {"key": "CurrentIntent", "type": "enum", "source": "behavior_tree"},
            {"key": "MoveTarget", "type": "Vector3", "source": "navmesh"},
        ],
        "tree": {
            "root": "root_selector",
            "tick_interval_seconds": 0.25,
            "nodes": nodes,
            "transitions": [
                {
                    "from": "check_low_health",
                    "to": "retreat_to_cover",
                    "condition": "SelfHealth < 35 or ThreatLevel >= 0.8",
                },
                {
                    "from": "check_target_visible",
                    "to": "warn_target",
                    "condition": "TargetActor is visible",
                },
                {
                    "from": "check_quest_flag",
                    "to": "offer_context_hint",
                    "condition": "QuestFlags contains required flag",
                },
            ],
        },
        "unity_mapping": {
            "component": "LudensBehaviorTreeRunner",
            "blackboardAsset": f"Assets/LudensFlow/Generated/{class_name}Blackboard.asset",
            "treeAsset": f"Assets/LudensFlow/Generated/{class_name}BehaviorTree.json",
            "tickIntervalSeconds": 0.25,
            "csharpSnippet": _behavior_tree_csharp(class_name, scene["id"]),
        },
        "llm_prompt_contract": {
            "system_prompt": scene["systemPrompt"],
            "input_fields": ["character_name", "goal", "context", "traits", "constraints"],
            "output_format": "Strict JSON with blackboard, tree.nodes, tree.transitions, unity_mapping.",
        },
        "validation": {
            "max_depth": 5,
            "requires_human_review": ["combat_action_side_effects", "state_write_tools"],
        },
    }


def generate_questline(request: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(request or {})
    scene = payload.get("scene") if isinstance(payload.get("scene"), dict) else None
    scene = _normalize_scene(scene) if scene else _scene_by_id(payload.get("scene_id") or "questline-generator")
    theme = _trim_text(payload.get("theme"), "区域危机", limit=100)
    region = _trim_text(payload.get("region"), "当前区域", limit=80)
    player_level = int(payload.get("player_level") or 1)
    beats = _as_list(
        payload.get("beats"),
        fallback=["侦查线索", "救援关键 NPC", "破坏敌方补给", "解决首领冲突"],
        limit=6,
    )
    if len(beats) < 3:
        beats.extend(["推进冲突", "完成收束"][: 3 - len(beats)])

    quests: list[dict[str, Any]] = []
    for index, beat in enumerate(beats[:5]):
        quest_id = f"q{index + 1}_{re.sub(r'[^a-zA-Z0-9]+', '_', beat).strip('_') or 'step'}"
        depends_on = [quests[-1]["id"]] if quests else []
        quests.append(
            {
                "id": quest_id,
                "title": f"{theme}：{beat}",
                "depends_on": depends_on,
                "recommended_level": max(1, player_level + index - 1),
                "region": region,
                "objectives": [
                    {
                        "id": f"{quest_id}_objective_primary",
                        "type": "investigate" if index == 0 else "complete_action",
                        "description": f"围绕“{beat}”完成主目标并记录任务状态。",
                        "required_count": 1,
                    },
                    {
                        "id": f"{quest_id}_objective_context",
                        "type": "collect_context",
                        "description": "收集至少一条可用于 NPC 对话或后续任务分支的上下文线索。",
                        "required_count": 1,
                    },
                ],
                "success_state": f"{quest_id}_completed",
                "failure_state": f"{quest_id}_failed",
                "rewards": {
                    "xp": 180 + index * 60,
                    "gold": 80 + index * 35,
                    "flags": [f"{quest_id}_unlocked"],
                },
            }
        )

    return {
        "artifact_type": "questline",
        "scene_id": scene["id"],
        "questline_id": f"questline_{re.sub(r'[^a-zA-Z0-9]+', '_', theme).strip('_') or 'runtime'}",
        "title": theme,
        "summary": f"面向 {region}、玩家等级 {player_level} 的运行时任务线。",
        "quests": quests,
        "runtime_variables": [
            {"key": "quest_state", "type": "map<string,string>", "scope": "player"},
            {"key": "objective_progress", "type": "map<string,int>", "scope": "player"},
            {"key": "region_tension", "type": "float", "scope": "world"},
            {"key": "npc_memory_flags", "type": "string[]", "scope": "actor"},
        ],
        "server_contract": {
            "base_path": "/runtime/quests",
            "events": [
                "start_quest",
                "complete_objective",
                "fail_quest",
                "claim_reward",
            ],
            "required_payload_fields": ["player_id", "quest_id", "objective_id", "timestamp"],
        },
        "unity_mapping": {
            "component": "LudensQuestlineRunner",
            "assetPath": "Assets/LudensFlow/Generated/Questlines",
            "csharpSnippet": _questline_csharp(),
        },
        "llm_prompt_contract": {
            "system_prompt": scene["systemPrompt"],
            "output_format": "Strict JSON with quests, dependencies, objectives, rewards, runtime_variables, server_contract.",
        },
    }


def build_multimodal_plan(request: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(request or {})
    purpose = _trim_text(
        payload.get("purpose"),
        "分析玩家运行时截图、语音和视频，输出调试线索。",
        limit=500,
    )
    requested_modalities = _as_list(
        payload.get("modalities"),
        fallback=["image", "audio", "video"],
        limit=3,
    )
    modalities = [item for item in requested_modalities if item in ALLOWED_MODALITIES]
    if not modalities:
        modalities = ["image", "audio", "video"]

    specs = {
        "image": {
            "runtime_capture": "screenshot_or_uploaded_asset",
            "preprocessing": ["resize_long_edge_1600", "strip_metadata", "ui_region_optional"],
            "limits": {"max_files": 4, "max_megabytes": 8},
        },
        "audio": {
            "runtime_capture": "microphone_clip_or_feedback_recording",
            "preprocessing": ["normalize_volume", "transcribe_if_needed", "strip_speaker_id"],
            "limits": {"max_seconds": 60, "max_megabytes": 12},
        },
        "video": {
            "runtime_capture": "playtest_clip",
            "preprocessing": ["sample_keyframes", "extract_short_audio", "compress_720p"],
            "limits": {"max_seconds": 90, "max_megabytes": 80},
        },
    }
    inputs = [{"modality": modality, **deepcopy(specs[modality])} for modality in modalities]

    return {
        "artifact_type": "multimodal_plan",
        "scene_id": _trim_text(payload.get("scene_id"), "multimodal-runtime", limit=100),
        "purpose": purpose,
        "inputs": inputs,
        "permissions": [
            "player_consent",
            "debug_session_only",
            "no_face_or_voice_identity_storage",
            "project_tool_allowlist",
        ],
        "pipeline": [
            {"step": "capture", "owner": "game_client", "output": "attachments"},
            {"step": "sanitize", "owner": "runtime_gateway", "output": "safe_payload"},
            {"step": "analyze", "owner": "model_provider", "output": "structured_report"},
            {"step": "review", "owner": "workbench", "output": "debug_tasks"},
        ],
        "test_payload": {
            "player_id": "debug-player",
            "session_id": "local-playtest",
            "attachments": [
                {"type": modality, "uri": f"file://sample.{modality}", "metadata": {"source": "debug"}}
                for modality in modalities
            ],
            "question": purpose,
        },
        "cost_guardrails": {
            "max_analysis_per_session": 3,
            "cache_key": "session_id + attachment_hash",
            "summarize_video_before_llm": "video" in modalities,
        },
    }


def run_runtime_scene_test(request: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(request or {})
    project_id = payload.get("project_id")
    scene = payload.get("scene") if isinstance(payload.get("scene"), dict) else None
    scene = _normalize_scene(scene) if scene else _scene_by_id(payload.get("scene_id"), project_id=project_id)
    user_input = _trim_text(
        payload.get("input") or payload.get("test_input") or payload.get("prompt"),
        scene.get("testInput", ""),
        limit=2000,
    )
    attachments = payload.get("attachments") if isinstance(payload.get("attachments"), list) else []
    live_model = bool(payload.get("live_model"))
    runtime_params = {
        "temperature": scene["temperature"],
        "max_tokens": scene["maxTokens"],
        "tools": scene["tools"],
        "runtime_stage": scene.get("runtimeStage", "ready"),
    }

    if scene.get("runtimeStage") == "coming_soon":
        response: dict[str, Any] = {
            "type": "not_available",
            "message": "This scene is reserved for a coming-soon world model runtime.",
            "world_model": deepcopy(WORLD_MODEL_PLAN),
        }
    elif live_model:
        capability = f"game_model_{scene['category']}"
        cfg = resolve_model_config(
            project_id=project_id,
            agent_key="runtime",
            capability=capability,
            default_route={
                "model": scene["modelId"],
                "temperature": scene["temperature"],
            },
        )
        if not cfg.api_key and cfg.provider != "ollama":
            response = {
                "type": "live_model_unavailable",
                "message": "Live model test requires a configured API key or local provider.",
                "provider": cfg.provider,
                "model": cfg.model,
            }
        else:
            text = generate_llm(
                system=scene["systemPrompt"],
                user=user_input,
                cfg=cfg,
            )
            response = {
                "type": "llm_text",
                "text": str(text or "").strip(),
                "provider": cfg.provider,
                "model": cfg.model,
            }
    elif scene["category"] == "multimodal":
        response = {
            "type": "multimodal_report",
            "observations": [
                "已完成图片、语音、视频输入边界检查。",
                "建议先截取关键帧和短音频摘要，再进入模型分析。",
            ],
            "evidence": [
                {"kind": "input", "value": modality}
                for modality in (scene.get("modalities") or ["image", "audio", "video"])
            ],
            "severity": "debug",
            "next_debug_steps": ["确认玩家授权", "压缩附件", "记录 session_id"],
        }
    elif scene["category"] == "quest_behavior":
        response = {
            "type": "structured_logic_preview",
            "summary": "运行时测试已生成结构化逻辑预览，可继续生成行为树或任务线工件。",
            "recommended_actions": ["generate_behavior_tree", "generate_questline"],
            "state_reads": ["quest_state", "perception", "region_tension"],
        }
    else:
        response = {
            "type": "dialogue_turn",
            "speaker": scene["name"],
            "text": "我会按当前场景规则回应，并只使用已授权的运行时工具。",
            "emotion": "neutral",
            "suggested_animation": "idle_talk",
            "quest_flags": [],
        }

    estimated_input_tokens = max(1, len(scene["systemPrompt"]) // 4 + len(user_input) // 4)
    estimated_output_tokens = min(scene["maxTokens"], 160)
    return {
        "artifact_type": "runtime_test_result",
        "scene_id": scene["id"],
        "scene_name": scene["name"],
        "request": {
            "system_prompt": scene["systemPrompt"],
            "input": user_input,
            "attachments": attachments,
            "tools": scene["tools"],
            "runtime_params": runtime_params,
        },
        "response": response,
        "debug": {
            "mode": (
                "live_model"
                if live_model and response.get("type") == "llm_text"
                else "live_model_unavailable"
                if live_model
                else "deterministic_runtime_preview"
            ),
            "model": response.get("model") or scene["modelId"],
            "estimated_input_tokens": estimated_input_tokens,
            "estimated_output_tokens": estimated_output_tokens,
            "tool_policy": "allowlisted_tools_only",
            "tool_calls_preview": [
                {"tool": tool, "status": "available_for_runtime_gateway"}
                for tool in scene["tools"]
            ],
        },
    }


def build_runtime_export(request: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(request or {})
    project_id = _resolve(payload.get("project_id"))
    state = build_runtime_state(project_id=project_id, scenes=payload.get("scenes"))
    requested_ids = set(_as_list(payload.get("scene_ids"), fallback=[], limit=20))
    scenes = [
        scene
        for scene in state["scenes"]
        if scene.get("runtimeStage") != "coming_soon"
        and (not requested_ids or scene["id"] in requested_ids)
    ]
    if not scenes:
        scenes = [scene for scene in state["scenes"] if scene.get("runtimeStage") != "coming_soon"][:1]

    runtime_config = {
        "schema_version": RUNTIME_SCHEMA_VERSION,
        "project_id": project_id,
        "gateway": {
            "base_url": "https://your-game-runtime.example.com",
            "invoke_path": "/runtime/invoke",
            "feedback_path": "/runtime/debug-events",
        },
        "scenes": [
            {
                "id": scene["id"],
                "name": scene["name"],
                "category": scene["category"],
                "model": scene["modelId"],
                "temperature": scene["temperature"],
                "max_tokens": scene["maxTokens"],
                "tools": scene["tools"],
                "output_contract": scene["outputContract"],
            }
            for scene in scenes
        ],
        "guardrails": state["guardrails"],
    }
    rest_contract = {
        "endpoints": [
            "/runtime/invoke",
            "/runtime/quests/events",
            "/runtime/behavior-tree/tick",
            "/runtime/multimodal/analyze",
            "/runtime/debug-events",
        ],
        "auth": "Bearer token with project-scoped runtime permission",
        "request_shape": {
            "scene_id": "string",
            "actor_id": "string optional",
            "player_id": "string optional",
            "input": "text or structured payload",
            "attachments": "optional multimodal attachment list",
        },
        "response_shape": {
            "artifact_type": "dialogue_turn | behavior_tree | questline | multimodal_report",
            "content": "structured JSON",
            "debug": "token usage, model id, tool calls",
        },
    }
    files = {
        "runtime_config.json": json.dumps(runtime_config, ensure_ascii=False, indent=2),
        "LudensFlowRuntimeClient.cs": _runtime_client_csharp(),
        "LudensFlowAgentBinder.cs": _agent_binder_csharp(),
        "README_runtime_contract.md": _runtime_readme(runtime_config, rest_contract),
    }
    return {
        "artifact_type": "runtime_export_bundle",
        "project_id": project_id,
        "runtime_config": runtime_config,
        "rest_contract": rest_contract,
        "files": files,
        "deployment_checklist": [
            "Unity: import LudensFlowRuntimeClient.cs and bind runtime_config.json as a TextAsset.",
            "Server: expose REST endpoints and enforce project-scoped auth.",
            "Tools: register only the tools listed in each scene config.",
            "Debug: forward runtime logs to /runtime/debug-events for workbench iteration.",
        ],
    }


def _behavior_tree_csharp(class_name: str, scene_id: str) -> str:
    return f"""using UnityEngine;

public sealed class {class_name}BehaviorBinder : MonoBehaviour
{{
    [SerializeField] private TextAsset behaviorTreeJson;
    [SerializeField] private LudensBehaviorTreeRunner runner;

    private void Awake()
    {{
        runner.Load("{scene_id}", behaviorTreeJson.text);
    }}
}}"""


def _questline_csharp() -> str:
    return """using UnityEngine;

public sealed class LudensQuestlineBinder : MonoBehaviour
{
    [SerializeField] private TextAsset questlineJson;
    [SerializeField] private LudensQuestlineRunner runner;

    private void Start()
    {
        runner.LoadQuestline(questlineJson.text);
    }
}"""


def _runtime_client_csharp() -> str:
    return """using System.Net.Http;
using System.Text;
using System.Threading.Tasks;
using UnityEngine;

public sealed class LudensFlowRuntimeClient
{
    private readonly HttpClient http = new HttpClient();
    private readonly string baseUrl;
    private readonly string token;

    public LudensFlowRuntimeClient(string baseUrl, string token)
    {
        this.baseUrl = baseUrl.TrimEnd('/');
        this.token = token;
    }

    public async Task<string> InvokeAsync(string sceneId, string jsonPayload)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, baseUrl + "/runtime/invoke");
        request.Headers.Add("Authorization", "Bearer " + token);
        request.Content = new StringContent(jsonPayload, Encoding.UTF8, "application/json");
        using var response = await http.SendAsync(request);
        var body = await response.Content.ReadAsStringAsync();
        if (!response.IsSuccessStatusCode)
        {
            Debug.LogError($"LudensFlow runtime call failed for {sceneId}: {body}");
        }
        return body;
    }
}"""


def _agent_binder_csharp() -> str:
    return """using UnityEngine;

public sealed class LudensFlowAgentBinder : MonoBehaviour
{
    [SerializeField] private TextAsset runtimeConfig;
    [SerializeField] private string runtimeBaseUrl = "https://your-game-runtime.example.com";
    [SerializeField] private string runtimeToken = "PROJECT_RUNTIME_TOKEN";

    private LudensFlowRuntimeClient client;

    private void Awake()
    {
        client = new LudensFlowRuntimeClient(runtimeBaseUrl, runtimeToken);
    }

    public async void SendRuntimeEvent(string sceneId, string jsonPayload)
    {
        var response = await client.InvokeAsync(sceneId, jsonPayload);
        Debug.Log(response);
    }
}"""


def _runtime_readme(runtime_config: dict[str, Any], rest_contract: dict[str, Any]) -> str:
    scene_lines = "\n".join(
        f"- {scene['id']} ({scene['category']}): {scene['model']}"
        for scene in runtime_config["scenes"]
    )
    endpoint_lines = "\n".join(f"- {endpoint}" for endpoint in rest_contract["endpoints"])
    return f"""# Ludens-Flow Runtime Export

## Scenes
{scene_lines}

## REST Endpoints
{endpoint_lines}

## Integration Notes
- Put runtime_config.json under a Unity Resources or Addressables path.
- Keep API tokens server-issued and project-scoped.
- Send debug events back to the workbench after local playtests.
"""

import { fetchJson } from "../workbench/api/http";
import type {
  GameModelExportRequest,
  GameModelGenerationRequest,
  GameModelRuntimeState,
  GameModelRuntimeTestRequest,
  GameSceneConfig,
  RuntimeArtifact,
  RuntimeExportBundle,
} from "./types";

const JSON_HEADERS = { "Content-Type": "application/json" };

export function getGameModelRuntime() {
  return fetchJson<GameModelRuntimeState>("/api/projects/current/game-model/runtime");
}

export function saveGameModelRuntimeScenes(scenes: GameSceneConfig[]) {
  return fetchJson<GameModelRuntimeState>("/api/projects/current/game-model/runtime/scenes", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ scenes }),
  });
}

export function generateGameModelBehaviorTree(body: GameModelGenerationRequest) {
  return fetchJson<RuntimeArtifact>("/api/projects/current/game-model/behavior-tree", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  });
}

export function generateGameModelQuestline(body: GameModelGenerationRequest) {
  return fetchJson<RuntimeArtifact>("/api/projects/current/game-model/questline", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  });
}

export function generateGameModelMultimodalPlan(body: GameModelGenerationRequest) {
  return fetchJson<RuntimeArtifact>("/api/projects/current/game-model/multimodal-plan", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  });
}

export function runGameModelRuntimeTest(body: GameModelRuntimeTestRequest) {
  return fetchJson<RuntimeArtifact>("/api/projects/current/game-model/runtime/test", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  });
}

export function exportGameModelRuntime(body: GameModelExportRequest) {
  return fetchJson<RuntimeExportBundle>("/api/projects/current/game-model/export", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  });
}

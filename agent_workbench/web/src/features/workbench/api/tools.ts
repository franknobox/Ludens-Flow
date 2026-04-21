import type { ToolsResponse } from "../types";
import { fetchJson } from "./http";

export function getTools() {
  return fetchJson<ToolsResponse>("/api/tools");
}

import { fetchJson } from "../../workbench/api/http";
import type { DesignCopywritingRequest, DesignCopywritingResponse } from "../types";

export function generateDesignCopywriting(body: DesignCopywritingRequest) {
  return fetchJson<DesignCopywritingResponse>("/api/projects/current/copywriting/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

import { fetchJson } from "../../workbench/api/http";
import type { DesignCopywritingRequest, DesignCopywritingResponse } from "../types";

const COPYWRITING_REQUEST_TIMEOUT_MS = 130000;

export interface DesignCopywritingJobStartResponse {
  job_id: string;
  status: string;
}

export function startDesignCopywritingJob(body: DesignCopywritingRequest) {
  return fetchJson<DesignCopywritingJobStartResponse>(
    "/api/projects/current/copywriting/jobs",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
}

export function generateDesignCopywriting(body: DesignCopywritingRequest) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(
    () => controller.abort(),
    COPYWRITING_REQUEST_TIMEOUT_MS,
  );

  return fetchJson<DesignCopywritingResponse>("/api/projects/current/copywriting/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: controller.signal,
  }).finally(() => window.clearTimeout(timeoutId));
}

import type { ChatResponse, ComposerAttachment, StateResponse } from "../types";
import { fetchJson } from "./http";

export function getState() {
  return fetchJson<StateResponse>("/api/state");
}

export function postChat(body: {
  message: string;
  attachments?: Array<{
    kind: ComposerAttachment["kind"];
    name: string;
    mime_type: string;
    data_url: string;
    size: number;
  }>;
}) {
  return fetchJson<ChatResponse>("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function postAction(action: string) {
  return fetchJson<ChatResponse>("/api/actions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  });
}

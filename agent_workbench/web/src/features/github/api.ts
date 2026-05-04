import { fetchJson } from "../workbench/api/http";
import type { GithubState } from "./types";

export function getProjectGithubState() {
  return fetchJson<GithubState>("/api/projects/current/github");
}

export function bindProjectGithubRepo(repo: string) {
  return fetchJson<GithubState>("/api/projects/current/github/bind", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repo }),
  });
}

export function unbindProjectGithubRepo() {
  return fetchJson<GithubState>("/api/projects/current/github/bind", {
    method: "DELETE",
  });
}

export interface GithubBranch {
  name: string;
  is_default: boolean;
  is_protected: boolean;
  last_commit: string;
  last_commit_time: string;
}

export interface GithubCommit {
  sha: string;
  short_sha: string;
  message: string;
  author: string;
  timestamp: string;
  branch: string;
  url?: string;
}

export interface GithubPR {
  id: number;
  number: number;
  title: string;
  state: "open" | "closed" | "merged";
  author: string;
  source_branch: string;
  target_branch: string;
  created_at: string;
  updated_at: string;
  review_decision?: "approved" | "changes_requested" | "pending";
  checks_status?: "success" | "failure" | "pending" | "running" | "unknown";
  url?: string;
}

export interface GithubRepoInfo {
  owner: string;
  repo: string;
  default_branch: string;
  description?: string;
  url?: string;
  private?: boolean;
  stars?: number;
  forks?: number;
  open_issues_count?: number;
}

export interface GithubIssue {
  id: number;
  number: number;
  title: string;
  state: string;
  author: string;
  updated_at: string;
  labels: string[];
  url?: string;
}

export interface GithubWorkflowRun {
  id: number;
  name: string;
  status: string;
  conclusion: string;
  branch: string;
  event: string;
  updated_at: string;
  url?: string;
}

export interface GithubSummary {
  branch_count?: number;
  recent_commit_count?: number;
  open_pr_count?: number;
  open_issue_count?: number;
  failing_ci_count?: number;
  active_authors?: string[];
}

export type GithubViewTab = "overview" | "issues" | "pulls" | "commits" | "ci";

export interface GithubState {
  project_id: string;
  configured: boolean;
  repo: GithubRepoInfo | null;
  summary: GithubSummary;
  branches: GithubBranch[];
  commits: GithubCommit[];
  pull_requests: GithubPR[];
  issues: GithubIssue[];
  workflow_runs: GithubWorkflowRun[];
  errors: string[];
  fetched_at: string;
  auth?: { token_configured?: boolean };
}

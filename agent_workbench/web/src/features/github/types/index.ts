export interface GithubBranch {
  name: string;
  isDefault: boolean;
  isProtected: boolean;
  lastCommit: string;
  lastCommitTime: string;
}

export interface GithubCommit {
  sha: string;
  shortSha: string;
  message: string;
  author: string;
  authorAvatar?: string;
  timestamp: string;
  branch: string;
}

export interface GithubCommitNode {
  sha: string;
  message: string;
  author: string;
  timestamp: string;
  parents: string[];
}

export interface GithubPR {
  id: number;
  number: number;
  title: string;
  state: "open" | "closed" | "merged";
  author: string;
  authorAvatar?: string;
  sourceBranch: string;
  targetBranch: string;
  createdAt: string;
  updatedAt: string;
  additions: number;
  deletions: number;
  reviewDecision?: "approved" | "changes_requested" | "pending";
  checksStatus?: "success" | "failure" | "pending" | "running";
}

export interface GithubRepoInfo {
  owner: string;
  repo: string;
  defaultBranch: string;
  description?: string;
}

export type GithubViewTab = "branches" | "commits" | "pulls";

export interface GithubState {
  repoInfo: GithubRepoInfo | null;
  branches: GithubBranch[];
  commits: GithubCommit[];
  commitGraph: GithubCommitNode[];
  pullRequests: GithubPR[];
  activeTab: GithubViewTab;
  branchFilter: string;
  loading: boolean;
  error: string;
}
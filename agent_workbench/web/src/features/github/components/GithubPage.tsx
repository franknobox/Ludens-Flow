import { useEffect, useMemo, useState, type ReactNode } from "react";

import {
  bindProjectGithubRepo,
  getProjectGithubState,
  unbindProjectGithubRepo,
} from "../api";
import type {
  GithubBranch,
  GithubCommit,
  GithubIssue,
  GithubPR,
  GithubState,
  GithubViewTab,
  GithubWorkflowRun,
} from "../types";
import { useProjectRuntime } from "../../workbench/state/ProjectRuntimeContext";
import { toErrorMessage } from "../../workbench/utils";

const EMPTY_STATE: GithubState = {
  project_id: "",
  configured: false,
  repo: null,
  summary: {},
  branches: [],
  commits: [],
  pull_requests: [],
  issues: [],
  workflow_runs: [],
  errors: [],
  fetched_at: "",
  auth: { token_configured: false },
};

const TABS: { id: GithubViewTab; label: string }[] = [
  { id: "overview", label: "概览" },
  { id: "issues", label: "Issues" },
  { id: "pulls", label: "Pull Requests" },
  { id: "commits", label: "Commits" },
  { id: "ci", label: "CI" },
];

function githubIcon() {
  return (
    <svg className="github-icon" viewBox="0 0 24 24" width="22" height="22" fill="currentColor">
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
    </svg>
  );
}

function formatTime(value?: string) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function reviewLabel(value?: string) {
  if (value === "approved") return "已批准";
  if (value === "changes_requested") return "需修改";
  return "待评审";
}

function checkLabel(value?: string) {
  if (value === "success") return "CI 通过";
  if (value === "failure") return "CI 失败";
  if (value === "running") return "运行中";
  if (value === "pending") return "等待中";
  return "未知";
}

function prStateLabel(value: string) {
  if (value === "merged") return "已合并";
  if (value === "closed") return "已关闭";
  return "打开";
}

function externalLink(url?: string, children?: ReactNode) {
  if (!url) return children || null;
  return (
    <a href={url} target="_blank" rel="noreferrer" className="github-inline-link">
      {children || "打开"}
    </a>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="github-stat-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function BranchItem({ branch }: { branch: GithubBranch }) {
  return (
    <article className={`github-list-item${branch.is_default ? " is-active" : ""}`}>
      <div className="github-list-item-main">
        <div className="github-list-item-row">
          <strong className="github-branch-name">{branch.name}</strong>
          {branch.is_default ? <span className="github-badge">默认</span> : null}
          {branch.is_protected ? (
            <span className="github-badge github-badge-protected">保护</span>
          ) : null}
        </div>
        <div className="github-list-item-meta">
          <span className="github-commit-hash">{branch.last_commit || "-"}</span>
        </div>
      </div>
    </article>
  );
}

function CommitItem({ commit }: { commit: GithubCommit }) {
  return (
    <article className="github-list-item">
      <div className="github-list-item-main">
        <div className="github-list-item-row">
          <span className="github-commit-hash">{commit.short_sha}</span>
          {externalLink(commit.url, <span className="github-commit-message">{commit.message}</span>)}
        </div>
        <div className="github-list-item-meta">
          <span>{commit.author}</span>
          <span className="github-meta-sep">·</span>
          <span className="github-branch-chip">{commit.branch}</span>
          <span className="github-meta-sep">·</span>
          <span>{formatTime(commit.timestamp)}</span>
        </div>
      </div>
    </article>
  );
}

function IssueItem({ issue }: { issue: GithubIssue }) {
  return (
    <article className="github-list-item">
      <div className="github-list-item-main">
        <div className="github-list-item-row">
          <span className="github-pr-number">#{issue.number}</span>
          {externalLink(issue.url, <strong className="github-pr-title">{issue.title}</strong>)}
        </div>
        <div className="github-list-item-meta">
          <span>{issue.author}</span>
          <span className="github-meta-sep">·</span>
          <span>{formatTime(issue.updated_at)}</span>
          {issue.labels.map((label) => (
            <span key={label} className="github-branch-chip">
              {label}
            </span>
          ))}
        </div>
      </div>
    </article>
  );
}

function PRItem({ pr }: { pr: GithubPR }) {
  const stateClass =
    pr.state === "open" ? "github-pr-open" : pr.state === "merged" ? "github-pr-merged" : "github-pr-closed";
  return (
    <article className="github-list-item">
      <div className="github-list-item-main">
        <div className="github-list-item-row">
          <span className={`github-pr-state ${stateClass}`}>{prStateLabel(pr.state)}</span>
          <span className="github-pr-number">#{pr.number}</span>
          {externalLink(pr.url, <strong className="github-pr-title">{pr.title}</strong>)}
        </div>
        <div className="github-list-item-meta">
          <span>{pr.author}</span>
          <span className="github-meta-sep">·</span>
          <span className="github-branch-chip">{pr.source_branch}</span>
          <span className="github-meta-sep">→</span>
          <span className="github-branch-chip">{pr.target_branch}</span>
          <span className="github-meta-sep">·</span>
          <span className={`github-review-badge ${pr.review_decision || "pending"}`}>
            {reviewLabel(pr.review_decision)}
          </span>
          <span className={`github-checks-badge ${pr.checks_status || "pending"}`}>
            {checkLabel(pr.checks_status)}
          </span>
        </div>
      </div>
    </article>
  );
}

function WorkflowRunItem({ run }: { run: GithubWorkflowRun }) {
  const state = run.conclusion || run.status || "unknown";
  const stateClass = state === "success" ? "success" : state === "failure" ? "failure" : "pending";
  return (
    <article className="github-list-item">
      <div className="github-list-item-main">
        <div className="github-list-item-row">
          <span className={`github-checks-badge ${stateClass}`}>{checkLabel(state)}</span>
          {externalLink(run.url, <strong className="github-pr-title">{run.name}</strong>)}
        </div>
        <div className="github-list-item-meta">
          <span className="github-branch-chip">{run.branch || "-"}</span>
          <span className="github-meta-sep">·</span>
          <span>{run.event || "-"}</span>
          <span className="github-meta-sep">·</span>
          <span>{formatTime(run.updated_at)}</span>
        </div>
      </div>
    </article>
  );
}

export function GithubPage() {
  const { runtimeState } = useProjectRuntime();
  const [activeTab, setActiveTab] = useState<GithubViewTab>("overview");
  const [repoInput, setRepoInput] = useState("");
  const [state, setState] = useState<GithubState>(EMPTY_STATE);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errorText, setErrorText] = useState("");

  const projectId = runtimeState?.project_id || "";

  const repoTitle = state.repo ? `${state.repo.owner}/${state.repo.repo}` : "未绑定 GitHub 仓库";

  const load = async () => {
    setLoading(true);
    setErrorText("");
    try {
      const next = await getProjectGithubState();
      setState(next);
      if (next.repo) {
        setRepoInput(`${next.repo.owner}/${next.repo.repo}`);
      }
    } catch (error) {
      setErrorText(toErrorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [projectId]);

  const bindRepo = async () => {
    const repo = repoInput.trim();
    if (!repo) {
      setErrorText("请输入 GitHub 仓库，例如 franknobox/Ludens-Flow。");
      return;
    }
    setSubmitting(true);
    setErrorText("");
    try {
      setState(await bindProjectGithubRepo(repo));
    } catch (error) {
      setErrorText(toErrorMessage(error));
    } finally {
      setSubmitting(false);
    }
  };

  const unbindRepo = async () => {
    if (!window.confirm("要解除当前项目绑定的 GitHub 仓库吗？")) return;
    setSubmitting(true);
    setErrorText("");
    try {
      setState(await unbindProjectGithubRepo());
      setRepoInput("");
    } catch (error) {
      setErrorText(toErrorMessage(error));
    } finally {
      setSubmitting(false);
    }
  };

  const summary = state.summary || {};
  const latestCommit = state.commits[0];
  const authors = useMemo(() => summary.active_authors || [], [summary.active_authors]);

  return (
    <div className="github-page">
      <header className="github-header">
        <div className="github-header-left">
          {githubIcon()}
          <div>
            <div className="github-repo-name">{repoTitle}</div>
            <div className="github-subtitle">PM Agent 子能力 · 只读协作视图</div>
          </div>
        </div>
        <div className="github-header-right">
          <span className="github-auth-chip">
            {state.auth?.token_configured ? "Token 已配置" : "公开访问"}
          </span>
          <button type="button" className="github-action-btn" onClick={() => void load()} disabled={loading}>
            {loading ? "刷新中..." : "刷新"}
          </button>
        </div>
      </header>

      <section className="github-bind-panel">
        <div className="github-bind-copy">
          <strong>绑定当前项目仓库</strong>
          <span>支持 owner/repo 或 github.com 仓库地址。当前版本只读取协作状态，不执行写入。</span>
        </div>
        <div className="github-bind-form">
          <input
            className="github-filter-input github-bind-input"
            value={repoInput}
            onChange={(event) => setRepoInput(event.target.value)}
            placeholder="例如 franknobox/Ludens-Flow"
            disabled={submitting}
          />
          <button type="button" className="github-action-btn primary" onClick={() => void bindRepo()} disabled={submitting}>
            {submitting ? "绑定中..." : "绑定并读取"}
          </button>
          {state.configured ? (
            <button type="button" className="github-action-btn" onClick={() => void unbindRepo()} disabled={submitting}>
              解除绑定
            </button>
          ) : null}
        </div>
      </section>

      <nav className="github-tabs">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`github-tab${activeTab === tab.id ? " is-active" : ""}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <div className="github-content">
        {!state.configured ? (
          <div className="github-empty-state">
            <strong>当前项目还没有绑定 GitHub 仓库。</strong>
            <span>绑定后会显示 Issues、Pull Requests、最近提交和 CI 运行状态。</span>
          </div>
        ) : null}

        {errorText ? <div className="github-message danger">{errorText}</div> : null}
        {state.errors?.length ? (
          <div className="github-message">
            部分数据读取失败：{state.errors.slice(0, 2).join("；")}
          </div>
        ) : null}

        {state.configured && activeTab === "overview" ? (
          <section className="github-section">
            <div className="github-stat-grid">
              <StatCard label="分支" value={summary.branch_count || 0} />
              <StatCard label="近期提交" value={summary.recent_commit_count || 0} />
              <StatCard label="打开 PR" value={summary.open_pr_count || 0} />
              <StatCard label="打开 Issue" value={summary.open_issue_count || 0} />
              <StatCard label="异常 CI" value={summary.failing_ci_count || 0} />
            </div>
            <div className="github-overview-split-3col">
              <div className="github-section-panel">
                <div className="github-section-title">研发节奏</div>
                <div className="github-list">
                  {latestCommit ? <CommitItem commit={latestCommit} /> : <div className="github-empty-state compact">暂无提交数据</div>}
                  <div className="github-list-item">
                    <div className="github-list-item-main">
                      <div className="github-list-item-row">
                        <strong className="github-pr-title">活跃成员</strong>
                      </div>
                      <div className="github-list-item-meta">
                        {authors.length ? authors.join("、") : "暂无"}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="github-section-panel">
                <div className="github-section-title">版本拓扑树 (Version Topology)</div>
                <div className="github-graph-container">
                  <svg className="github-graph-svg" viewBox="0 0 800 300" preserveAspectRatio="xMidYMid meet">
                    <defs>
                      <linearGradient id="main-branch" x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0%" stopColor="#81a1c1" />
                        <stop offset="100%" stopColor="#5e81ac" />
                      </linearGradient>
                      <linearGradient id="dev-branch" x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0%" stopColor="#a3be8c" />
                        <stop offset="100%" stopColor="#8fbcbb" />
                      </linearGradient>
                      <linearGradient id="feat-branch" x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0%" stopColor="#b48ead" />
                        <stop offset="100%" stopColor="#d08770" />
                      </linearGradient>
                    </defs>
                    
                    {/* Main Branch Line */}
                    <path d="M 50 150 L 750 150" fill="none" stroke="url(#main-branch)" strokeWidth="6" strokeLinecap="round" />
                    
                    {/* Dev Branch Line */}
                    <path d="M 150 150 C 200 150, 200 80, 250 80 L 600 80 C 650 80, 650 150, 700 150" fill="none" stroke="url(#dev-branch)" strokeWidth="4" strokeLinecap="round" strokeDasharray="8 4" />
                    
                    {/* Feat Branch Line */}
                    <path d="M 300 80 C 330 80, 330 220, 360 220 L 500 220 C 530 220, 530 80, 560 80" fill="none" stroke="url(#feat-branch)" strokeWidth="4" strokeLinecap="round" />
                    
                    {/* Main Commits */}
                    <circle cx="50" cy="150" r="10" fill="#eceff4" stroke="#5e81ac" strokeWidth="4" />
                    <circle cx="150" cy="150" r="10" fill="#eceff4" stroke="#5e81ac" strokeWidth="4" />
                    <circle cx="700" cy="150" r="10" fill="#eceff4" stroke="#5e81ac" strokeWidth="4" />
                    <circle cx="750" cy="150" r="14" fill="#5e81ac" stroke="#eceff4" strokeWidth="3" />
                    
                    {/* Dev Commits */}
                    <circle cx="250" cy="80" r="8" fill="#eceff4" stroke="#8fbcbb" strokeWidth="3" />
                    <circle cx="300" cy="80" r="8" fill="#eceff4" stroke="#8fbcbb" strokeWidth="3" />
                    <circle cx="450" cy="80" r="8" fill="#eceff4" stroke="#8fbcbb" strokeWidth="3" />
                    <circle cx="560" cy="80" r="8" fill="#eceff4" stroke="#8fbcbb" strokeWidth="3" />
                    <circle cx="600" cy="80" r="8" fill="#eceff4" stroke="#8fbcbb" strokeWidth="3" />
                    
                    {/* Feat Commits */}
                    <circle cx="360" cy="220" r="8" fill="#eceff4" stroke="#b48ead" strokeWidth="3" />
                    <circle cx="420" cy="220" r="8" fill="#eceff4" stroke="#b48ead" strokeWidth="3" />
                    <circle cx="500" cy="220" r="8" fill="#eceff4" stroke="#b48ead" strokeWidth="3" />
                    
                    {/* Labels */}
                    <text x="50" y="180" fontFamily="sans-serif" fontSize="14" fill="#4c566a" fontWeight="bold">v1.0</text>
                    <text x="750" y="180" fontFamily="sans-serif" fontSize="14" fill="#4c566a" fontWeight="bold">main</text>
                    <text x="600" y="60" fontFamily="sans-serif" fontSize="14" fill="#4c566a" fontWeight="bold">dev</text>
                    <text x="420" y="250" fontFamily="sans-serif" fontSize="14" fill="#4c566a" fontWeight="bold">feat/w1-baseline</text>
                    
                    {/* Commit Hashes */}
                    <text x="250" y="55" fontFamily="monospace" fontSize="12" fill="#90a4ae">c07aaef</text>
                    <text x="420" y="200" fontFamily="monospace" fontSize="12" fill="#90a4ae">86f1441</text>
                    <text x="700" y="125" fontFamily="monospace" fontSize="12" fill="#90a4ae">cb2e3db</text>
                  </svg>
                </div>
              </div>

              <div className="github-section-panel">
                <div className="github-section-title">分支概览</div>
                <div className="github-list">
                  {state.branches.slice(0, 6).map((branch) => (
                    <BranchItem key={branch.name} branch={branch} />
                  ))}
                </div>
              </div>
            </div>
          </section>
        ) : null}

        {state.configured && activeTab === "issues" ? (
          <section className="github-section">
            <div className="github-list">
              {state.issues.length ? state.issues.map((issue) => <IssueItem key={issue.id} issue={issue} />) : <div className="github-empty-state compact">暂无打开的 Issue</div>}
            </div>
          </section>
        ) : null}

        {state.configured && activeTab === "pulls" ? (
          <section className="github-section">
            <div className="github-list">
              {state.pull_requests.length ? state.pull_requests.map((pr) => <PRItem key={pr.id} pr={pr} />) : <div className="github-empty-state compact">暂无 Pull Request</div>}
            </div>
          </section>
        ) : null}

        {state.configured && activeTab === "commits" ? (
          <section className="github-section">
            <div className="github-list">
              {state.commits.length ? state.commits.map((commit) => <CommitItem key={commit.sha} commit={commit} />) : <div className="github-empty-state compact">暂无提交数据</div>}
            </div>
          </section>
        ) : null}

        {state.configured && activeTab === "ci" ? (
          <section className="github-section">
            <div className="github-list">
              {state.workflow_runs.length ? state.workflow_runs.map((run) => <WorkflowRunItem key={run.id} run={run} />) : <div className="github-empty-state compact">暂无 CI 运行记录</div>}
            </div>
          </section>
        ) : null}
      </div>
    </div>
  );
}

import { useState } from "react";

import type {
  GithubBranch,
  GithubCommit,
  GithubCommitNode,
  GithubPR,
  GithubState,
  GithubViewTab,
} from "../types";

const MOCK_BRANCHES: GithubBranch[] = [
  { name: "main", isDefault: true, isProtected: true, lastCommit: "a1b2c3d", lastCommitTime: "2小时前" },
  { name: "dev", isDefault: false, isProtected: false, lastCommit: "e4f5g6h", lastCommitTime: "昨天" },
  { name: "feat/gameplay-systems", isDefault: false, isProtected: false, lastCommit: "i7j8k9l", lastCommitTime: "3天前" },
  { name: "fix/collision-bug", isDefault: false, isProtected: false, lastCommit: "m0n1o2p", lastCommitTime: "5天前" },
];

const MOCK_COMMITS: GithubCommit[] = [
  { sha: "a1b2c3d", shortSha: "a1b2c3d", message: "feat: 实现基础移动系统", author: "张三", timestamp: "2小时前", branch: "main" },
  { sha: "e4f5g6h", shortSha: "e4f5g6h", message: "refactor: 重构角色控制器结构", author: "李四", timestamp: "昨天", branch: "dev" },
  { sha: "i7j8k9l", shortSha: "i7j8k9l", message: "feat: 添加天气系统", author: "张三", timestamp: "3天前", branch: "feat/gameplay-systems" },
  { sha: "m0n1o2p", shortSha: "m0n1o2p", message: "fix: 修复碰撞检测边界问题", author: "王五", timestamp: "5天前", branch: "fix/collision-bug" },
  { sha: "q3r4s5t", shortSha: "q3r4s5t", message: "docs: 更新 README", author: "李四", timestamp: "上周", branch: "main" },
];

const MOCK_PR: GithubPR[] = [
  {
    id: 1,
    number: 12,
    title: "feat: 添加新手引导系统",
    state: "open",
    author: "张三",
    sourceBranch: "feat/new-player-guide",
    targetBranch: "main",
    createdAt: "3天前",
    updatedAt: "1天前",
    additions: 342,
    deletions: 28,
    reviewDecision: "approved",
    checksStatus: "success",
  },
  {
    id: 2,
    number: 11,
    title: "fix: 修复保存数据丢失问题",
    state: "open",
    author: "李四",
    sourceBranch: "fix/save-data-loss",
    targetBranch: "dev",
    createdAt: "1周前",
    updatedAt: "2天前",
    additions: 89,
    deletions: 45,
    reviewDecision: "changes_requested",
    checksStatus: "pending",
  },
  {
    id: 3,
    number: 10,
    title: "refactor: 简化战斗系统逻辑",
    state: "merged",
    author: "王五",
    sourceBranch: "refactor/combat-system",
    targetBranch: "main",
    createdAt: "2周前",
    updatedAt: "1周前",
    additions: 156,
    deletions: 203,
    reviewDecision: "approved",
    checksStatus: "success",
  },
];

const TABS: { id: GithubViewTab; label: string }[] = [
  { id: "branches", label: "分支" },
  { id: "commits", label: "提交记录" },
  { id: "pulls", label: "Pull Requests" },
];

function BranchItem({ branch, isActive }: { branch: GithubBranch; isActive: boolean }) {
  return (
    <div className={`github-list-item${isActive ? " is-active" : ""}`}>
      <div className="github-list-item-main">
        <div className="github-list-item-row">
          <strong className="github-branch-name">
            {branch.isDefault ? "★ " : ""}{branch.name}
          </strong>
          {branch.isProtected ? (
            <span className="github-badge github-badge-protected">保护</span>
          ) : null}
        </div>
        <div className="github-list-item-meta">
          <span className="github-commit-hash">{branch.lastCommit}</span>
          <span className="github-meta-sep">·</span>
          <span>{branch.lastCommitTime}</span>
        </div>
      </div>
    </div>
  );
}

function CommitItem({ commit }: { commit: GithubCommit }) {
  return (
    <div className="github-list-item">
      <div className="github-list-item-main">
        <div className="github-list-item-row">
          <span className="github-commit-hash">{commit.shortSha}</span>
          <span className="github-commit-message">{commit.message}</span>
        </div>
        <div className="github-list-item-meta">
          <span>{commit.author}</span>
          <span className="github-meta-sep">·</span>
          <span className="github-branch-chip">{commit.branch}</span>
          <span className="github-meta-sep">·</span>
          <span>{commit.timestamp}</span>
        </div>
      </div>
    </div>
  );
}

function PRItem({ pr }: { pr: GithubPR }) {
  const stateClass = pr.state === "open" ? "github-pr-open" : pr.state === "merged" ? "github-pr-merged" : "github-pr-closed";
  return (
    <div className="github-list-item">
      <div className="github-list-item-main">
        <div className="github-list-item-row">
          <span className={`github-pr-state ${stateClass}`}>{pr.state === "open" ? "开放" : pr.state === "merged" ? "已合并" : "已关闭"}</span>
          <span className="github-pr-number">#{pr.number}</span>
          <strong className="github-pr-title">{pr.title}</strong>
        </div>
        <div className="github-list-item-meta">
          <span>{pr.author}</span>
          <span className="github-meta-sep">·</span>
          <span className="github-branch-chip">{pr.sourceBranch}</span>
          <span className="github-meta-sep">→</span>
          <span className="github-branch-chip">{pr.targetBranch}</span>
          <span className="github-meta-sep">·</span>
          <span>+{pr.additions} -{pr.deletions}</span>
          {pr.reviewDecision ? (
            <>
              <span className="github-meta-sep">·</span>
              <span className={`github-review-badge ${pr.reviewDecision}`}>
                {pr.reviewDecision === "approved" ? "✓ 已批准" : pr.reviewDecision === "changes_requested" ? "✗ 需修改" : "○ 审阅中"}
              </span>
            </>
          ) : null}
          {pr.checksStatus ? (
            <>
              <span className="github-meta-sep">·</span>
              <span className={`github-checks-badge ${pr.checksStatus}`}>
                {pr.checksStatus === "success" ? "✓ 检查通过" : pr.checksStatus === "failure" ? "✗ 检查失败" : pr.checksStatus === "running" ? "⟳ 进行中" : "○ 待检查"}
              </span>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function CommitGraphView({ commits }: { commits: GithubCommit[] }) {
  return (
    <div className="github-commit-graph">
      {commits.map((commit, idx) => (
        <div key={commit.sha} className="github-graph-row">
          <div className="github-graph-lane">
            <div className="github-graph-dot" />
            {idx < commits.length - 1 ? <div className="github-graph-line" /> : null}
          </div>
          <div className="github-graph-content">
            <div className="github-graph-commit">
              <span className="github-commit-hash">{commit.shortSha}</span>
              <span className="github-commit-message">{commit.message}</span>
            </div>
            <div className="github-graph-meta">
              <span>{commit.author}</span>
              <span className="github-meta-sep">·</span>
              <span>{commit.timestamp}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function BranchTreeView({ branches }: { branches: GithubBranch[] }) {
  return (
    <div className="github-branch-tree">
      {branches.map((branch) => (
        <div key={branch.name} className="github-tree-node">
          <div className="github-tree-connector">
            <span className="github-tree-dot" />
            <span className="github-tree-line" />
          </div>
          <div className="github-tree-content">
            <BranchItem branch={branch} isActive={branch.name === "main"} />
          </div>
        </div>
      ))}
    </div>
  );
}

export function GithubPage() {
  const [activeTab, setActiveTab] = useState<GithubViewTab>("branches");
  const [branchFilter, setBranchFilter] = useState("");

  const filteredBranches = MOCK_BRANCHES.filter((b) =>
    b.name.toLowerCase().includes(branchFilter.toLowerCase()),
  );

  return (
    <div className="github-page" style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <header className="github-header">
        <div className="github-header-left">
          <svg className="github-icon" viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
            <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
          </svg>
          <span className="github-repo-name">ludens-flow / main</span>
        </div>
        <div className="github-header-right">
          <button type="button" className="github-action-btn">
            ↻ 同步
          </button>
          <button type="button" className="github-action-btn">
            ⟳ 刷新
          </button>
        </div>
      </header>

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
        {activeTab === "branches" && (
          <div className="github-section">
            <div className="github-section-toolbar">
              <input
                className="github-filter-input"
                type="text"
                placeholder="筛选分支…"
                value={branchFilter}
                onChange={(e) => setBranchFilter(e.target.value)}
              />
            </div>
            <div className="github-section-body">
              <div className="github-section-split">
                <div className="github-section-panel">
                  <div className="github-section-title">列表视图</div>
                  <div className="github-list">
                    {filteredBranches.map((branch) => (
                      <BranchItem key={branch.name} branch={branch} isActive={branch.name === "main"} />
                    ))}
                  </div>
                </div>
                <div className="github-section-panel">
                  <div className="github-section-title">树状结构</div>
                  <BranchTreeView branches={filteredBranches} />
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === "commits" && (
          <div className="github-section">
            <div className="github-section-toolbar">
              <select className="github-filter-select">
                <option value="">所有分支</option>
                {MOCK_BRANCHES.map((b) => (
                  <option key={b.name} value={b.name}>{b.name}</option>
                ))}
              </select>
            </div>
            <div className="github-section-body">
              <div className="github-section-split">
                <div className="github-section-panel">
                  <div className="github-section-title">提交列表</div>
                  <div className="github-list">
                    {MOCK_COMMITS.map((commit) => (
                      <CommitItem key={commit.sha} commit={commit} />
                    ))}
                  </div>
                </div>
                <div className="github-section-panel">
                  <div className="github-section-title">提交图</div>
                  <CommitGraphView commits={MOCK_COMMITS} />
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === "pulls" && (
          <div className="github-section">
            <div className="github-section-toolbar">
              <select className="github-filter-select">
                <option value="">所有状态</option>
                <option value="open">开放</option>
                <option value="merged">已合并</option>
                <option value="closed">已关闭</option>
              </select>
            </div>
            <div className="github-list">
              {MOCK_PR.map((pr) => (
                <PRItem key={pr.id} pr={pr} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
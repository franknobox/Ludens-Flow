import os

# 1. Update CSS
css_file = r'agent_workbench/web/src/styles/layout.css'
with open(css_file, 'r', encoding='utf-8') as f:
    css_content = f.read()

new_css = """
.github-overview-split-3col {
  display: grid;
  grid-template-columns: minmax(180px, 18%) 1fr minmax(180px, 18%);
  gap: 16px;
  align-items: stretch;
}

.github-graph-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: calc(100% - 30px);
  min-height: 220px;
  background: rgba(246, 248, 250, 0.4);
  border-radius: 12px;
  border: 1px dashed rgba(27, 31, 35, 0.15);
  position: relative;
  overflow: hidden;
}

.github-graph-svg {
  width: 100%;
  height: 100%;
  padding: 10px;
}
"""

if '.github-overview-split-3col' not in css_content:
    with open(css_file, 'a', encoding='utf-8') as f:
        f.write("\n" + new_css)


# 2. Update TSX
tsx_file = r'agent_workbench/web/src/features/github/components/GithubPage.tsx'
with open(tsx_file, 'r', encoding='utf-8') as f:
    tsx_content = f.read()

old_block = """            <div className="github-section-split github-overview-split">
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
                <div className="github-section-title">分支概览</div>
                <div className="github-list">
                  {state.branches.slice(0, 6).map((branch) => (
                    <BranchItem key={branch.name} branch={branch} />
                  ))}
                </div>
              </div>
            </div>"""

new_block = """            <div className="github-overview-split-3col">
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
            </div>"""

if old_block in tsx_content:
    tsx_content = tsx_content.replace(old_block, new_block)
    with open(tsx_file, 'w', encoding='utf-8') as f:
        f.write(tsx_content)
    print("TSX updated successfully!")
else:
    print("Failed to find block in TSX")

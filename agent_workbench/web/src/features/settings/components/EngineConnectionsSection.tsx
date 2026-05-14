import { useState } from "react";

import type {
  McpConnectionConfig,
  McpConnectionStatus,
} from "../../workbench/types";

function mcpStatusLabel(status?: McpConnectionStatus): string {
  if (!status) return "已配置";
  if (status.status === "not_configured") return "未配置";
  if (status.status === "configured") return "已配置";
  if (status.status === "reachable") return "可连接";
  if (status.status === "tools_loaded") return "工具列表已加载";
  return "连接失败";
}

function mcpStatusClass(status?: McpConnectionStatus): string {
  if (!status) return "neutral";
  if (status.status === "tools_loaded" || status.status === "reachable") return "ok";
  if (status.status === "failed") return "danger";
  if (status.status === "not_configured") return "muted";
  return "neutral";
}

interface EngineConnectionsSectionProps {
  loading: boolean;
  submitting: boolean;
  checking: boolean;
  connections: McpConnectionConfig[];
  statuses: Record<string, McpConnectionStatus>;
  engineInput: McpConnectionConfig["engine"];
  labelInput: string;
  commandInput: string;
  argsInput: string;
  envInput: string;
  onEngineChange: (value: McpConnectionConfig["engine"]) => void;
  onLabelChange: (value: string) => void;
  onCommandChange: (value: string) => void;
  onArgsChange: (value: string) => void;
  onEnvChange: (value: string) => void;
  onFillEnginePreset: (engine: McpConnectionConfig["engine"]) => void;
  onAddConnection: () => void;
  onUpdateConnection: (
    connectionId: string,
    patch: Partial<McpConnectionConfig>,
  ) => void;
  onRemoveConnection: (connectionId: string) => void;
  onCheckConnection: (connectionId: string) => void;
  onCheckAll: () => void;
}

type EngineGuideKey = Extract<McpConnectionConfig["engine"], "blender" | "unity" | "godot">;

function hasInstallGuide(engine: McpConnectionConfig["engine"]): engine is EngineGuideKey {
  return engine === "blender" || engine === "unity" || engine === "godot";
}

function EngineInstallGuideModal({
  engine,
  onClose,
  onFillPreset,
}: {
  engine: EngineGuideKey;
  onClose: () => void;
  onFillPreset: () => void;
}) {
  const engineName =
    engine === "unity" ? "Unity MCP" : engine === "godot" ? "Godot MCP" : "Blender MCP";

  return (
    <div
      className={`settings-guide-overlay settings-guide-overlay--${engine}`}
      role="dialog"
      aria-modal="true"
    >
      <div className="settings-guide-panel">
        <button
          type="button"
          className="settings-guide-close"
          aria-label={`关闭 ${engineName} 安装指引`}
          onClick={onClose}
        >
          ×
        </button>

        <div className="settings-guide-head">
          <span className="settings-guide-kicker">{engineName}</span>
          <h2>安装指引</h2>
          {engine === "unity" ? (
            <p>
              这一步会把 Unity Editor 和 Ludens-Flow 连接起来。先在 Unity 项目中安装
              MCP for Unity 包并启动编辑器侧服务，再在当前项目里保存 MCP 配置。
            </p>
          ) : null}
          {engine === "godot" ? (
            <p>
              这一步会把 Godot 和 Ludens-Flow 连接起来。Godot MCP 通过本机 Node.js
              命令启动，必要时用 GODOT_PATH 指向你的 Godot 可执行文件。
            </p>
          ) : null}
          {engine === "blender" ? (
            <p>
              这一步会把 Blender 和 Ludens-Flow 连接起来。先完成 Blender 插件安装，
              再在当前项目里保存 MCP 启动配置，最后回到这里做健康检查。
            </p>
          ) : null}
        </div>

        <div className="settings-guide-body">
          {engine === "unity" ? (
            <>
              <section className="settings-guide-step">
                <div className="settings-guide-step-index">1</div>
                <div>
                  <h3>确认本机环境</h3>
                  <p>需要先安装 Unity 2021.3 LTS+、Python 3.10+，并确保已经安装 uv。</p>
                  <p>如果还没有 uv，在 Windows PowerShell 里运行：</p>
                  <pre><code>powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"</code></pre>
                  <p>安装完成后重新打开终端，确认 uv 可用：</p>
                  <pre><code>uv --version</code></pre>
                </div>
              </section>

              <section className="settings-guide-step">
                <div className="settings-guide-step-index">2</div>
                <div>
                  <h3>在 Unity 项目中安装包</h3>
                  <ol>
                    <li>打开目标 Unity 项目。</li>
                    <li>进入 <code>Window / Package Manager</code>。</li>
                    <li>点击 <code>+</code>，选择 <code>Add package from git URL...</code>。</li>
                    <li>填入下面的 Git URL，然后等待 Unity 导入完成。</li>
                  </ol>
                  <pre><code>https://github.com/CoplayDev/unity-mcp.git?path=/MCPForUnity#main</code></pre>
                  <a
                    className="settings-guide-link"
                    href="https://github.com/CoplayDev/unity-mcp"
                    target="_blank"
                    rel="noreferrer"
                  >
                    打开 Unity MCP 仓库
                  </a>
                </div>
              </section>

              <section className="settings-guide-step">
                <div className="settings-guide-step-index">3</div>
                <div>
                  <h3>启动 Unity 编辑器侧服务</h3>
                  <ol>
                    <li>在 Unity 中打开 <code>窗口 / 面板 / MCP For Unity / Toggle MCP Window</code>（快捷键 <code>Ctrl+Shift+M</code>）。</li>
                    <li>在弹出的 MCP 面板中点击 <code>Start Server</code>，确认状态指示灯变绿（Session 建立）。</li>
                    <li>保持默认的 stdio 传输模式即可，无需额外地址配置。</li>
                  </ol>
                </div>
              </section>

              <section className="settings-guide-step">
                <div className="settings-guide-step-index">4</div>
                <div>
                  <h3>在 Ludens-Flow 中保存 MCP 配置</h3>
                  <p>推荐 stdio 模式：启动命令填 <code>cmd</code>，启动参数每行一个填入下方内容。和 Blender MCP 完全一致的连接方式。</p>
                  <button
                    type="button"
                    className="settings-guide-inline-button"
                    onClick={onFillPreset}
                  >
                    一键填入添加表单
                  </button>
                  <div className="settings-guide-config-grid">
                    <div>
                      <span>启动命令</span>
                      <pre><code>cmd</code></pre>
                    </div>
                    <div>
                      <span>启动参数，每行一个</span>
                      <pre><code>{"/c\nuvx\n--from\nmcpforunityserver\nmcp-for-unity"}</code></pre>
                    </div>
                    <div>
                      <span>环境变量</span>
                      <pre><code>（留空）</code></pre>
                    </div>
                  </div>
                </div>
              </section>

              <section className="settings-guide-step">
                <div className="settings-guide-step-index">5</div>
                <div>
                  <h3>回到设置页检查连接</h3>
                  <p>
                    保存配置后点击“检查”。如果能读取工具列表，再去工作台的 Unity MCP
                    页面查看能力映射。
                  </p>
                </div>
              </section>
            </>
          ) : null}

          {engine === "godot" ? (
            <>
              <section className="settings-guide-step">
                <div className="settings-guide-step-index">1</div>
                <div>
                  <h3>确认本机环境</h3>
                  <p>需要先安装 Godot Engine，并确保本机已有 Node.js 18+ 和 npm。</p>
                  <p>在 Windows PowerShell 里可以先检查：</p>
                  <pre><code>node --version{"\n"}npm --version</code></pre>
                </div>
              </section>

              <section className="settings-guide-step">
                <div className="settings-guide-step-index">2</div>
                <div>
                  <h3>确认 Godot 可执行文件</h3>
                  <p>
                    如果 Godot 没有加入 PATH，建议准备好 <code>Godot.exe</code> 的完整路径，
                    后续填入 <code>GODOT_PATH</code> 环境变量。
                  </p>
                  <pre><code>{`GODOT_PATH=E:\\Tools\\Godot\\Godot_v4.4-stable_win64.exe`}</code></pre>
                  <a
                    className="settings-guide-link"
                    href="https://github.com/Coding-Solo/godot-mcp"
                    target="_blank"
                    rel="noreferrer"
                  >
                    打开 Godot MCP 仓库
                  </a>
                </div>
              </section>

              <section className="settings-guide-step">
                <div className="settings-guide-step-index">3</div>
                <div>
                  <h3>在 Ludens-Flow 中保存 MCP 配置</h3>
                  <p>
                    推荐使用 npx 启动。第一次检查时 npm 可能会下载依赖，等待时间会更长。
                    如果 Godot 已加入 PATH，环境变量可以留空；否则把等号后改成你的本机路径。
                  </p>
                  <button
                    type="button"
                    className="settings-guide-inline-button"
                    onClick={onFillPreset}
                  >
                    一键填入添加表单
                  </button>
                  <div className="settings-guide-config-grid">
                    <div>
                      <span>启动命令</span>
                      <pre><code>cmd</code></pre>
                    </div>
                    <div>
                      <span>启动参数，每行一个</span>
                      <pre><code>{"/c\nnpx\n-y\n@coding-solo/godot-mcp"}</code></pre>
                    </div>
                    <div>
                      <span>环境变量</span>
                      <pre><code>GODOT_PATH=</code></pre>
                    </div>
                  </div>
                </div>
              </section>

              <section className="settings-guide-step">
                <div className="settings-guide-step-index">4</div>
                <div>
                  <h3>回到设置页检查连接</h3>
                  <p>
                    保存配置后点击“检查”。如果能读取工具列表，再去工作台的 Godot MCP
                    页面查看能力映射。
                  </p>
                </div>
              </section>
            </>
          ) : null}

          {engine === "blender" ? (
            <>
              <section className="settings-guide-step">
                <div className="settings-guide-step-index">1</div>
                <div>
                  <h3>确认本机环境</h3>
                  <p>需要先安装 Blender 3.0+、Python 3.10+，并确保已经安装 uv。</p>
                  <p>如果还没有 uv，在 Windows PowerShell 里运行：</p>
                  <pre><code>powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"</code></pre>
                  <p>安装完成后重新打开终端，确认 uv 可用：</p>
                  <pre><code>uv --version</code></pre>
                </div>
              </section>

              <section className="settings-guide-step">
                <div className="settings-guide-step-index">2</div>
                <div>
                  <h3>下载 Blender 插件</h3>
                  <p>
                    打开 GitHub 文件页，将 <code>addon.py</code> 下载并保存到本地。
                    也可以用下面的 PowerShell 命令直接保存到下载目录。
                  </p>
                  <pre><code>{`Invoke-WebRequest -Uri "https://raw.githubusercontent.com/ahujasid/blender-mcp/main/addon.py" -OutFile "$env:USERPROFILE\\Downloads\\addon.py"`}</code></pre>
                  <a
                    className="settings-guide-link"
                    href="https://github.com/ahujasid/blender-mcp/blob/main/addon.py"
                    target="_blank"
                    rel="noreferrer"
                  >
                    打开 GitHub 文件页
                  </a>
                </div>
              </section>

              <section className="settings-guide-step">
                <div className="settings-guide-step-index">3</div>
                <div>
                  <h3>在 Blender 中启用插件</h3>
                  <ol>
                    <li>打开 Blender。</li>
                    <li>进入 Edit / Preferences / Add-ons。</li>
                    <li>点击 Install，选择刚下载的 <code>addon.py</code>。</li>
                    <li>启用 <code>Interface: Blender MCP</code>。</li>
                    <li>回到 3D View，按键盘 <code>N</code> 呼出右侧侧边栏。</li>
                    <li>在右侧侧边栏里找到 BlenderMCP 面板，点击连接按钮。</li>
                  </ol>
                </div>
              </section>

              <section className="settings-guide-step">
                <div className="settings-guide-step-index">4</div>
                <div>
                  <h3>在 Ludens-Flow 中保存 MCP 配置</h3>
                  <p>Windows 推荐使用下面这组配置，并默认关闭第三方 telemetry。</p>
                  <button
                    type="button"
                    className="settings-guide-inline-button"
                    onClick={onFillPreset}
                  >
                    一键填入添加表单
                  </button>
                  <div className="settings-guide-config-grid">
                    <div>
                      <span>启动命令</span>
                      <pre><code>cmd</code></pre>
                    </div>
                    <div>
                      <span>启动参数，每行一个</span>
                      <pre><code>{"/c\nuvx\nblender-mcp"}</code></pre>
                    </div>
                    <div>
                      <span>环境变量</span>
                      <pre><code>DISABLE_TELEMETRY=true</code></pre>
                    </div>
                  </div>
                </div>
              </section>

              <section className="settings-guide-step">
                <div className="settings-guide-step-index">5</div>
                <div>
                  <h3>回到设置页检查连接</h3>
                  <p>
                    保存配置后点击“检查”。如果能读取到底层工具列表，再去工作台的
                    Blender MCP 页面查看能力映射。
                  </p>
                </div>
              </section>
            </>
          ) : null}
        </div>

      </div>
    </div>
  );
}

export function EngineConnectionsSection(props: EngineConnectionsSectionProps) {
  const {
    loading,
    submitting,
    checking,
    connections,
    statuses,
    engineInput,
    labelInput,
    commandInput,
    argsInput,
    envInput,
    onEngineChange,
    onLabelChange,
    onCommandChange,
    onArgsChange,
    onEnvChange,
    onFillEnginePreset,
    onAddConnection,
    onUpdateConnection,
    onRemoveConnection,
    onCheckConnection,
    onCheckAll,
  } = props;

  const busy = loading || submitting || checking;
  const [activeGuide, setActiveGuide] = useState<EngineGuideKey | null>(null);
  const configuredEngines = new Set(connections.map((connection) => connection.engine));
  const missingEngines = MCP_ENGINE_OPTIONS.filter(
    (engine) => !configuredEngines.has(engine.value),
  );

  return (
    <>
      {activeGuide ? (
        <EngineInstallGuideModal
          engine={activeGuide}
          onClose={() => setActiveGuide(null)}
          onFillPreset={() => onFillEnginePreset(activeGuide)}
        />
      ) : null}
      <div className="settings-detail-stack settings-detail-stack--fill">
      <section className="settings-pane-card settings-pane-card-main settings-engine-whole">
        <div className="settings-card-head">
          <h2 className="settings-card-title">引擎连接</h2>
          <div className="settings-card-actions">
            <span className="settings-chip">{connections.length} 项</span>
            <button
              type="button"
              className="settings-pill-button"
              disabled={busy || !connections.length}
              onClick={onCheckAll}
            >
              {checking ? "检查中..." : "检查全部"}
            </button>
          </div>
        </div>

        <div className="settings-engine-grid">
          <div className="settings-engine-list">
            {connections.map((connection) => {
                const status = statuses[connection.id];
                const guideEngine = hasInstallGuide(connection.engine) ? connection.engine : null;
                return (
                  <article key={connection.id} className="settings-engine-card">
                    <div className="settings-engine-card-head">
                      <div>
                        <h3>{connection.label}</h3>
                        <span>{connection.engine}</span>
                      </div>
                      <span className={`settings-chip ${mcpStatusClass(status)}`}>
                        {mcpStatusLabel(status)}
                      </span>
                    </div>

                    <div className="settings-engine-command">
                      <code>{connection.command || "未填写启动命令"}</code>
                      {connection.args.length ? (
                        <small>{connection.args.join(" ")}</small>
                      ) : null}
                    </div>

                    {status?.message ? (
                      <p className="settings-engine-message">{status.message}</p>
                    ) : null}

                    {status?.tools?.length ? (
                      <div className="settings-engine-tools">
                        {status.tools.slice(0, 12).map((tool) => (
                          <span key={tool.name} className="settings-chip subtle">
                            {tool.name}
                          </span>
                        ))}
                        {status.tools.length > 12 ? (
                          <span className="settings-chip subtle">
                            +{status.tools.length - 12}
                          </span>
                        ) : null}
                      </div>
                    ) : null}

                    <div className="settings-engine-actions">
                      {guideEngine ? (
                        <button
                          type="button"
                          className="settings-pill-button"
                          onClick={() => setActiveGuide(guideEngine)}
                        >
                          安装指引
                        </button>
                      ) : null}
                      <label className="settings-toggle compact">
                        <input
                          type="checkbox"
                          checked={connection.enabled}
                          disabled={busy}
                          onChange={(event) =>
                            onUpdateConnection(connection.id, {
                              enabled: event.target.checked,
                            })
                          }
                        />
                        <span>启用</span>
                      </label>
                      <button
                        type="button"
                        className="settings-pill-button"
                        disabled={busy || !connection.command}
                        onClick={() => onCheckConnection(connection.id)}
                      >
                        检查
                      </button>
                      <button
                        type="button"
                        className="settings-pill-button danger"
                        disabled={busy}
                        onClick={() => onRemoveConnection(connection.id)}
                      >
                        移除
                      </button>
                    </div>
                  </article>
                );
              })}
            {missingEngines.map((engine) => {
              const guideEngine = hasInstallGuide(engine.value) ? engine.value : null;
              return (
              <article key={engine.value} className="settings-engine-card is-empty">
                <div className="settings-engine-card-head">
                  <div>
                    <h3>{engine.label}</h3>
                    <span>{engine.value}</span>
                  </div>
                  <span className="settings-chip muted">未配置</span>
                </div>
                <p className="settings-engine-message">
                  尚未为当前项目配置 {engine.label} MCP。填写右侧表单后可进行健康检查。
                </p>
                {guideEngine ? (
                  <div className="settings-engine-actions align-right">
                    <button
                      type="button"
                      className="settings-pill-button"
                      onClick={() => setActiveGuide(guideEngine)}
                    >
                      安装指引
                    </button>
                  </div>
                ) : null}
              </article>
              );
            })}
          </div>

          <div className="settings-engine-form">
            <div className="settings-card-head compact">
              <h2 className="settings-card-title">添加 MCP</h2>
            </div>
            <div className="settings-form">
              <label className="settings-field">
                <span>引擎</span>
                <select
                  value={engineInput}
                  disabled={busy}
                  onChange={(event) =>
                    onEngineChange(event.target.value as McpConnectionConfig["engine"])
                  }
                >
                  {MCP_ENGINE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="settings-field">
                <span>显示名称</span>
                <input
                  value={labelInput}
                  disabled={busy}
                  onChange={(event) => onLabelChange(event.target.value)}
                  placeholder="例如：主引擎 MCP"
                />
              </label>
              <label className="settings-field">
                <span>启动命令</span>
                <input
                  value={commandInput}
                  disabled={busy}
                  onChange={(event) => onCommandChange(event.target.value)}
                  placeholder="例如：npx / uv / python"
                />
              </label>
              <label className="settings-field">
                <span>启动参数，每行一个</span>
                <textarea
                  value={argsInput}
                  disabled={busy}
                  onChange={(event) => onArgsChange(event.target.value)}
                  placeholder={"例如：\n@coding-solo/godot-mcp"}
                />
              </label>
              <label className="settings-field">
                <span>环境变量，每行 KEY=VALUE</span>
                <textarea
                  value={envInput}
                  disabled={busy}
                  onChange={(event) => onEnvChange(event.target.value)}
                  placeholder={"例如：\nGODOT_PATH=E:\\Tools\\Godot.exe"}
                />
              </label>
              <button
                type="button"
                className="settings-primary-button"
                disabled={busy}
                onClick={onAddConnection}
              >
                保存连接
              </button>
            </div>
          </div>
        </div>
      </section>
      </div>
    </>
  );
}

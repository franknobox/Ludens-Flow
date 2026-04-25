import { useState } from "react";
import "../styles/game-model.css";

import {
  type GameModel,
  type GameSceneConfig,
  type ModelCategory,
  MODEL_CATEGORIES,
  MOCK_MODELS,
  SCENE_TEMPLATES,
  generateUnitySnippet,
  generateRestApiSnippet,
} from "../types";

type Tab = "models" | "scenes" | "custom" | "export";

function ModelCard({ model, onSelect }: { model: GameModel; onSelect: () => void }) {
  return (
    <div className={`game-model-card${model.status === "coming_soon" ? " is-coming-soon" : ""}`} onClick={model.status !== "coming_soon" ? onSelect : undefined}>
      <div className="game-model-card-head">
        <div className="game-model-card-name-row">
          <strong className="game-model-card-name">{model.name}</strong>
          {model.status === "recommended" ? (
            <span className="game-model-badge recommended">推荐</span>
          ) : model.status === "popular" ? (
            <span className="game-model-badge popular">热门</span>
          ) : (
            <span className="game-model-badge coming-soon">即将上线</span>
          )}
        </div>
        <span className="game-model-card-provider">{model.provider}</span>
      </div>

      <p className="game-model-card-desc">{model.description}</p>

      <div className="game-model-card-categories">
        {model.categories.map((cat) => {
          const catDef = MODEL_CATEGORIES.find((c) => c.id === cat);
          return (
            <span key={cat} className="game-model-cat-chip">
              {catDef?.icon} {catDef?.label}
            </span>
          );
        })}
      </div>

      <div className="game-model-card-strengths">
        {model.strengths.map((s) => (
          <span key={s} className="game-model-strength-tag">{s}</span>
        ))}
      </div>

      <div className="game-model-card-meta">
        {model.contextWindow > 0 ? (
          <span className="game-model-meta-item">上下文 {model.contextWindow.toLocaleString()}k</span>
        ) : null}
        {model.inputCostPer1M > 0 ? (
          <span className="game-model-meta-item">
            ${model.inputCostPer1M}/1M 输入 · ${model.outputCostPer1M}/1M 输出
          </span>
        ) : (
          <span className="game-model-meta-item">详见官网定价</span>
        )}
      </div>

      {model.status !== "coming_soon" && (
        <div className="game-model-card-recommended-for">
          <span className="game-model-recommended-label">适用场景：</span>
          {model.recommendedFor.map((r) => (
            <span key={r} className="game-model-recommended-tag">{r}</span>
          ))}
        </div>
      )}
    </div>
  );
}

function SceneItem({ scene, onEdit, onExport }: { scene: GameSceneConfig; onEdit: () => void; onExport: () => void }) {
  const catDef = MODEL_CATEGORIES.find((c) => c.id === scene.category);
  const model = MOCK_MODELS.find((m) => m.id === scene.modelId);

  return (
    <div className="game-scene-item">
      <div className="game-scene-item-head">
        <div className="game-scene-name-row">
          <span className="game-scene-cat-chip">{catDef?.icon} {catDef?.label}</span>
          <strong className="game-scene-name">{scene.name}</strong>
        </div>
        <div className="game-scene-model-badge">
          {model?.provider} · {model?.name}
        </div>
      </div>

      <div className="game-scene-params">
        <span className="game-scene-param">温度 {scene.temperature}</span>
        <span className="game-scene-param">最大 {scene.maxTokens} tokens</span>
        {scene.tools.length > 0 && (
          <span className="game-scene-param">工具 {scene.tools.length} 个</span>
        )}
      </div>

      <div className="game-scene-preview">
        <span className="game-scene-preview-label">测试输入：</span>
        <span className="game-scene-preview-text">{scene.testInput}</span>
      </div>

      <div className="game-scene-actions">
        <button type="button" className="game-scene-btn" onClick={onEdit}>编辑配置</button>
        <button type="button" className="game-scene-btn primary" onClick={onExport}>导出代码</button>
      </div>
    </div>
  );
}

function ExportPanel({ scene, onClose }: { scene: GameSceneConfig; onClose: () => void }) {
  const model = MOCK_MODELS.find((m) => m.id === scene.modelId) || MOCK_MODELS[0];
  const [activeFormat, setActiveFormat] = useState<"unity" | "rest">("unity");

  const snippet = activeFormat === "unity"
    ? generateUnitySnippet(scene, model)
    : generateRestApiSnippet(scene, model);

  return (
    <div className="game-export-panel">
      <div className="game-export-head">
        <div>
          <div className="game-export-title">导出配置：{scene.name}</div>
          <div className="game-export-subtitle">
            模型：{model.name} · 场景：{MODEL_CATEGORIES.find((c) => c.id === scene.category)?.label}
          </div>
        </div>
        <button type="button" className="game-export-close" onClick={onClose}>×</button>
      </div>

      <div className="game-export-format-tabs">
        <button
          type="button"
          className={`game-export-format-tab${activeFormat === "unity" ? " is-active" : ""}`}
          onClick={() => setActiveFormat("unity")}
        >
          Unity C# 接入
        </button>
        <button
          type="button"
          className={`game-export-format-tab${activeFormat === "rest" ? " is-active" : ""}`}
          onClick={() => setActiveFormat("rest")}
        >
          REST API 接入
        </button>
      </div>

      <pre className="game-export-code">{snippet}</pre>

      <div className="game-export-actions">
        <button
          type="button"
          className="game-export-copy-btn"
          onClick={() => {
            navigator.clipboard.writeText(snippet).catch(() => {});
          }}
        >
          复制代码
        </button>
      </div>
    </div>
  );
}

export function GameModelPage() {
  const [activeTab, setActiveTab] = useState<Tab>("models");
  const [activeCategory, setActiveCategory] = useState<ModelCategory | "all">("all");
  const [selectedModel, setSelectedModel] = useState<GameModel | null>(null);
  const [scenes, setScenes] = useState<GameSceneConfig[]>(SCENE_TEMPLATES);
  const [editingScene, setEditingScene] = useState<GameSceneConfig | null>(null);
  const [exportScene, setExportScene] = useState<GameSceneConfig | null>(null);
  const [customBaseUrl, setCustomBaseUrl] = useState("");
  const [customApiKey, setCustomApiKey] = useState("");
  const [customModelName, setCustomModelName] = useState("");

  const filteredModels = activeCategory === "all"
    ? MOCK_MODELS
    : MOCK_MODELS.filter((m) => m.categories.includes(activeCategory as ModelCategory));

  return (
    <div className="game-model-page">
      <header className="game-model-header">
        <div className="game-model-header-left">
          <div className="game-model-title-row">
            <span className="game-model-icon">🎮</span>
            <span className="game-model-title">游戏内模型接入</span>
          </div>
          <span className="game-model-subtitle">
            配置和导出大模型能力到 Unity / REST 游戏运行时
          </span>
        </div>
        <div className="game-model-header-right">
          <button type="button" className="game-model-action-btn">测试调用</button>
          <button type="button" className="game-model-action-btn">全部导出</button>
        </div>
      </header>

      <nav className="game-model-tabs">
        <button
          type="button"
          className={`game-model-tab${activeTab === "models" ? " is-active" : ""}`}
          onClick={() => setActiveTab("models")}
        >
          模型目录
        </button>
        <button
          type="button"
          className={`game-model-tab${activeTab === "scenes" ? " is-active" : ""}`}
          onClick={() => setActiveTab("scenes")}
        >
          场景配置
        </button>
        <button
          type="button"
          className={`game-model-tab${activeTab === "custom" ? " is-active" : ""}`}
          onClick={() => setActiveTab("custom")}
        >
          自定义接入
        </button>
        <button
          type="button"
          className={`game-model-tab${activeTab === "export" ? " is-active" : ""}`}
          onClick={() => setActiveTab("export")}
        >
          导出说明
        </button>
      </nav>

      <div className="game-model-content">
        {activeTab === "models" && (
          <div className="game-models-tab">
            <div className="game-model-filter-bar">
              <button
                type="button"
                className={`game-model-filter-btn${activeCategory === "all" ? " is-active" : ""}`}
                onClick={() => setActiveCategory("all")}
              >
                全部
              </button>
              {MODEL_CATEGORIES.map((cat) => (
                <button
                  key={cat.id}
                  type="button"
                  className={`game-model-filter-btn${activeCategory === cat.id ? " is-active" : ""}`}
                  onClick={() => setActiveCategory(cat.id)}
                >
                  {cat.icon} {cat.label}
                </button>
              ))}
            </div>

            <div className="game-models-grid">
              {filteredModels.map((model) => (
                <ModelCard
                  key={model.id}
                  model={model}
                  onSelect={() => setSelectedModel(model)}
                />
              ))}
            </div>

            {selectedModel && (
              <div className="game-model-detail-panel" onClick={() => setSelectedModel(null)}>
                <div className="game-model-detail-card" onClick={(e) => e.stopPropagation()}>
                  <div className="game-model-detail-head">
                    <div>
                      <strong className="game-model-detail-name">{selectedModel.name}</strong>
                      <span className="game-model-detail-provider">{selectedModel.provider}</span>
                    </div>
                    <button
                      type="button"
                      className="game-model-detail-close"
                      onClick={() => setSelectedModel(null)}
                    >
                      ×
                    </button>
                  </div>

                  <p className="game-model-detail-desc">{selectedModel.description}</p>

                  <div className="game-model-detail-params">
                    <div className="game-model-detail-param">
                      <span className="game-model-detail-param-label">上下文窗口</span>
                      <span className="game-model-detail-param-val">
                        {selectedModel.contextWindow > 0
                          ? `${selectedModel.contextWindow.toLocaleString()} tokens`
                          : "N/A"}
                      </span>
                    </div>
                    <div className="game-model-detail-param">
                      <span className="game-model-detail-param-label">输入成本</span>
                      <span className="game-model-detail-param-val">
                        {selectedModel.inputCostPer1M > 0
                          ? `$${selectedModel.inputCostPer1M}/1M tokens`
                          : "详见官网"}
                      </span>
                    </div>
                    <div className="game-model-detail-param">
                      <span className="game-model-detail-param-label">输出成本</span>
                      <span className="game-model-detail-param-val">
                        {selectedModel.outputCostPer1M > 0
                          ? `$${selectedModel.outputCostPer1M}/1M tokens`
                          : "详见官网"}
                      </span>
                    </div>
                  </div>

                  <div className="game-model-detail-recommended">
                    <span className="game-model-detail-recommended-label">适用场景</span>
                    <div className="game-model-detail-recommended-tags">
                      {selectedModel.recommendedFor.map((r) => (
                        <span key={r} className="game-model-detail-recommended-tag">{r}</span>
                      ))}
                    </div>
                  </div>

                  <div className="game-model-detail-actions">
                    <button
                      type="button"
                      className="game-model-detail-btn primary"
                      onClick={() => {
                        const scene: GameSceneConfig = {
                          id: `scene-${Date.now()}`,
                          name: `新建 ${selectedModel.name} 场景`,
                          category: selectedModel.categories[0],
                          modelId: selectedModel.id,
                          systemPrompt: "你是一个游戏助手。",
                          temperature: 0.8,
                          maxTokens: 300,
                          tools: [],
                          testInput: "",
                        };
                        setScenes((prev) => [...prev, scene]);
                        setSelectedModel(null);
                        setActiveTab("scenes");
                      }}
                    >
                      创建场景
                    </button>
                    <button
                      type="button"
                      className="game-model-detail-btn"
                      onClick={() => {
                        setSelectedModel(null);
                        setActiveTab("custom");
                      }}
                    >
                      自定义配置
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === "scenes" && (
          <div className="game-scenes-tab">
            <div className="game-scenes-header">
              <span className="game-scenes-count">{scenes.length} 个已配置场景</span>
              <button
                type="button"
                className="game-scenes-add-btn"
                onClick={() => {
                  const newScene: GameSceneConfig = {
                    id: `scene-${Date.now()}`,
                    name: `新场景 ${scenes.length + 1}`,
                    category: "npc",
                    modelId: "gpt-4o",
                    systemPrompt: "",
                    temperature: 0.8,
                    maxTokens: 300,
                    tools: [],
                    testInput: "",
                  };
                  setScenes((prev) => [...prev, newScene]);
                  setEditingScene(newScene);
                }}
              >
                + 新建场景
              </button>
            </div>

            <div className="game-scenes-list">
              {scenes.map((scene) => (
                <SceneItem
                  key={scene.id}
                  scene={scene}
                  onEdit={() => setEditingScene(scene)}
                  onExport={() => setExportScene(scene)}
                />
              ))}
            </div>

            {editingScene && (
              <div className="game-model-detail-panel" onClick={() => setEditingScene(null)}>
                <div className="game-model-edit-card" onClick={(e) => e.stopPropagation()}>
                  <div className="game-model-detail-head">
                    <strong>编辑场景：{editingScene.name}</strong>
                    <button type="button" className="game-model-detail-close" onClick={() => setEditingScene(null)}>×</button>
                  </div>

                  <div className="game-model-edit-form">
                    <label className="game-model-edit-field">
                      <span>场景名称</span>
                      <input
                        type="text"
                        value={editingScene.name}
                        onChange={(e) => setEditingScene({ ...editingScene, name: e.target.value })}
                      />
                    </label>

                    <label className="game-model-edit-field">
                      <span>分类</span>
                      <select
                        value={editingScene.category}
                        onChange={(e) => setEditingScene({ ...editingScene, category: e.target.value as ModelCategory })}
                      >
                        {MODEL_CATEGORIES.map((cat) => (
                          <option key={cat.id} value={cat.id}>{cat.icon} {cat.label}</option>
                        ))}
                      </select>
                    </label>

                    <label className="game-model-edit-field">
                      <span>System Prompt</span>
                      <textarea
                        value={editingScene.systemPrompt}
                        onChange={(e) => setEditingScene({ ...editingScene, systemPrompt: e.target.value })}
                        placeholder="定义 AI 的角色和行为规则…"
                      />
                    </label>

                    <div className="game-model-edit-row">
                      <label className="game-model-edit-field">
                        <span>Temperature</span>
                        <input
                          type="number"
                          min="0"
                          max="2"
                          step="0.1"
                          value={editingScene.temperature}
                          onChange={(e) => setEditingScene({ ...editingScene, temperature: parseFloat(e.target.value) })}
                        />
                      </label>
                      <label className="game-model-edit-field">
                        <span>Max Tokens</span>
                        <input
                          type="number"
                          min="1"
                          max="32000"
                          value={editingScene.maxTokens}
                          onChange={(e) => setEditingScene({ ...editingScene, maxTokens: parseInt(e.target.value) })}
                        />
                      </label>
                    </div>

                    <label className="game-model-edit-field">
                      <span>测试输入</span>
                      <textarea
                        value={editingScene.testInput}
                        onChange={(e) => setEditingScene({ ...editingScene, testInput: e.target.value })}
                        placeholder="输入测试对话内容…"
                      />
                    </label>

                    <div className="game-model-edit-actions">
                      <button
                        type="button"
                        className="game-model-detail-btn primary"
                        onClick={() => {
                          setScenes((prev) => prev.map((s) => s.id === editingScene.id ? editingScene : s));
                          setEditingScene(null);
                        }}
                      >
                        保存
                      </button>
                      <button
                        type="button"
                        className="game-model-detail-btn"
                        onClick={() => setEditingScene(null)}
                      >
                        取消
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {exportScene && (
              <div className="game-model-detail-panel" onClick={() => setExportScene(null)}>
                <div onClick={(e) => e.stopPropagation()}>
                  <ExportPanel scene={exportScene} onClose={() => setExportScene(null)} />
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === "custom" && (
          <div className="game-custom-tab">
            <div className="game-custom-intro">
              <p>如果你有自己的模型服务（兼容 OpenAI API 格式），可以直接填入接入。</p>
            </div>

            <div className="game-custom-form">
              <label className="game-model-edit-field">
                <span>Base URL</span>
                <input
                  type="text"
                  placeholder="https://api.openai.com/v1"
                  value={customBaseUrl}
                  onChange={(e) => setCustomBaseUrl(e.target.value)}
                />
              </label>

              <label className="game-model-edit-field">
                <span>API Key</span>
                <input
                  type="password"
                  placeholder="sk-..."
                  value={customApiKey}
                  onChange={(e) => setCustomApiKey(e.target.value)}
                />
              </label>

              <label className="game-model-edit-field">
                <span>模型名称</span>
                <input
                  type="text"
                  placeholder="gpt-4o / claude-3-5-sonnet / ..."
                  value={customModelName}
                  onChange={(e) => setCustomModelName(e.target.value)}
                />
              </label>

              <div className="game-custom-actions">
                <button
                  type="button"
                  className="game-model-detail-btn primary"
                  disabled={!customBaseUrl || !customApiKey || !customModelName}
                  onClick={() => {
                    const scene: GameSceneConfig = {
                      id: `custom-${Date.now()}`,
                      name: `自定义接入`,
                      category: "npc",
                      modelId: "custom",
                      systemPrompt: "",
                      temperature: 0.8,
                      maxTokens: 300,
                      tools: [],
                      testInput: "",
                    };
                    setScenes((prev) => [...prev, scene]);
                    setActiveTab("scenes");
                  }}
                >
                  保存并创建场景
                </button>
                <button
                  type="button"
                  className="game-model-detail-btn"
                  onClick={() => {
                    setCustomBaseUrl("");
                    setCustomApiKey("");
                    setCustomModelName("");
                  }}
                >
                  重置
                </button>
              </div>
            </div>
          </div>
        )}

        {activeTab === "export" && (
          <div className="game-export-tab">
            <div className="game-export-info">
              <h3 className="game-export-info-title">导出能力说明</h3>

              <div className="game-export-section">
                <h4 className="game-export-section-title">Unity C# 接入</h4>
                <p>生成 Unity 游戏项目可直接使用的 C# 接入代码，包含 Agent 初始化、消息发送、工具调用等完整流程。</p>
                <div className="game-export-feature-list">
                  <span>✓ 完整 Agent 类模板</span>
                  <span>✓ 工具配置自动生成</span>
                  <span>✓ 异步消息处理</span>
                  <span>✓ Unity 日志集成</span>
                </div>
              </div>

              <div className="game-export-section">
                <h4 className="game-export-section-title">REST API 接入</h4>
                <p>生成标准 REST API 调用配置，适合任何游戏引擎或服务端使用。</p>
                <div className="game-export-feature-list">
                  <span>✓ curl 请求示例</span>
                  <span>✓ 请求/响应格式</span>
                  <span>✓ 鉴权配置</span>
                  <span>✓ 错误处理说明</span>
                </div>
              </div>

              <div className="game-export-section">
                <h4 className="game-export-section-title">运行时注意事项</h4>
                <ul className="game-export-notes">
                  <li>API Key 请通过环境变量或安全存储注入，不要硬编码</li>
                  <li>生产环境建议配置请求重试和降级策略</li>
                  <li>高频场景建议使用流式输出（Server-Sent Events）</li>
                  <li>成本控制：建议设置单次请求最大 token 上限</li>
                </ul>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
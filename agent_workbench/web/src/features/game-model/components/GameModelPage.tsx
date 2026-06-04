import { useEffect, useMemo, useState } from "react";

import {
  exportGameModelRuntime,
  getGameModelRuntime,
  runGameModelRuntimeTest,
  saveGameModelRuntimeScenes,
} from "../api";
import "../styles/game-model.css";

import {
  type GameModel,
  type GameModelRuntimeState,
  type GameSceneConfig,
  type ModelCategory,
  type RuntimeArtifact,
  type RuntimeExportBundle,
  MODEL_CATEGORIES,
  MOCK_MODELS,
  SCENE_TEMPLATES,
  generateRestApiSnippet,
  generateUnitySnippet,
} from "../types";

type Tab = "scenes" | "models" | "custom" | "export";

interface ArtifactState {
  title: string;
  subtitle: string;
  content: RuntimeArtifact | string;
}

function toErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error || "请求失败");
}

function artifactText(content: RuntimeArtifact | string): string {
  if (typeof content === "string") {
    return content;
  }
  return JSON.stringify(content, null, 2);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isRuntimeExportBundle(value: unknown): value is RuntimeExportBundle {
  return isRecord(value) && value.artifact_type === "runtime_export_bundle" && isRecord(value.files);
}

function safeFileName(value: string): string {
  return value.replace(/[\\/:*?"<>|]+/g, "-").replace(/\s+/g, "-").trim() || "ludens-runtime";
}

function downloadTextFile(filename: string, content: string, mimeType = "text/plain") {
  const blob = new Blob([content], { type: `${mimeType};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function categoryLabel(category: ModelCategory | string): string {
  return MODEL_CATEGORIES.find((item) => item.id === category)?.label || category;
}

function getSceneModel(scene: GameSceneConfig): GameModel {
  return (
    MOCK_MODELS.find((model) => model.id === scene.modelId) || {
      id: "custom",
      name: scene.modelId === "custom" ? "Custom Model" : scene.modelId,
      provider: scene.modelId === "custom" ? "Custom" : "Runtime",
      description: "",
      categories: [scene.category],
      contextWindow: 0,
      strengths: [],
      inputCostPer1M: 0,
      outputCostPer1M: 0,
      status: "popular",
      recommendedFor: [],
    }
  );
}

function ModelCard({ model, onSelect }: { model: GameModel; onSelect: () => void }) {
  return (
    <div
      className={`game-model-card${model.status === "coming_soon" ? " is-coming-soon" : ""}`}
      onClick={model.status !== "coming_soon" ? onSelect : undefined}
    >
      <div className="game-model-card-head">
        <div className="game-model-card-name-row">
          <strong className="game-model-card-name">{model.name}</strong>
          {model.status === "recommended" ? (
            <span className="game-model-badge recommended">推荐</span>
          ) : model.status === "popular" ? (
            <span className="game-model-badge popular">热门</span>
          ) : (
            <span className="game-model-badge coming-soon">Coming Soon</span>
          )}
        </div>
        <span className="game-model-card-provider">{model.provider}</span>
      </div>

      <p className="game-model-card-desc">{model.description}</p>

      <div className="game-model-card-categories">
        {model.categories.map((cat) => {
          const catDef = MODEL_CATEGORIES.find((item) => item.id === cat);
          return (
            <span key={cat} className="game-model-cat-chip">
              {catDef?.icon} {catDef?.label}
            </span>
          );
        })}
      </div>

      <div className="game-model-card-strengths">
        {model.strengths.map((strength) => (
          <span key={strength} className="game-model-strength-tag">
            {strength}
          </span>
        ))}
      </div>

      <div className="game-model-card-meta">
        {model.contextWindow > 0 ? (
          <span className="game-model-meta-item">
            上下文 {model.contextWindow.toLocaleString()} tokens
          </span>
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
          {model.recommendedFor.map((item) => (
            <span key={item} className="game-model-recommended-tag">
              {item}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function SceneItem({
  scene,
  busyAction,
  onEdit,
  onExport,
  onTest,
  onDelete,
}: {
  scene: GameSceneConfig;
  busyAction: string;
  onEdit: () => void;
  onExport: () => void;
  onTest: () => void;
  onDelete: () => void;
}) {
  const catDef = MODEL_CATEGORIES.find((item) => item.id === scene.category);
  const model = getSceneModel(scene);
  const isComingSoon = scene.runtimeStage === "coming_soon";
  const isBusy = busyAction.endsWith(`:${scene.id}`);
  const capabilityTags =
    scene.category === "quest"
      ? ["任务"]
      : scene.category === "behavior_tree"
        ? ["行为树"]
        : scene.category === "multimodal"
          ? ["多模态方案"]
          : [];

  return (
    <div className={`game-scene-item${isComingSoon ? " is-coming-soon" : ""}`}>
      <div className="game-scene-item-head">
        <div className="game-scene-name-block">
          <div className="game-scene-name-row">
            <span className="game-scene-cat-chip">
              {catDef?.icon} {catDef?.label}
            </span>
            <strong className="game-scene-name">{scene.name}</strong>
            {isComingSoon ? <span className="game-model-badge coming-soon">Coming Soon</span> : null}
          </div>
          {capabilityTags.length ? (
            <div className="game-scene-capability-tags">
              {capabilityTags.map((tag) => (
                <span key={tag} className="game-scene-capability-tag">
                  {tag}
                </span>
              ))}
            </div>
          ) : null}
          {scene.description ? <p className="game-scene-desc">{scene.description}</p> : null}
        </div>
        <div className="game-scene-model-badge">
          {model.provider} · {model.name}
        </div>
      </div>

      <div className="game-scene-params">
        <span className="game-scene-param">温度 {scene.temperature}</span>
        <span className="game-scene-param">最大 {scene.maxTokens} tokens</span>
        {scene.tools.length > 0 ? (
          <span className="game-scene-param">工具 {scene.tools.length} 个</span>
        ) : null}
        {scene.modalities?.map((modality) => (
          <span key={modality} className="game-scene-param">
            {modality}
          </span>
        ))}
      </div>

      <div className="game-scene-preview">
        <span className="game-scene-preview-label">测试输入：</span>
        <span className="game-scene-preview-text">{scene.testInput || "未配置"}</span>
      </div>

      <div className="game-scene-actions">
        <button type="button" className="game-scene-btn" onClick={onEdit}>
          编辑配置
        </button>
        <button
          type="button"
          className="game-scene-btn danger"
          disabled={isBusy}
          onClick={onDelete}
        >
          删除
        </button>
        <button
          type="button"
          className="game-scene-btn"
          disabled={isComingSoon || isBusy}
          onClick={onTest}
        >
          测试调用
        </button>
        <button
          type="button"
          className="game-scene-btn primary"
          disabled={isComingSoon || isBusy}
          onClick={onExport}
        >
          导出包
        </button>
      </div>
    </div>
  );
}

function ArtifactPreview({ artifact }: { artifact: ArtifactState | null }) {
  const exportBundle = artifact && isRuntimeExportBundle(artifact.content) ? artifact.content : null;

  return (
    <section className="game-runtime-output">
      <div className="game-runtime-section-head">
        <div>
          <h3>最新AI配置结果</h3>
          <span>{artifact?.subtitle || "等待测试或导出"}</span>
        </div>
      </div>
      {exportBundle ? (
        <div className="game-runtime-file-list">
          {Object.entries(exportBundle.files).map(([filename, content]) => (
            <button
              type="button"
              className="game-runtime-file-btn"
              key={filename}
              onClick={() => downloadTextFile(safeFileName(filename), content)}
            >
              {filename}
            </button>
          ))}
        </div>
      ) : null}
      <pre className="game-export-code game-runtime-code">
        {artifact ? artifactText(artifact.content) : "选择场景后测试调用或导出配置包。"}
      </pre>
      {artifact ? (
        <div className="game-runtime-output-actions">
          <button
            type="button"
            className="game-export-copy-btn"
            onClick={() => {
              navigator.clipboard.writeText(artifactText(artifact.content)).catch(() => {});
            }}
          >
            复制 JSON
          </button>
          {exportBundle ? (
            <button
              type="button"
              className="game-export-copy-btn"
              onClick={() => {
                for (const [filename, content] of Object.entries(exportBundle.files)) {
                  downloadTextFile(safeFileName(filename), content);
                }
              }}
            >
              下载导出文件
            </button>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function ExportPanel({ scene, onClose }: { scene: GameSceneConfig; onClose: () => void }) {
  const model = getSceneModel(scene);
  const [activeFormat, setActiveFormat] = useState<"unity" | "rest">("unity");

  const snippet =
    activeFormat === "unity"
      ? generateUnitySnippet(scene, model)
      : generateRestApiSnippet(scene, model);

  return (
    <div className="game-export-panel">
      <div className="game-export-head">
        <div>
          <div className="game-export-title">导出配置：{scene.name}</div>
          <div className="game-export-subtitle">
            模型：{model.name} · 场景：{categoryLabel(scene.category)}
          </div>
        </div>
        <button type="button" className="game-export-close" onClick={onClose}>
          ×
        </button>
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
  const [activeTab, setActiveTab] = useState<Tab>("scenes");
  const [activeCategory, setActiveCategory] = useState<ModelCategory | "all">("all");
  const [selectedModel, setSelectedModel] = useState<GameModel | null>(null);
  const [runtimeState, setRuntimeState] = useState<GameModelRuntimeState | null>(null);
  const [scenes, setScenes] = useState<GameSceneConfig[]>(SCENE_TEMPLATES);
  const [editingScene, setEditingScene] = useState<GameSceneConfig | null>(null);
  const [categoryPickerOpen, setCategoryPickerOpen] = useState(false);
  const [exportScene, setExportScene] = useState<GameSceneConfig | null>(null);
  const [customBaseUrl, setCustomBaseUrl] = useState("");
  const [customApiKey, setCustomApiKey] = useState("");
  const [customModelName, setCustomModelName] = useState("");
  const [busyAction, setBusyAction] = useState("");
  const [errorText, setErrorText] = useState("");
  const [artifact, setArtifact] = useState<ArtifactState | null>(null);
  const [useLiveModel, setUseLiveModel] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setBusyAction("runtime:load");
    getGameModelRuntime()
      .then((state) => {
        if (cancelled) {
          return;
        }
        setRuntimeState(state);
        setScenes(state.scenes.length ? state.scenes : SCENE_TEMPLATES);
        setErrorText("");
      })
      .catch((error) => {
        if (!cancelled) {
          setErrorText(toErrorMessage(error));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setBusyAction("");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const filteredModels = useMemo(
    () =>
      activeCategory === "all"
        ? MOCK_MODELS
        : MOCK_MODELS.filter((model) => model.categories.includes(activeCategory)),
    [activeCategory],
  );

  async function persistScenes(nextScenes: GameSceneConfig[]) {
    setScenes(nextScenes);
    setBusyAction("runtime:save");
    try {
      const state = await saveGameModelRuntimeScenes(nextScenes);
      setRuntimeState(state);
      setScenes(state.scenes);
      setErrorText("");
    } catch (error) {
      setErrorText(toErrorMessage(error));
    } finally {
      setBusyAction("");
    }
  }

  async function handleRuntimeTest(scene: GameSceneConfig) {
    if (scene.runtimeStage === "coming_soon") {
      setArtifact({
        title: "世界模型 Coming Soon",
        subtitle: "当前只开放计划预览，不执行运行时测试调用。",
        content: runtimeState?.world_model || "world_model coming soon",
      });
      setActiveTab("scenes");
      return;
    }

    setBusyAction(`test:${scene.id}`);
    try {
      const result = await runGameModelRuntimeTest({
        scene_id: scene.id,
        scene,
        input: scene.testInput || scene.description || scene.systemPrompt,
        live_model: useLiveModel,
      });
      setArtifact({
        title: scene.name,
        subtitle: useLiveModel ? "真实模型测试调用结果" : "运行时预览测试结果",
        content: result,
      });
      setErrorText("");
      setActiveTab("scenes");
    } catch (error) {
      setErrorText(toErrorMessage(error));
    } finally {
      setBusyAction("");
    }
  }

  async function handleExport(sceneIds?: string[]) {
    setBusyAction(sceneIds?.length ? `export:${sceneIds[0]}` : "export:all");
    try {
      const bundle = await exportGameModelRuntime({
        scene_ids: sceneIds,
        scenes,
      });
      setArtifact({
        title: "运行时导出包",
        subtitle: `${Object.keys(bundle.files).length} 个文件 · ${bundle.rest_contract.endpoints.length} 个 REST 端点`,
        content: bundle,
      });
      setErrorText("");
      setActiveTab("scenes");
    } catch (error) {
      setErrorText(toErrorMessage(error));
    } finally {
      setBusyAction("");
    }
  }

  function addSceneFromModel(model: GameModel) {
    const scene: GameSceneConfig = {
      id: `scene-${Date.now()}`,
      name: `新建 ${model.name} 场景`,
      category: model.categories[0],
      modelId: model.id,
      systemPrompt: "你是一个游戏运行时助手。",
      temperature: 0.8,
      maxTokens: 300,
      tools: [],
      testInput: "",
      runtimeStage: "ready",
    };
    void persistScenes([...scenes, scene]);
    setSelectedModel(null);
    setActiveTab("scenes");
  }

  function addBlankScene() {
    const newScene: GameSceneConfig = {
      id: `scene-${Date.now()}`,
      name: `新场景 ${scenes.length + 1}`,
      category: "npc",
      modelId: "gpt-5.4-mini",
      systemPrompt: "",
      temperature: 0.8,
      maxTokens: 300,
      tools: [],
      testInput: "",
      runtimeStage: "ready",
    };
    setCategoryPickerOpen(false);
    setEditingScene(newScene);
  }

  function deleteScene(scene: GameSceneConfig) {
    const confirmed = window.confirm(`删除场景“${scene.name}”？此操作会更新当前项目的运行时配置。`);
    if (!confirmed) {
      return;
    }
    const nextScenes = scenes.filter((item) => item.id !== scene.id);
    void persistScenes(nextScenes).then(() => {
      if (editingScene?.id === scene.id) {
        setEditingScene(null);
        setCategoryPickerOpen(false);
      }
      if (exportScene?.id === scene.id) {
        setExportScene(null);
      }
      if (artifact?.title === scene.name) {
        setArtifact(null);
      }
    });
  }

  const firstRunnableScene =
    scenes.find((scene) => scene.id === "character-behavior-tree") ||
    scenes.find((scene) => scene.runtimeStage !== "coming_soon") ||
    scenes[0];
  const editingCategory = editingScene
    ? MODEL_CATEGORIES.find((cat) => cat.id === editingScene.category)
    : null;

  return (
    <div className="game-model-page">
      <header className="game-model-header">
        <div className="game-model-header-left">
          <div className="game-model-title-stack">
            <span className="game-model-eyebrow">GAME AI CONFIG</span>
            <h1 className="game-model-title">游戏AI配置中心</h1>
          </div>
          <span className="game-model-subtitle">
            在你的游戏项目当中接入AI模型，统一管理配置
          </span>
        </div>
        <div className="game-model-header-right">
          <button
            type="button"
            className={`game-model-action-btn${useLiveModel ? " is-active" : ""}`}
            onClick={() => setUseLiveModel((value) => !value)}
          >
            {useLiveModel ? "真实模型" : "预览模式"}
          </button>
          <button
            type="button"
            className="game-model-action-btn"
            disabled={!firstRunnableScene || Boolean(busyAction)}
            onClick={() => firstRunnableScene && void handleRuntimeTest(firstRunnableScene)}
          >
            测试调用
          </button>
          <button
            type="button"
            className="game-model-action-btn"
            disabled={Boolean(busyAction)}
            onClick={() => void handleExport()}
          >
            全部导出
          </button>
        </div>
      </header>

      <nav className="game-model-tabs">
        <button
          type="button"
          className={`game-model-tab${activeTab === "scenes" ? " is-active" : ""}`}
          onClick={() => setActiveTab("scenes")}
        >
          场景配置
        </button>
        <button
          type="button"
          className={`game-model-tab${activeTab === "models" ? " is-active" : ""}`}
          onClick={() => setActiveTab("models")}
        >
          模型广场
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
              {MODEL_CATEGORIES.map((cat) => {
                const isComingSoon = cat.status === "coming_soon";
                return (
                  <button
                    key={cat.id}
                    type="button"
                    className={`game-model-filter-btn${activeCategory === cat.id ? " is-active" : ""}${
                      isComingSoon ? " is-coming-soon" : ""
                    }`}
                    disabled={isComingSoon}
                    onClick={() => {
                      if (!isComingSoon) {
                        setActiveCategory(cat.id);
                      }
                    }}
                  >
                    <span>{cat.icon} {cat.label}</span>
                    {isComingSoon ? <small>Coming Soon</small> : null}
                  </button>
                );
              })}
            </div>

            <div className="game-models-grid">
              {filteredModels.map((model) => (
                <ModelCard key={model.id} model={model} onSelect={() => setSelectedModel(model)} />
              ))}
            </div>

            {selectedModel && (
              <div className="game-model-detail-panel" onClick={() => setSelectedModel(null)}>
                <div className="game-model-detail-card" onClick={(event) => event.stopPropagation()}>
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
                      {selectedModel.recommendedFor.map((item) => (
                        <span key={item} className="game-model-detail-recommended-tag">
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="game-model-detail-actions">
                    <button
                      type="button"
                      className="game-model-detail-btn primary"
                      onClick={() => addSceneFromModel(selectedModel)}
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
              <button type="button" className="game-scenes-add-btn" onClick={addBlankScene}>
                + 新建场景
              </button>
            </div>

            {errorText ? <div className="game-scenes-error">{errorText}</div> : null}

            {artifact ? <ArtifactPreview artifact={artifact} /> : null}

            <div className="game-scenes-list">
              {scenes.map((scene) => (
                <SceneItem
                  key={scene.id}
                  scene={scene}
                  busyAction={busyAction}
                  onEdit={() => {
                    setCategoryPickerOpen(false);
                    setEditingScene(scene);
                  }}
                  onExport={() => void handleExport([scene.id])}
                  onTest={() => void handleRuntimeTest(scene)}
                  onDelete={() => deleteScene(scene)}
                />
              ))}
            </div>

            {editingScene && (
              <div
                className="game-model-detail-panel"
                onClick={() => {
                  setCategoryPickerOpen(false);
                  setEditingScene(null);
                }}
              >
                <div className="game-model-edit-card" onClick={(event) => event.stopPropagation()}>
                  <div className="game-model-detail-head">
                    <strong className="game-model-detail-name">编辑场景：{editingScene.name}</strong>
                    <button
                      type="button"
                      className="game-model-detail-close"
                      onClick={() => {
                        setCategoryPickerOpen(false);
                        setEditingScene(null);
                      }}
                    >
                      ×
                    </button>
                  </div>

                  <div className="game-model-edit-form">
                    <label className="game-model-edit-field">
                      <span>场景名称</span>
                      <input
                        type="text"
                        value={editingScene.name}
                        onChange={(event) => setEditingScene({ ...editingScene, name: event.target.value })}
                      />
                    </label>

                    <div className="game-model-edit-field">
                      <span>分类</span>
                      <div className={`game-category-select${categoryPickerOpen ? " is-open" : ""}`}>
                        <button
                          type="button"
                          className="game-category-select-trigger"
                          onClick={() => setCategoryPickerOpen((value) => !value)}
                        >
                          <span className="game-category-select-value">
                            {editingCategory?.icon} {editingCategory?.label || categoryLabel(editingScene.category)}
                          </span>
                          <span className="game-category-select-arrow">⌄</span>
                        </button>
                        {categoryPickerOpen ? (
                          <div className="game-category-option-list">
                            {MODEL_CATEGORIES.map((cat) => {
                              const isComingSoon = cat.status === "coming_soon";
                              const isActive = editingScene.category === cat.id;
                              return (
                                <button
                                  key={cat.id}
                                  type="button"
                                  className={`game-category-option${isActive ? " is-active" : ""}${
                                    isComingSoon ? " is-coming-soon" : ""
                                  }`}
                                  disabled={isComingSoon}
                                  onClick={() => {
                                    if (!isComingSoon) {
                                      setEditingScene({ ...editingScene, category: cat.id });
                                      setCategoryPickerOpen(false);
                                    }
                                  }}
                                >
                                  <span className="game-category-option-main">
                                    <span className="game-category-option-label">
                                      {cat.icon} {cat.label}
                                    </span>
                                    {isComingSoon ? (
                                      <span className="game-category-option-status">Coming Soon</span>
                                    ) : null}
                                  </span>
                                  <span className="game-category-option-hint">{cat.hint}</span>
                                </button>
                              );
                            })}
                          </div>
                        ) : null}
                      </div>
                    </div>

                    <label className="game-model-edit-field">
                      <span>System Prompt</span>
                      <textarea
                        value={editingScene.systemPrompt}
                        onChange={(event) =>
                          setEditingScene({ ...editingScene, systemPrompt: event.target.value })
                        }
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
                          onChange={(event) =>
                            setEditingScene({
                              ...editingScene,
                              temperature: Number.parseFloat(event.target.value) || 0,
                            })
                          }
                        />
                      </label>
                      <label className="game-model-edit-field">
                        <span>Max Tokens</span>
                        <input
                          type="number"
                          min="1"
                          max="32000"
                          value={editingScene.maxTokens}
                          onChange={(event) =>
                            setEditingScene({
                              ...editingScene,
                              maxTokens: Number.parseInt(event.target.value, 10) || 1,
                            })
                          }
                        />
                      </label>
                    </div>

                    <label className="game-model-edit-field">
                      <span>测试输入</span>
                      <textarea
                        value={editingScene.testInput}
                        onChange={(event) =>
                          setEditingScene({ ...editingScene, testInput: event.target.value })
                        }
                      />
                    </label>

                    <label className="game-model-edit-field">
                      <span>工具列表</span>
                      <input
                        type="text"
                        value={editingScene.tools.join(", ")}
                        onChange={(event) =>
                          setEditingScene({
                            ...editingScene,
                            tools: event.target.value
                              .split(/[,，]/)
                              .map((item) => item.trim())
                              .filter(Boolean),
                          })
                        }
                      />
                    </label>

                    <div className="game-model-edit-actions">
                      <button
                        type="button"
                        className="game-model-detail-btn primary"
                        onClick={() => {
                          const sceneExists = scenes.some((scene) => scene.id === editingScene.id);
                          const nextScenes = sceneExists
                            ? scenes.map((scene) => (scene.id === editingScene.id ? editingScene : scene))
                            : [...scenes, editingScene];
                          void persistScenes(nextScenes).then(() => {
                            setCategoryPickerOpen(false);
                            setEditingScene(null);
                          });
                        }}
                      >
                        保存
                      </button>
                      <button
                        type="button"
                        className="game-model-detail-btn"
                        onClick={() => {
                          setCategoryPickerOpen(false);
                          setEditingScene(null);
                        }}
                      >
                        取消
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === "custom" && (
          <div className="game-custom-tab">
            <div className="game-custom-intro">
              <p>兼容 OpenAI API 格式的自有模型服务可作为运行时场景模型源。</p>
            </div>

            <div className="game-custom-form">
              <label className="game-model-edit-field">
                <span>Base URL</span>
                <input
                  type="text"
                  placeholder="https://api.openai.com/v1"
                  value={customBaseUrl}
                  onChange={(event) => setCustomBaseUrl(event.target.value)}
                />
              </label>

              <label className="game-model-edit-field">
                <span>API Key</span>
                <input
                  type="password"
                  placeholder="sk-..."
                  value={customApiKey}
                  onChange={(event) => setCustomApiKey(event.target.value)}
                />
              </label>

              <label className="game-model-edit-field">
                <span>模型名称</span>
                <input
                  type="text"
                  placeholder="gpt-5.4 / claude-sonnet / local-model"
                  value={customModelName}
                  onChange={(event) => setCustomModelName(event.target.value)}
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
                      name: `自定义接入：${customModelName}`,
                      category: "npc",
                      modelId: "custom",
                      systemPrompt: "",
                      temperature: 0.8,
                      maxTokens: 300,
                      tools: [],
                      testInput: "",
                      runtimeStage: "ready",
                    };
                    void persistScenes([...scenes, scene]);
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
                <p>导出包包含 `runtime_config.json`、运行时客户端和 Agent Binder。</p>
                <div className="game-export-feature-list">
                  <span>runtime_config.json</span>
                  <span>LudensFlowRuntimeClient.cs</span>
                  <span>LudensFlowAgentBinder.cs</span>
                  <span>行为树 / 任务线 Runner 绑定点</span>
                </div>
              </div>

              <div className="game-export-section">
                <h4 className="game-export-section-title">REST API 接入</h4>
                <p>导出包声明运行时调用、任务事件、行为树 tick、多模态分析和调试日志端点。</p>
                <div className="game-export-feature-list">
                  <span>/runtime/invoke</span>
                  <span>/runtime/quests/events</span>
                  <span>/runtime/behavior-tree/tick</span>
                  <span>/runtime/multimodal/analyze</span>
                </div>
              </div>

              <div className="game-export-section">
                <h4 className="game-export-section-title">运行时边界</h4>
                <ul className="game-export-notes">
                  <li>API Key 只放服务端或安全配置，不写进客户端仓库。</li>
                  <li>工具调用必须走 allowlist，状态写入默认需要人工审阅。</li>
                  <li>多模态输入需要玩家授权、脱敏和 payload 上限。</li>
                  <li>世界模型当前只提供 Coming Soon 里程碑与接口预留。</li>
                </ul>
              </div>
            </div>
          </div>
        )}
      </div>

      {exportScene && (
        <div className="game-model-detail-panel" onClick={() => setExportScene(null)}>
          <div onClick={(event) => event.stopPropagation()}>
            <ExportPanel scene={exportScene} onClose={() => setExportScene(null)} />
          </div>
        </div>
      )}
    </div>
  );
}

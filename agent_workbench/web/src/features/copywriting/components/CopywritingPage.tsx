import { useMemo, useState } from "react";

import "../styles/copywriting.css";

type CopyType = {
  id: string;
  name: string;
  desc: string;
  examples: string[];
};

const COPY_TYPES: CopyType[] = [
  {
    id: "dialogue",
    name: "角色台词",
    desc: "用于 NPC 对话、剧情对白、战斗喊话和事件反应。",
    examples: ["首次见面", "任务推进", "战斗触发"],
  },
  {
    id: "item",
    name: "物品描述",
    desc: "用于背包、商店、掉落、装备和收藏品说明。",
    examples: ["短描述", "风味文本", "稀有度差异"],
  },
  {
    id: "world",
    name: "世界观片段",
    desc: "用于地区介绍、阵营背景、历史传说和规则说明。",
    examples: ["地区传闻", "阵营档案", "古老事件"],
  },
  {
    id: "naming",
    name: "命名生成",
    desc: "用于角色名、地名、技能名、道具名和组织名。",
    examples: ["中文名", "英文名", "系列命名"],
  },
  {
    id: "quest",
    name: "任务文本",
    desc: "用于任务标题、目标说明、阶段提示和完成反馈。",
    examples: ["任务标题", "目标文案", "完成提示"],
  },
];

const STYLE_PRESETS = ["简洁直给", "细腻叙事", "口语自然", "诗性凝练"];
const LENGTH_PRESETS = ["极短", "短句", "标准", "较长"];
const CODEX_ITEMS = [
  { name: "GDD", desc: "核心玩法、题材、目标体验", active: true },
  { name: "角色设定", desc: "角色身份、关系、语气边界", active: true },
  { name: "世界观术语", desc: "专有名词、地名、阵营名", active: true },
  { name: "禁用规则", desc: "不能出现的词、设定冲突", active: false },
];

export function CopywritingPage() {
  const [activeTypeId, setActiveTypeId] = useState(COPY_TYPES[0].id);
  const [selectedStyle, setSelectedStyle] = useState(STYLE_PRESETS[0]);
  const [selectedLength, setSelectedLength] = useState(LENGTH_PRESETS[2]);
  const [quantity, setQuantity] = useState(5);

  const activeType = useMemo(
    () => COPY_TYPES.find((item) => item.id === activeTypeId) || COPY_TYPES[0],
    [activeTypeId],
  );

  return (
    <div className="copywriting-page" aria-label="文案加工台">
      <aside className="copywriting-rail">
        <div className="copywriting-rail-head">
          <span className="copywriting-kicker">策划子能力</span>
          <strong>文案类型</strong>
        </div>
        <div className="copywriting-type-list">
          {COPY_TYPES.map((type) => (
            <button
              key={type.id}
              type="button"
              className={`copywriting-type-card${type.id === activeTypeId ? " is-active" : ""}`}
              onClick={() => setActiveTypeId(type.id)}
            >
              <span>{type.name}</span>
              <small>{type.desc}</small>
            </button>
          ))}
        </div>
      </aside>

      <main className="copywriting-workbench">
        <section className="copywriting-panel copywriting-brief-panel">
          <header className="copywriting-hero copywriting-hero-compact">
            <div>
              <span className="copywriting-kicker">Copy Workshop</span>
              <h2>{activeType.name}</h2>
            </div>
          </header>

          <div className="copywriting-section-head">
            <h3>加工要求</h3>
            <button type="button" className="copywriting-ghost-btn">
              载入项目工件
            </button>
          </div>

          <div className="copywriting-form-grid">
            <label className="copywriting-field copywriting-field-wide">
              <span>具体需求</span>
              <textarea placeholder="例如：为一名看似散漫但很可靠的武器店老板生成 5 句首次见面台词，语气轻松但不要太现代。" />
            </label>

            <label className="copywriting-field">
              <span>用途</span>
              <input type="text" placeholder="例如：NPC 首次见面 / 商店介绍 / 任务完成" />
            </label>

            <label className="copywriting-field">
              <span>生成数量</span>
              <input
                type="number"
                min={1}
                max={30}
                value={quantity}
                onChange={(event) => {
                  const nextValue = Number(event.target.value);
                  setQuantity(Number.isFinite(nextValue) ? Math.min(30, Math.max(1, nextValue)) : 1);
                }}
              />
            </label>
          </div>

          <div className="copywriting-choice-row">
            <div>
              <span className="copywriting-choice-label">风格预设</span>
              <div className="copywriting-chip-row">
                {STYLE_PRESETS.map((style) => (
                  <button
                    key={style}
                    type="button"
                    className={`copywriting-chip${style === selectedStyle ? " is-active" : ""}`}
                    onClick={() => setSelectedStyle(style)}
                  >
                    {style}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <span className="copywriting-choice-label">长度</span>
              <div className="copywriting-chip-row">
                {LENGTH_PRESETS.map((length) => (
                  <button
                    key={length}
                    type="button"
                    className={`copywriting-chip${length === selectedLength ? " is-active" : ""}`}
                    onClick={() => setSelectedLength(length)}
                  >
                    {length}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="copywriting-constraint-grid">
            <label className="copywriting-field">
              <span>必须包含</span>
              <input type="text" placeholder="关键词、角色名、道具名" />
            </label>
            <label className="copywriting-field">
              <span>必须避免</span>
              <input type="text" placeholder="禁词、出戏表达、设定冲突" />
            </label>
          </div>

          <div className="copywriting-actions">
            <div className="copywriting-action-note">当前为前端样机，生成按钮后续接入策划 Agent。</div>
            <button type="button" className="copywriting-primary-btn" disabled>
              生成文案
            </button>
          </div>
        </section>

        <section className="copywriting-panel copywriting-result-panel">
          <div className="copywriting-section-head">
            <div>
              <span className="copywriting-kicker">Output</span>
              <h3>候选结果</h3>
            </div>
            <div className="copywriting-result-actions">
              <button type="button" disabled>导出 MD</button>
              <button type="button" disabled>导出 CSV</button>
            </div>
          </div>

          <div className="copywriting-empty-result">
            <strong>等待生成</strong>
            <span>后续这里会展示多条候选文案，并支持采用、重写、扩写、缩短和改风格。</span>
          </div>
        </section>
      </main>

      <aside className="copywriting-codex">
        <div className="copywriting-codex-head">
          <span className="copywriting-kicker">Codex</span>
          <strong>项目参考包</strong>
          <p>生成时优先参考项目工件、角色设定和术语表，避免文案脱离当前游戏。</p>
        </div>

        <div className="copywriting-codex-list">
          {CODEX_ITEMS.map((item) => (
            <div key={item.name} className={`copywriting-codex-item${item.active ? " is-active" : ""}`}>
              <div>
                <strong>{item.name}</strong>
                <span>{item.desc}</span>
              </div>
              <small>{item.active ? "已启用" : "待配置"}</small>
            </div>
          ))}
        </div>

      </aside>
    </div>
  );
}

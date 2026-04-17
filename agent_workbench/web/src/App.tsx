import { useState } from "react";

import { WorkbenchPage } from "./features/workbench/WorkbenchPage";

type TopLevelRoute = "workbench" | "settings";

function SettingsPageShell() {
  return (
    <div className="settings-shell">
      <div className="settings-shell-card">
        <div className="settings-shell-kicker">设置</div>
        <h1 className="settings-shell-title">项目设置</h1>
        <p className="settings-shell-text">
          这里将承载项目级配置。下一步我们会把工作区清单等能力放到这里，
          让设置与日常工作台流程保持分离。
        </p>
      </div>
    </div>
  );
}

export default function App() {
  const [route, setRoute] = useState<TopLevelRoute>("workbench");

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-brand">
          <div className="topbar-title">Ludens-Flow</div>
          <div className="topbar-subtitle">游戏开发工作台</div>
        </div>
        <nav className="topbar-tabs" aria-label="主导航">
          <button
            type="button"
            className={`topbar-tab${route === "workbench" ? " is-active" : ""}`}
            onClick={() => setRoute("workbench")}
          >
            工作台
          </button>
          <button
            type="button"
            className={`topbar-tab${route === "settings" ? " is-active" : ""}`}
            onClick={() => setRoute("settings")}
          >
            设置
          </button>
        </nav>
      </header>

      <main className="app-stage">
        {route === "workbench" ? <WorkbenchPage /> : <SettingsPageShell />}
      </main>
    </div>
  );
}

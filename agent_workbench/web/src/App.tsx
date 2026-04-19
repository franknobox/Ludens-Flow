import { useState } from "react";

import { SettingsPage } from "./features/settings/SettingsPage";
import { WorkbenchPage } from "./features/workbench/WorkbenchPage";

type TopLevelRoute = "workbench" | "settings";

export default function App() {
  const [route, setRoute] = useState<TopLevelRoute>("workbench");

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-block topbar-brand-box">
          <div className="topbar-brand">
            <div className="topbar-brand-line">
              <img
                className="topbar-logo"
                src="/LF.svg?v=2"
                alt="Ludens-Flow"
                width={44}
                height={44}
              />
              <div className="topbar-brand-text">
                <div className="topbar-title">Ludens-Flow</div>
                <div className="topbar-subtitle">游戏开发工作台</div>
              </div>
            </div>
          </div>
        </div>

        <div className="topbar-block topbar-center-box">
          <div id="topbar-center-slot" className="topbar-center-slot" />
        </div>

        <div className="topbar-block topbar-tabs-box">
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
        </div>
      </header>

      <main className="app-stage">
        <div className="app-stage-route" hidden={route !== "workbench"}>
          <WorkbenchPage isActive={route === "workbench"} />
        </div>
        <div className="app-stage-route" hidden={route !== "settings"}>
          <SettingsPage isActive={route === "settings"} />
        </div>
      </main>
    </div>
  );
}

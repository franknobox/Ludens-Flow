import { Suspense, lazy, useEffect, useState } from "react";

import { WelcomePage } from "./features/welcome/WelcomePage";
import { WorkbenchPage } from "./features/workbench/WorkbenchPage";
import { ProjectRuntimeProvider } from "./features/workbench/state/ProjectRuntimeContext";

const SettingsPage = lazy(() =>
  import("./features/settings/SettingsPage").then((module) => ({
    default: module.SettingsPage,
  })),
);

type TopLevelRoute = "workbench" | "settings";

function LazySettingsRoute({ isActive }: { isActive: boolean }) {
  const [shouldMount, setShouldMount] = useState(isActive);

  useEffect(() => {
    if (isActive) {
      setShouldMount(true);
    }
  }, [isActive]);

  if (!shouldMount) {
    return null;
  }

  return (
    <div className="app-stage-route" hidden={!isActive}>
      <Suspense fallback={<div className="route-loading">加载设置...</div>}>
        <SettingsPage isActive={isActive} />
      </Suspense>
    </div>
  );
}

export default function App() {
  const [route, setRoute] = useState<TopLevelRoute>("workbench");
  const [showWelcome, setShowWelcome] = useState(() => {
    return sessionStorage.getItem("ludens_welcome_seen") !== "1";
  });

  useEffect(() => {
    const savedTheme = localStorage.getItem("ludens_theme") || "light";
    document.documentElement.setAttribute("data-theme", savedTheme);
  }, []);

  useEffect(() => {
    if (!showWelcome) {
      return;
    }

    const timer = window.setTimeout(() => {
      sessionStorage.setItem("ludens_welcome_seen", "1");
      setShowWelcome(false);
    }, 1600);

    return () => window.clearTimeout(timer);
  }, [showWelcome]);

  if (showWelcome) {
    return <WelcomePage />;
  }

  return (
    <ProjectRuntimeProvider>
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
          <LazySettingsRoute isActive={route === "settings"} />
        </main>
      </div>
    </ProjectRuntimeProvider>
  );
}

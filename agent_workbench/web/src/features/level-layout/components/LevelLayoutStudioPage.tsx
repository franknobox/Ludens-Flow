import "../styles/level-layout.css";

const TOOL_URL = "/vendor/level-layout-studio/index.html";

interface LevelLayoutStudioPageProps {
  projectId: string;
}

export function LevelLayoutStudioPage({ projectId }: LevelLayoutStudioPageProps) {
  const toolUrl = `${TOOL_URL}?ludensProjectId=${encodeURIComponent(projectId)}`;

  return (
    <div className="level-layout-page">
      <header className="level-layout-header">
        <div className="level-layout-title-block">
          <div>
            <div className="level-layout-kicker">LEVEL LAYOUT STUDIO</div>
            <h1>关卡设计台</h1>
          </div>
        </div>
        <div className="level-layout-meta">
          <span className="level-layout-source">Source: kluiyao.itch.io</span>
        </div>
      </header>

      <div className="level-layout-frame-wrap">
        <iframe
          className="level-layout-frame"
          title="Level Layout Studio"
          src={toolUrl}
          sandbox="allow-scripts allow-same-origin allow-downloads allow-forms allow-popups"
          allow="fullscreen; clipboard-read; clipboard-write; web-share"
        />
      </div>
    </div>
  );
}

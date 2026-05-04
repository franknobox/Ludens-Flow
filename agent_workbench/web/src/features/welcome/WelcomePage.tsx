export function WelcomePage() {
  return (
    <div className="welcome-page" aria-label="Ludens-Flow loading">
      <div className="welcome-mark">
        <img src="/LF.svg?v=2" alt="Ludens-Flow" width={104} height={104} />
      </div>
      <div className="welcome-progress" aria-hidden="true">
        <span />
      </div>
    </div>
  );
}

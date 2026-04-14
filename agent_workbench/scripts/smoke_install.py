import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen


def run(command: list[str], cwd: Path, env: dict[str, str]) -> None:
    print(f"$ {' '.join(command)}")
    subprocess.run(command, cwd=str(cwd), env=env, check=True)


def wait_http_ok(url: str, timeout_seconds: float) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Smoke test editable install and startup"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8020)
    parser.add_argument("--skip-install", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    workbench_root = repo_root / "agent_workbench"
    env = os.environ.copy()

    if not args.skip_install:
        run(
            [sys.executable, "-m", "pip", "install", "-e", str(workbench_root)],
            cwd=repo_root,
            env=env,
        )

    run(
        [sys.executable, "-m", "ludens_flow.app.cli", "--help"],
        cwd=repo_root,
        env=env,
    )
    run(
        [sys.executable, "-m", "ludens_flow.app.api", "--help"],
        cwd=repo_root,
        env=env,
    )

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "ludens_flow.app.api:app",
            "--host",
            args.host,
            "--port",
            str(args.port),
        ],
        cwd=str(repo_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        url = f"http://{args.host}:{args.port}/api/state"
        if not wait_http_ok(url, timeout_seconds=20):
            raise RuntimeError(f"Startup smoke failed: {url} not ready")
        print(f"Smoke OK: {url}")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    main()

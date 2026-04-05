import importlib
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parent
HEALTH_URL = "http://127.0.0.1:7860/health"
DASHBOARD_URL = "http://127.0.0.1:7860/dashboard"


def is_server_live() -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=1.5) as response:
            return response.status == 200
    except Exception:
        return False


def ensure_dependencies() -> None:
    modules = ["fastapi", "uvicorn", "openai", "requests"]
    missing = []
    for module in modules:
        try:
            importlib.import_module(module)
        except Exception:
            missing.append(module)

    if missing:
        print(f"Installing missing dependencies: {', '.join(missing)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])


def wait_for_server(timeout_seconds: int = 45) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if is_server_live():
            return True
        time.sleep(0.5)
    return False


def main() -> None:
    if is_server_live():
        print("JalGuard server already running. Opening dashboard...")
        webbrowser.open(DASHBOARD_URL)
        return

    ensure_dependencies()

    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "7860",
    ]

    print("Starting JalGuard server...")
    process = subprocess.Popen(command, cwd=str(ROOT))

    try:
        if wait_for_server():
            print("Server is live. Opening dashboard...")
            webbrowser.open(DASHBOARD_URL)
        else:
            print("Server did not start in time. Check logs for errors.")
        process.wait()
    except KeyboardInterrupt:
        print("Stopping JalGuard server...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    main()

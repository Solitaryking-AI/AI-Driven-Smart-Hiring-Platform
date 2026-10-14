"""
SmartHire AI - Application Launcher
-------------------------------------
Starts both the FastAPI backend (port 8000) and Streamlit frontend (port 8501)
with a single command across Windows, macOS, and Linux.

Usage:
    python run.py
"""

import os
import signal
import subprocess
import sys
import time

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable


def main():
    print("=" * 60)
    print("  SmartHire AI - AI-Powered Recruitment Platform")
    print("  Role-Based Copilot: Candidate | Recruiter | Admin")
    print("=" * 60)
    print()

    # Start FastAPI backend (port 8000)
    print("[1/2] Starting FastAPI backend on http://127.0.0.1:8000 ...")
    backend_proc = subprocess.Popen(
        [PYTHON, "api.py"],
        cwd=PROJECT_DIR,
        stdout=None,
        stderr=None,
    )
    # Give backend a moment to initialize
    time.sleep(2)

    if backend_proc.poll() is not None:
        print("[ERROR] Backend failed to start!")
        sys.exit(1)

    print(f"[OK] Backend running (PID: {backend_proc.pid})")
    print()

    # Start Streamlit frontend (port 8501)
    print("[2/2] Starting Streamlit frontend on http://127.0.0.1:8501 ...")
    frontend_proc = subprocess.Popen(
        [PYTHON, "-m", "streamlit", "run", "app.py", "--server.port", "8501", "--server.headless", "true"],
        cwd=PROJECT_DIR,
        stdout=None,
        stderr=None,
    )
    time.sleep(2)

    if frontend_proc.poll() is not None:
        print("[ERROR] Frontend failed to start!")
        backend_proc.terminate()
        sys.exit(1)

    print(f"[OK] Frontend running (PID: {frontend_proc.pid})")
    print()
    print("=" * 60)
    print("  SmartHire AI is ready!")
    print()
    print("  Frontend:  http://127.0.0.1:8501")
    print("  Backend:   http://127.0.0.1:8000")
    print("  API Docs:  http://127.0.0.1:8000/docs")
    print()
    print("  Press Ctrl+C to stop both servers.")
    print("=" * 60)

    def shutdown(sig, frame):
        print("\n\nShutting down SmartHire AI services...")
        try:
            backend_proc.terminate()
        except Exception:
            pass
        try:
            frontend_proc.terminate()
        except Exception:
            pass
        try:
            backend_proc.wait(timeout=5)
        except Exception:
            backend_proc.kill()
        try:
            frontend_proc.wait(timeout=5)
        except Exception:
            frontend_proc.kill()
        print("Both servers stopped. Goodbye!")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown)

    # Keep main process alive
    try:
        while True:
            if backend_proc.poll() is not None:
                print("\n[WARNING] Backend process exited unexpectedly.")
                frontend_proc.terminate()
                sys.exit(1)
            if frontend_proc.poll() is not None:
                print("\n[WARNING] Frontend process exited unexpectedly.")
                backend_proc.terminate()
                sys.exit(1)
            time.sleep(2)
    except KeyboardInterrupt:
        shutdown(None, None)


if __name__ == "__main__":
    main()

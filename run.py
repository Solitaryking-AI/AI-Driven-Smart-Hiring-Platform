"""
SmartHire AI - Application Launcher
-------------------------------------
Starts both the FastAPI backend (port 8000) and Streamlit frontend (port 8501)
with a single command.

Usage:
    python run.py
"""

import subprocess
import sys
import os
import time
import signal

PYTHON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv", "Scripts", "python.exe")
STREAMLIT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv", "Scripts", "streamlit.exe")
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    print("=" * 60)
    print("  SmartHire AI - Recruitment Copilot")
    print("  Milestone 1: Resume Parsing & Candidate Profiling")
    print("=" * 60)
    print()

    # Start FastAPI backend
    print("[1/2] Starting FastAPI backend on http://localhost:8000 ...")
    backend_proc = subprocess.Popen(
        [PYTHON, "api.py"],
        cwd=PROJECT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    # Give backend a moment to start
    time.sleep(3)

    if backend_proc.poll() is not None:
        print("[ERROR] Backend failed to start!")
        out = backend_proc.stdout.read()
        print(out)
        sys.exit(1)

    print("[OK] Backend running (PID: {})".format(backend_proc.pid))
    print()

    # Start Streamlit frontend
    print("[2/2] Starting Streamlit frontend on http://localhost:8501 ...")
    frontend_proc = subprocess.Popen(
        [STREAMLIT, "run", "app.py", "--server.port", "8501", "--server.headless", "true"],
        cwd=PROJECT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    time.sleep(3)

    if frontend_proc.poll() is not None:
        print("[ERROR] Frontend failed to start!")
        out = frontend_proc.stdout.read()
        print(out)
        backend_proc.terminate()
        sys.exit(1)

    print("[OK] Frontend running (PID: {})".format(frontend_proc.pid))
    print()
    print("=" * 60)
    print("  SmartHire AI is ready!")
    print()
    print("  Frontend:  http://localhost:8501")
    print("  Backend:   http://localhost:8000")
    print("  API Docs:  http://localhost:8000/docs")
    print()
    print("  Press Ctrl+C to stop both servers.")
    print("=" * 60)

    def shutdown(sig, frame):
        print("\n\nShutting down...")
        backend_proc.terminate()
        frontend_proc.terminate()
        backend_proc.wait()
        frontend_proc.wait()
        print("Both servers stopped. Goodbye!")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Keep main process alive
    try:
        while True:
            # Check if either process died
            if backend_proc.poll() is not None:
                print("[WARNING] Backend process exited unexpectedly.")
                frontend_proc.terminate()
                sys.exit(1)
            if frontend_proc.poll() is not None:
                print("[WARNING] Frontend process exited unexpectedly.")
                backend_proc.terminate()
                sys.exit(1)
            time.sleep(2)
    except KeyboardInterrupt:
        shutdown(None, None)


if __name__ == "__main__":
    main()

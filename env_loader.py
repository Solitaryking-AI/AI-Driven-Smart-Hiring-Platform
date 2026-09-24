"""
SmartHire AI - Environment Loader
Safely loads key-value pairs from .env in the project root into os.environ.
Zero third-party dependencies.
"""

import os


def load_env() -> None:
    """Load key-value pairs from .env into os.environ if present."""
    project_root = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(project_root, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k and v and not v.startswith("your_"):
                            os.environ[k] = v
        except Exception:
            pass


# Automatically load on import
load_env()

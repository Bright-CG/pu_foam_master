"""Load scraper/.env into os.environ (does not override existing env)."""

import os
from typing import Optional

_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ENV_FILE = os.path.join(_ROOT, ".env")


def load_scraper_env(path: Optional[str] = None) -> str:
    env_path = path or os.environ.get("SCRAPER_ENV_FILE") or DEFAULT_ENV_FILE
    if not os.path.isfile(env_path):
        return env_path
    with open(env_path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
    return env_path

from __future__ import annotations

import os
from pathlib import Path


def default_db_path() -> Path:
    configured = os.getenv("NUTRITION_DB")
    if configured:
        return Path(configured).expanduser()
    return Path("~/.nutrition/nutrition.db").expanduser()


def fdc_api_key() -> str:
    configured = os.getenv("FDC_API_KEY") or os.getenv("NUTRITION_FDC_API_KEY")
    if configured:
        return configured

    key_file = Path(os.getenv("NUTRITION_FDC_API_KEY_FILE", "~/.nutrition/fdc_api_key")).expanduser()
    if key_file.exists():
        value = key_file.read_text().strip()
        if value:
            return value

    return "DEMO_KEY"

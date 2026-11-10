"""Shared reporting settings: environment overrides local JSON, then defaults."""
import json
import os
from pathlib import Path

_config_path = Path(__file__).with_name("var_config.local.json")
_local = json.loads(_config_path.read_text(encoding="utf-8-sig")) if _config_path.exists() else {}


def _setting(name, default="", env_name=None):
    return os.environ.get(env_name or name, _local.get(name, default))


DB_HOST = _setting("DB_HOST", env_name="DB_HOST_STELLARRISK")
DB_USER = _setting("DB_USER", env_name="DB_USER_STELLARRISK")
DB_PASS = _setting("DB_PASS", env_name="DB_PASS_STELLARRISK")
DB_NAME = _setting("DB_NAME", "stellarrisk", env_name="DB_NAME_STELLARRISK")
GOOGLE_SHEET_ID = _setting("GOOGLE_SHEET_ID")
GOOGLE_SHEET_TAB = _setting("GOOGLE_SHEET_TAB", "Sheet1")
GOOGLE_CREDENTIALS_FILE = _setting("GOOGLE_CREDENTIALS_FILE", "google-credentials.json")

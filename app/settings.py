"""Shared helpers: read config/rag.yaml, find the git commit, open a Snowpark session."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "rag.yaml"


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def git_commit() -> str:
    """Commit SHA from GitHub Actions, else from the local checkout, else 'unknown'."""
    if os.environ.get("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"]
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def app_version(cfg: dict) -> str:
    """Short commit plus the settings that change between experiments."""
    label = (
        f"k{cfg['top_k']}-c{cfg['chunk_size']}-o{cfg['overlap']}"
        f"-{cfg['prompt_version']}-{cfg['model']}"
    )
    if cfg.get("settings_label"):
        label += f"-{cfg['settings_label']}"
    return f"{git_commit()[:7]}-{label}"


def get_session():
    """Snowpark session.

    In GitHub Actions: key-pair auth from SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PRIVATE_KEY_FILE.
    On a laptop: a named connection from ~/.snowflake/config.toml (SNOWFLAKE_CONNECTION, default 'default').
    """
    from snowflake.snowpark import Session

    cfg = load_config()["snowflake"]
    if os.environ.get("SNOWFLAKE_PRIVATE_KEY_FILE"):
        params = {
            "account": os.environ["SNOWFLAKE_ACCOUNT"],
            "user": os.environ["SNOWFLAKE_USER"],
            "authenticator": "SNOWFLAKE_JWT",
            # VERIFY: "private_key_file" key name in snowflake-connector-python
            "private_key_file": os.environ["SNOWFLAKE_PRIVATE_KEY_FILE"],
        }
    else:
        # VERIFY: connection_name support in Session.builder.configs
        params = {"connection_name": os.environ.get("SNOWFLAKE_CONNECTION", "default")}
    params.update(
        {"role": cfg["role"], "warehouse": cfg["warehouse"], "database": cfg["database"]}
    )
    return Session.builder.configs(params).create()

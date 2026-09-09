"""Configuration and schema loading utilities.

This module centralizes access to YAML configuration files and the data
contract (``schema.yaml``) so that no other module needs to hard-code paths.
"""

import os
import yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_config(env: str = "dev") -> dict:
    """Load the YAML configuration for the given environment.

    Reads ``config/{env}.yaml`` relative to the project root and optionally
    overrides the storage base path via the ``STORAGE_BASE_PATH`` environment
    variable.

    Args:
        env (str): Environment identifier (e.g. ``"dev"``, ``"test"``,
            ``"prod"``).  Defaults to ``"dev"``.

    Returns:
        dict: Parsed configuration dictionary containing storage paths,
        logging settings, metrics output location, and alert endpoints.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
    """
    config_path = PROJECT_ROOT / "config" / f"{env}.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Config file {config_path} not found")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    # Optional environment-variable override
    # e.g. if STORAGE_BASE_PATH is set, override the configured base path
    if os.getenv("STORAGE_BASE_PATH"):
        config["storage"]["base_path"] = os.getenv("STORAGE_BASE_PATH")
    # Anchor artifact paths (metrics file, log file) under the environment's
    # storage base path so each env keeps its own artifacts and the repo root
    # stays clean (dev → data/, test → test/data/, prod → data_prod/).
    _anchor_to_base(config, "metrics", "output_file")
    _anchor_to_base(config, "logging", "file")
    return config


def _anchor_to_base(config: dict, section: str, key: str) -> None:
    """Rewrite a relative path in ``config[section][key]`` to live under
    ``storage.base_path`` (absolute paths pass through unchanged)."""
    value = config.get(section, {}).get(key)
    if not value:
        return
    path = Path(value)
    if not path.is_absolute():
        config[section][key] = str(Path(config["storage"]["base_path"]) / path)


def load_schema() -> dict:
    """Load the data contract schema.yaml from the project config directory.

    Returns:
        dict: Parsed schema dictionary defining fields, types, required
        flags, enum values, and regex patterns.

    Raises:
        FileNotFoundError: If ``config/schema.yaml`` does not exist.
    """
    schema_path = PROJECT_ROOT / "config" / "schema.yaml"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file {schema_path} not found")
    with open(schema_path, "r") as f:
        return yaml.safe_load(f)

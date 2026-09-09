import os
import yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def load_config(env: str = "dev") -> dict:
    config_path = PROJECT_ROOT / "config" / f"{env}.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Config file {config_path} not found")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    # 环境变量覆盖（可选）
    # 例如：若设置了 STORAGE_BASE_PATH，则覆盖
    if os.getenv("STORAGE_BASE_PATH"):
        config["storage"]["base_path"] = os.getenv("STORAGE_BASE_PATH")
    return config

def load_schema() -> dict:
    """加载数据契约 schema.yaml（位于项目根 config/ 下）。"""
    schema_path = PROJECT_ROOT / "config" / "schema.yaml"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file {schema_path} not found")
    with open(schema_path, "r") as f:
        return yaml.safe_load(f)
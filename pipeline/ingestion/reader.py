import pandas as pd
from pathlib import Path
import json

def read_input(file_path: str) -> pd.DataFrame:
    """
    读取文件，支持 .json, .csv, .parquet。
    对 JSON 文件，按行读取（lines=True）。
    添加 _raw_json 列。
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Input file {file_path} not found")
    suffix = path.suffix.lower()
    if suffix == ".json":
        df = pd.read_json(path, lines=True)
    elif suffix == ".csv":
        df = pd.read_csv(path)
    elif suffix == ".parquet":
        df = pd.read_parquet(path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")
    # 添加原始 JSON 列（用于审计）
    # 注意：对于 DataFrame，每行转 JSON
    df["_raw_json"] = df.apply(lambda row: row.to_json(), axis=1)
    return df

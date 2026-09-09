import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path


class JsonFormatter(logging.Formatter):
    """结构化日志格式：每条日志输出为一行 JSON（便于采集与审计）。"""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def setup_logging(level: str = "INFO", log_file: str | None = None) -> logging.Logger:
    """配置并返回名为 pipeline 的 logger：输出到 stdout，可选追加文件。幂等，可重复调用。"""
    logger = logging.getLogger("pipeline")
    logger.setLevel(level.upper())
    if not logger.handlers:  # 幂等：已有 handler 则跳过，避免重复输出
        formatter = JsonFormatter()
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        if log_file:
            path = Path(log_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(path, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        logger.propagate = False
    return logger


def get_logger(name: str = "pipeline") -> logging.Logger:
    """获取 pipeline logger（供各模块复用，需先调用 setup_logging）。"""
    return logging.getLogger(name)

import json
from datetime import datetime
from pathlib import Path

class MetricsCollector:
    def __init__(self):
        self.metrics = {
            "start_time": datetime.utcnow().isoformat(),
            "input_rows": 0,
            "valid_rows": 0,
            "invalid_rows": 0,
            "duplicates_removed": 0,
            "silver_rows": 0,
            "gold_rows": 0,
            "errors": [],
        }
    def increment(self, key, value=1):
        if key in self.metrics:
            self.metrics[key] += value
        else:
            self.metrics[key] = value
    def set(self, key, value):
        self.metrics[key] = value
    def add_error(self, error_msg):
        self.metrics["errors"].append(error_msg)
    def save(self, output_path):
        self.metrics["end_time"] = datetime.utcnow().isoformat()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(self.metrics, f, indent=2)

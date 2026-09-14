# [AI-GENERATED] model=deepseek-flash date=2026-09-09 reviewed_by=pending
"""Metrics collection for pipeline runs.

Provides a lightweight collector that tracks row counts, error messages,
and timing information, then persists them to a JSON file.
"""

import json
from datetime import datetime, timezone
from pathlib import Path


class MetricsCollector:
    """Collects and persists pipeline execution metrics.

    Tracks input row counts, validation pass/fail counts, deduplication
    stats, Gold-layer row counts, and a list of error messages.  Results
    are saved as a JSON file for monitoring and SLA evaluation.
    """

    def __init__(self):
        """Initialize the metrics collector with default values.

        The ``start_time`` is recorded at construction; ``end_time`` is set
        when :meth:`save` is called.
        """
        self.metrics = {
            "start_time": datetime.now(timezone.utc).isoformat(),
            "input_rows": 0,
            "valid_rows": 0,
            "invalid_rows": 0,
            "duplicates_removed": 0,
            "silver_rows": 0,
            "gold_rows": 0,
            "errors": [],
        }

    def increment(self, key, value=1):
        """Increment a metric counter by the given value.

        If the key does not yet exist, it is created.

        Args:
            key (str): The metric key to increment.
            value (int): Amount to add.  Defaults to 1.
        """
        if key in self.metrics:
            self.metrics[key] += value
        else:
            self.metrics[key] = value

    def set(self, key, value):
        """Set a metric to an explicit value, overwriting any prior value.

        Args:
            key (str): The metric key.
            value: The value to set.
        """
        self.metrics[key] = value

    def add_error(self, error_msg):
        """Append an error message to the error list.

        Args:
            error_msg (str): A human-readable error description.
        """
        self.metrics["errors"].append(error_msg)

    def save(self, output_path):
        """Persist the collected metrics to a JSON file.

        Records the ``end_time``, creates parent directories if needed,
        and writes the metrics dictionary as indented JSON.

        Args:
            output_path (str): Path to the output JSON file.
        """
        self.metrics["end_time"] = datetime.now(timezone.utc).isoformat()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(self.metrics, f, indent=2)

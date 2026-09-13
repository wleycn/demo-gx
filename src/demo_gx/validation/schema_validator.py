"""Schema validation module.

Implements strict-mode validation against the data contract defined in
``config/schema.yaml``.  Validates field existence, types, enum membership,
regex patterns, and minimum values, then splits the DataFrame into valid
and invalid partitions with per-row error reasons.
"""

import pandas as pd
import re
import json
from datetime import datetime
import uuid

from demo_gx.common.time_utils import parse_utc_mixed


class SchemaValidator:
    """Validates a DataFrame against a schema contract.

    The validator operates in strict mode: it rejects unknown fields, checks
    required field presence, validates types (string, number, timestamp),
    and enforces constraints such as max length, regex patterns, enum
    values, and numeric minimums.

    Attributes:
        schema (dict): The raw schema configuration dictionary.
        expected_fields (set): Names of all fields defined in the schema.
        field_rules (dict): Per-field rule dictionaries (type, required,
            enum, pattern, etc.).
    """

    def __init__(self, schema_config, run_ts: pd.Timestamp):
        """Initialize the validator with a schema configuration.

        Args:
            schema_config (dict): Parsed ``schema.yaml`` content containing
                a ``fields`` key mapping field names to rule dictionaries.
            run_ts (pandas.Timestamp): The run instant, injected by the caller.
                Used as the reference for the ``<= current time`` rule, so a
                given run validates reproducibly (AGENTS.md section 3 red
                line 10).
        """
        self.schema = schema_config
        self.expected_fields = set(schema_config["fields"].keys())
        self.field_rules = schema_config["fields"]
        self.run_ts = run_ts

    def validate(self, df: pd.DataFrame) -> tuple:
        """Validate the DataFrame against the schema contract.

        Performs the following checks in order:
        1. Detects and removes extra (unknown) fields, marking affected rows.
        2. For each declared field, validates type, length, pattern, enum,
           and minimum constraints.
        3. Checks for null values in required fields.

        Returns a tuple of (valid_df, invalid_df).  The ``invalid_df``
        includes an ``error_reason`` column describing each violation;
        the ``valid_df`` has internal columns dropped.

        Args:
            df (pandas.DataFrame): The raw input DataFrame, typically
                including a ``_raw_json`` audit column.

        Returns:
            tuple: A pair ``(valid_df, invalid_df)`` of DataFrames.  Rows
            that pass all checks are in ``valid_df``; failing rows (with
            an ``error_reason`` column) are in ``invalid_df``.
        """
        # Copy first to avoid mutating the caller's DataFrame
        df = df.copy()
        # Initialize error-reason column (always present to avoid downstream
        # read/write errors on a non-existent column)
        df["_error_reason"] = ""
        invalid_mask = pd.Series(False, index=df.index)
        # 1. Check for extra (unknown) fields
        actual_fields = set(df.columns)
        # Exclude internal columns (_raw_json audit column, _error_reason
        # error column) so they are not mistaken for extra schema fields
        extra_fields = actual_fields - self.expected_fields - {"_raw_json", "_error_reason"}
        if extra_fields:
            # Strict mode: reject rows whose ORIGINAL record carries any
            # undeclared key. Row-level key presence is judged from the
            # preserved raw JSON when available — a null extra value and a
            # missing key are indistinguishable after pandas read_json, so
            # column-level notna() is only a fallback (dev-review: batch-
            # dependent judging). Fallback used by unit tests without _raw_json.
            if "_raw_json" in df.columns:
                def _has_extra_key(raw: str) -> bool:
                    try:
                        return bool(set(json.loads(raw)) & extra_fields)
                    except Exception:
                        return False
                extra_mask = df["_raw_json"].map(_has_extra_key).astype(bool)
            else:
                extra_mask = df[list(extra_fields)].notna().any(axis=1)
            if not extra_mask.any():
                invalid_mask = invalid_mask | True
                df["_error_reason"] = df["_error_reason"] + f" Extra fields (present in input): {extra_fields};"
            else:
                invalid_mask = invalid_mask | extra_mask
                df.loc[extra_mask, "_error_reason"] = df.loc[extra_mask, "_error_reason"].fillna("") + f" Extra fields: {extra_fields};"
            # Drop extra field columns (keep only standard fields + _raw_json)
            df = df.drop(columns=list(extra_fields))

        # 2. Per-field validation
        for field, rules in self.field_rules.items():
            if field not in df.columns:
                # Missing required field
                if rules.get("required", False):
                    invalid_mask = invalid_mask | True  # entire row invalid
                    df["_error_reason"] = df.get("_error_reason", "") + f" Missing required field: {field};"
                continue
            series = df[field]
            # Type validation
            expected_type = rules.get("type")
            if expected_type == "string":
                # Reject compound values (dict/list/tuple): only scalars are
                # acceptable strings — str() repr of a dict must not pass as
                # a customer id (round-2 QC #9)
                non_scalar = series.apply(lambda v: isinstance(v, (dict, list, tuple)))
                if non_scalar.any():
                    invalid_mask = invalid_mask | non_scalar
                    df.loc[non_scalar, "_error_reason"] = df.loc[non_scalar, "_error_reason"].fillna("") + f" Field {field} not a scalar string;"
                # Ensure the column is string-typed
                if not pd.api.types.is_string_dtype(series):
                    # Attempt conversion
                    try:
                        df[field] = series.astype(str)
                    except:
                        invalid_mask = invalid_mask | True
                        df.loc[series.index, "_error_reason"] = df.loc[series.index, "_error_reason"].fillna("") + f" Field {field} not string;"
                # Length constraint
                if "max_length" in rules:
                    too_long = df[field].str.len() > rules["max_length"]
                    if too_long.any():
                        invalid_mask = invalid_mask | too_long
                        df.loc[too_long, "_error_reason"] = df.loc[too_long, "_error_reason"].fillna("") + f" Field {field} exceeds max length;"
                # Regex pattern
                if "pattern" in rules:
                    pattern = rules["pattern"]
                    match_failed = ~df[field].str.match(pattern, na=False)
                    invalid_mask = invalid_mask | match_failed
                    df.loc[match_failed, "_error_reason"] = df.loc[match_failed, "_error_reason"].fillna("") + f" Field {field} pattern mismatch;"
                # Enum check
                if "enum" in rules:
                    not_in_enum = ~df[field].isin(rules["enum"])
                    invalid_mask = invalid_mask | not_in_enum
                    df.loc[not_in_enum, "_error_reason"] = df.loc[not_in_enum, "_error_reason"].fillna("") + f" Field {field} not in enum;"
            elif expected_type == "number":
                # Coerce to numeric without raising: unconvertible values
                # become NaN and are quarantined row-by-row below (a failed
                # coercion must never crash the whole batch).
                if not pd.api.types.is_numeric_dtype(series):
                    df[field] = pd.to_numeric(df[field], errors="coerce")
                # Rows that were originally non-null but failed coercion
                non_numeric = df[field].isna() & series.notna()
                if non_numeric.any():
                    invalid_mask = invalid_mask | non_numeric
                    df.loc[non_numeric, "_error_reason"] = df.loc[non_numeric, "_error_reason"].fillna("") + f" Field {field} not numeric;"
                # Minimum value (column is numeric now, so NaN comparisons are safe)
                if "minimum" in rules:
                    below_min = df[field].notna() & (df[field] < rules["minimum"])
                    invalid_mask = invalid_mask | below_min
                    df.loc[below_min, "_error_reason"] = df.loc[below_min, "_error_reason"].fillna("") + f" Field {field} below minimum;"
                # Non-finite values (inf after coercion) must not pollute sums
                non_finite = df[field].isin([float("inf"), float("-inf")])
                if non_finite.any():
                    invalid_mask = invalid_mask | non_finite
                    df.loc[non_finite, "_error_reason"] = df.loc[non_finite, "_error_reason"].fillna("") + f" Field {field} not finite;"
                # Precision: at most N decimal places when schema declares it
                if "max_decimals" in rules:
                    scaled = df[field] * 10 ** rules["max_decimals"]
                    too_precise = df[field].notna() & ((scaled - scaled.round()).abs() > 1e-6)
                    if too_precise.any():
                        invalid_mask = invalid_mask | too_precise
                        df.loc[too_precise, "_error_reason"] = df.loc[too_precise, "_error_reason"].fillna("") + f" Field {field} exceeds {rules['max_decimals']} decimal places;"
            elif expected_type == "timestamp":
                # Attempt to parse as datetime and check parseability
                # Back up the original string first, in case parsing fails
                df[f"_raw_{field}"] = df[field]  # backup original value
                # Shared parsing policy: mixed formats tolerated, no raise
                dt_series = parse_utc_mixed(df[field])
                # Rows where parsing failed (original non-null but result NaT)
                failed_parse = df[field].notna() & dt_series.isna()
                if failed_parse.any():
                    invalid_mask = invalid_mask | failed_parse
                    df.loc[failed_parse, "_error_reason"] = df.loc[failed_parse, "_error_reason"].fillna("") + f" Field {field} timestamp parse failed;"
                # Reject future timestamps: the schema contract requires
                # "<= current time" (see docs/business/PROJECT.md source-schema
                # table); a record stamped in the future is quarantined here
                # together with parse failures rather than silently passing.
                now_utc = self.run_ts
                in_future = dt_series > now_utc  # NaT > now is False
                if in_future.any():
                    invalid_mask = invalid_mask | in_future
                    df.loc[in_future, "_error_reason"] = df.loc[in_future, "_error_reason"].fillna("") + f" Field {field} in future;"
                df[field] = dt_series  # converted UTC datetime
            # Other types...
        # Handle null values for required fields
        for field, rules in self.field_rules.items():
            if rules.get("required", False) and field in df.columns:
                missing = df[field].isna()
                invalid_mask = invalid_mask | missing
                df.loc[missing, "_error_reason"] = df.loc[missing, "_error_reason"].fillna("") + f" Field {field} is null;"

        # Split into valid / invalid partitions
        invalid_df = df[invalid_mask].copy()
        valid_df = df[~invalid_mask].copy()
        # invalid_df: rename _error_reason to error_reason; valid_df: drop
        # internal columns
        invalid_df = invalid_df.rename(columns={"_error_reason": "error_reason"})
        valid_df = valid_df.drop(columns=["_error_reason"], errors="ignore")
        return valid_df, invalid_df

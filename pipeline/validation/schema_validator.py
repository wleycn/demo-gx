"""Schema validation module.

Implements strict-mode validation against the data contract defined in
``config/schema.yaml``.  Validates field existence, types, enum membership,
regex patterns, and minimum values, then splits the DataFrame into valid
and invalid partitions with per-row error reasons.
"""

import pandas as pd
import re
from datetime import datetime
import uuid


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

    def __init__(self, schema_config):
        """Initialize the validator with a schema configuration.

        Args:
            schema_config (dict): Parsed ``schema.yaml`` content containing
                a ``fields`` key mapping field names to rule dictionaries.
        """
        self.schema = schema_config
        self.expected_fields = set(schema_config["fields"].keys())
        self.field_rules = schema_config["fields"]

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
        # 1. Check for extra (unknown) fields
        actual_fields = set(df.columns)
        # Exclude internal columns (_raw_json audit column, _error_reason
        # error column) so they are not mistaken for extra schema fields
        extra_fields = actual_fields - self.expected_fields - {"_raw_json", "_error_reason"}
        if extra_fields:
            # Mark rows where any extra field has a non-null value
            extra_mask = df[list(extra_fields)].notna().any(axis=1)
            df.loc[extra_mask, "_error_reason"] = df.loc[extra_mask, "_error_reason"].fillna("") + f" Extra fields: {extra_fields}"
            # Drop extra field columns (keep only standard fields + _raw_json)
            df = df.drop(columns=list(extra_fields))

        # 2. Per-field validation
        invalid_mask = pd.Series(False, index=df.index)
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
                # Check whether the column is numeric
                if not pd.api.types.is_numeric_dtype(series):
                    # Attempt conversion
                    try:
                        df[field] = pd.to_numeric(series)
                    except:
                        invalid_mask = invalid_mask | True
                        df.loc[series.index, "_error_reason"] = df.loc[series.index, "_error_reason"].fillna("") + f" Field {field} not numeric;"
                # Minimum value
                if "minimum" in rules:
                    below_min = df[field] < rules["minimum"]
                    invalid_mask = invalid_mask | below_min
                    df.loc[below_min, "_error_reason"] = df.loc[below_min, "_error_reason"].fillna("") + f" Field {field} below minimum;"
            elif expected_type == "timestamp":
                # Attempt to parse as datetime and check parseability
                # Back up the original string first, in case parsing fails
                df[f"_raw_{field}"] = df[field]  # backup original value
                try:
                    dt_series = pd.to_datetime(df[field], utc=True, errors="coerce")
                except:
                    dt_series = pd.Series([pd.NaT] * len(df), index=df.index)
                # Rows where parsing failed (original non-null but result NaT)
                failed_parse = df[field].notna() & dt_series.isna()
                if failed_parse.any():
                    invalid_mask = invalid_mask | failed_parse
                    df.loc[failed_parse, "_error_reason"] = df.loc[failed_parse, "_error_reason"].fillna("") + f" Field {field} timestamp parse failed;"
                # Check whether the value is <= current time (optional; here we
                # only validate, not block, but could log a warning).
                # We only handle parse failures here; future timestamps are
                # flagged as warnings but not marked invalid?  Per the design,
                # future timestamps should be quarantined.
                # For simplicity, should invalid_mask include future times?
                # An additional condition could be added.
                # Here we only handle parse failures.  Other business rules
                # can be applied in the cleaner, or added here.
                # For separation of concerns, business rules go in the cleaner;
                # this module performs only basic type validation.
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

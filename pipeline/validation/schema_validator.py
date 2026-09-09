import pandas as pd
import re
from datetime import datetime
import uuid

class SchemaValidator:
    def __init__(self, schema_config):
        self.schema = schema_config
        self.expected_fields = set(schema_config["fields"].keys())
        self.field_rules = schema_config["fields"]
    
    def validate(self, df: pd.DataFrame) -> tuple:
        """
        返回 (valid_df, invalid_df)
        invalid_df 包含原始行及 error_reason 列
        """
        # 先复制，避免修改原df
        df = df.copy()
        # 初始化错误原因列（恒存在，避免后续对不存在列的读写崩溃）
        df["_error_reason"] = ""
        # 1. 检查额外字段
        actual_fields = set(df.columns)
        # 排除内部列（_raw_json 审计列、_error_reason 错误列），避免被误判为额外字段
        extra_fields = actual_fields - self.expected_fields - {"_raw_json", "_error_reason"}
        if extra_fields:
            # 标记含有额外字段的行（只要这些字段非空）
            extra_mask = df[list(extra_fields)].notna().any(axis=1)
            df.loc[extra_mask, "_error_reason"] = df.loc[extra_mask, "_error_reason"].fillna("") + f" Extra fields: {extra_fields}"
            # 删除额外字段列（只保留标准字段 + _raw_json）
            df = df.drop(columns=list(extra_fields))
        
        # 2. 逐字段校验
        invalid_mask = pd.Series(False, index=df.index)
        for field, rules in self.field_rules.items():
            if field not in df.columns:
                # 缺失必填字段
                if rules.get("required", False):
                    invalid_mask = invalid_mask | True  # 整行无效
                    df["_error_reason"] = df.get("_error_reason", "") + f" Missing required field: {field};"
                continue
            series = df[field]
            # 类型校验
            expected_type = rules.get("type")
            if expected_type == "string":
                # 确保是字符串
                if not pd.api.types.is_string_dtype(series):
                    # 尝试转换
                    try:
                        df[field] = series.astype(str)
                    except:
                        invalid_mask = invalid_mask | True
                        df.loc[series.index, "_error_reason"] = df.loc[series.index, "_error_reason"].fillna("") + f" Field {field} not string;"
                # 长度限制
                if "max_length" in rules:
                    too_long = df[field].str.len() > rules["max_length"]
                    if too_long.any():
                        invalid_mask = invalid_mask | too_long
                        df.loc[too_long, "_error_reason"] = df.loc[too_long, "_error_reason"].fillna("") + f" Field {field} exceeds max length;"
                # 正则
                if "pattern" in rules:
                    pattern = rules["pattern"]
                    match_failed = ~df[field].str.match(pattern, na=False)
                    invalid_mask = invalid_mask | match_failed
                    df.loc[match_failed, "_error_reason"] = df.loc[match_failed, "_error_reason"].fillna("") + f" Field {field} pattern mismatch;"
                # 枚举
                if "enum" in rules:
                    not_in_enum = ~df[field].isin(rules["enum"])
                    invalid_mask = invalid_mask | not_in_enum
                    df.loc[not_in_enum, "_error_reason"] = df.loc[not_in_enum, "_error_reason"].fillna("") + f" Field {field} not in enum;"
            elif expected_type == "number":
                # 检查是否为数值
                if not pd.api.types.is_numeric_dtype(series):
                    # 尝试转换
                    try:
                        df[field] = pd.to_numeric(series)
                    except:
                        invalid_mask = invalid_mask | True
                        df.loc[series.index, "_error_reason"] = df.loc[series.index, "_error_reason"].fillna("") + f" Field {field} not numeric;"
                # 最小值
                if "minimum" in rules:
                    below_min = df[field] < rules["minimum"]
                    invalid_mask = invalid_mask | below_min
                    df.loc[below_min, "_error_reason"] = df.loc[below_min, "_error_reason"].fillna("") + f" Field {field} below minimum;"
            elif expected_type == "timestamp":
                # 尝试转为 datetime，并检查是否可解析
                # 先存原始字符串，以备转换失败时保留
                df[f"_raw_{field}"] = df[field]  # 备份原始值
                try:
                    dt_series = pd.to_datetime(df[field], utc=True, errors="coerce")
                except:
                    dt_series = pd.Series([pd.NaT] * len(df), index=df.index)
                # 转换失败的行（原始非空但转换后为NaT）
                failed_parse = df[field].notna() & dt_series.isna()
                if failed_parse.any():
                    invalid_mask = invalid_mask | failed_parse
                    df.loc[failed_parse, "_error_reason"] = df.loc[failed_parse, "_error_reason"].fillna("") + f" Field {field} timestamp parse failed;"
                # 检查是否 <= 当前时间（可选，这里我们仅校验，不阻塞，但可记录警告）
                # 我们只处理失败的情况，未来时间我们标记为warning但不置为invalid？根据设计，未来时间应该隔离。
                # 但为了简化，我们让invalid_mask包含未来时间？可以附加条件。
                # 我们这里只做解析失败处理，其他业务规则可在cleaner中做，或者此处加上
                # 但为了分离关注点，我们把业务规则放在cleaner，这里只做基础类型校验
                df[field] = dt_series  # 转换后的UTC datetime
            # 其他类型...
        # 处理空值（required）
        for field, rules in self.field_rules.items():
            if rules.get("required", False) and field in df.columns:
                missing = df[field].isna()
                invalid_mask = invalid_mask | missing
                df.loc[missing, "_error_reason"] = df.loc[missing, "_error_reason"].fillna("") + f" Field {field} is null;"
        
        # 分割有效/无效
        invalid_df = df[invalid_mask].copy()
        valid_df = df[~invalid_mask].copy()
        # invalid_df: _error_reason 更名为 error_reason；valid_df: 丢弃内部列
        invalid_df = invalid_df.rename(columns={"_error_reason": "error_reason"})
        valid_df = valid_df.drop(columns=["_error_reason"], errors="ignore")
        return valid_df, invalid_df

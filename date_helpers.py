"""Date and column helpers adapted from MucheliSS/EPA_Dashboard. No UI side effects."""
import calendar
import re
from datetime import date, datetime
from typing import List, Optional
import pandas as pd

def _norm_str_series(s: pd.Series) -> pd.Series:
    """Trim extra whitespace and normalize to string."""
    return (
        s.astype("string")
         .str.replace(r"\s+", " ", regex=True)
         .str.strip()
    )

def pick_first_present(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None


FEEDBACK_MONTH_LABEL_COL = "__Feedback Month__"
FEEDBACK_MONTH_SORT_COL = "__Feedback Month Sort__"
ASSESSMENT_PROFILE_COL = "__Assessment Profile__"
UNKNOWN_MONTH = "Unknown month"
UNKNOWN_ASSESSMENT_DATE = "date unavailable"

MONTH_COLUMN_CANDIDATES = [
    "Feedback Month",
    "Month of Feedback",
    "Assessment Month",
    "EPA Month",
    "Rotation Month",
    "Month",
    "Feedback Date",
    "Date of Feedback",
    "Assessment Date",
    "Date of Assessment",
    "Submission Date",
    "Date Submitted",
    "Submitted Date",
    "Created Date",
    "Timestamp",
    "Date",
]

YEAR_COLUMN_CANDIDATES = [
    "Feedback Year",
    "Year of Feedback",
    "Assessment Year",
    "EPA Year",
    "Rotation Year",
    "Academic Year",
    "Year",
]

REMARKS_COLUMN_CANDIDATES = [
    "Remarks",
    "Remark",
    "Comments",
    "Comment",
    "Feedback",
    "Qualitative Feedback",
    "Narrative Feedback",
    "Additional Comments",
    "Assessor Comments",
    "Evaluator Comments",
]


def _column_tokens(name: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", str(name).lower())


def _norm_column_name(name: str) -> str:
    return " ".join(_column_tokens(name))


def pick_feedback_month_column(df: pd.DataFrame) -> Optional[str]:
    if df.empty:
        return None

    normalized = {_norm_column_name(c): c for c in df.columns}
    for candidate in MONTH_COLUMN_CANDIDATES:
        match = normalized.get(_norm_column_name(candidate))
        if match is not None:
            return match

    for c in df.columns:
        tokens = set(_column_tokens(c))
        if "month" in tokens:
            return c

    for c in df.columns:
        tokens = set(_column_tokens(c))
        if tokens.intersection({"date", "timestamp"}):
            return c

    return None


def pick_feedback_year_column(df: pd.DataFrame) -> Optional[str]:
    if df.empty:
        return None

    normalized = {_norm_column_name(c): c for c in df.columns}
    for candidate in YEAR_COLUMN_CANDIDATES:
        match = normalized.get(_norm_column_name(candidate))
        if match is not None:
            return match

    for c in df.columns:
        tokens = set(_column_tokens(c))
        if "year" in tokens:
            return c

    return None


def pick_remarks_column(df: pd.DataFrame) -> Optional[str]:
    if df.empty:
        return None

    normalized = {_norm_column_name(c): c for c in df.columns}
    for candidate in REMARKS_COLUMN_CANDIDATES:
        match = normalized.get(_norm_column_name(candidate))
        if match is not None:
            return match

    for c in df.columns:
        tokens = set(_column_tokens(c))
        is_comment = tokens.intersection({"remark", "remarks", "comment", "comments", "feedback"})
        is_metadata = tokens.intersection({"date", "month", "time", "timestamp"})
        if is_comment and not is_metadata:
            return c

    return None


def _numeric_month(value) -> Optional[int]:
    if isinstance(value, bool) or pd.isna(value):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if number.is_integer() and 1 <= int(number) <= 12:
        return int(number)
    return None


MONTH_NAME_TO_NUMBER = {
    name.lower(): idx
    for idx, name in enumerate(calendar.month_name)
    if name
}
MONTH_NAME_TO_NUMBER.update(
    {
        name.lower(): idx
        for idx, name in enumerate(calendar.month_abbr)
        if name
    }
)


def _numeric_year(value) -> Optional[int]:
    if isinstance(value, bool) or pd.isna(value):
        return None

    if isinstance(value, pd.Timestamp):
        return int(value.year)

    if isinstance(value, (datetime, date)):
        return int(value.year)

    text = str(value).strip()
    match = re.search(r"\b((?:19|20)\d{2})\b", text)
    if match:
        return int(match.group(1))

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if number.is_integer() and 1900 <= int(number) <= 2100:
        return int(number)

    if number.is_integer() and 0 <= int(number) <= 99:
        return 2000 + int(number)

    return None


def _month_number(value) -> Optional[int]:
    numeric = _numeric_month(value)
    if numeric is not None:
        return numeric

    if isinstance(value, pd.Timestamp):
        return int(value.month)

    if isinstance(value, (datetime, date)):
        return int(value.month)

    if pd.isna(value):
        return None

    tokens = _column_tokens(value)
    for token in tokens:
        month = MONTH_NAME_TO_NUMBER.get(token)
        if month is not None:
            return month

    return None


def _has_year_context(text: str) -> bool:
    if re.search(r"\b(?:19|20)\d{2}\b", text):
        return True

    tokens = _column_tokens(text)
    has_month = any(token in MONTH_NAME_TO_NUMBER for token in tokens)
    has_two_digit_year = any(re.fullmatch(r"\d{2}", token) for token in tokens)
    if has_month and has_two_digit_year:
        return True

    numeric_parts = re.findall(r"\d+", text)
    return len(numeric_parts) >= 3 and any(len(part) in (2, 4) for part in numeric_parts)


def _month_name_year_period(text: str):
    tokens = _column_tokens(text)
    month = None
    for token in tokens:
        month = MONTH_NAME_TO_NUMBER.get(token)
        if month is not None:
            break

    if month is None:
        return pd.NaT

    four_digit_years = [
        int(token)
        for token in tokens
        if re.fullmatch(r"(?:19|20)\d{2}", token)
    ]
    if four_digit_years:
        return pd.Timestamp(four_digit_years[-1], month, 1)

    two_digit_years = [
        int(token)
        for token in tokens
        if re.fullmatch(r"\d{2}", token)
    ]
    if two_digit_years:
        return pd.Timestamp(2000 + two_digit_years[-1], month, 1)

    return pd.NaT


def _month_period(value):
    if pd.isna(value):
        return pd.NaT

    if isinstance(value, pd.Timestamp):
        return pd.Timestamp(value.year, value.month, 1)

    if isinstance(value, (datetime, date)):
        return pd.Timestamp(value.year, value.month, 1)

    if _numeric_month(value) is not None:
        return pd.NaT

    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "none"}:
        return pd.NaT

    if _numeric_month(text) is not None:
        return pd.NaT

    month_name_period = _month_name_year_period(text)
    if pd.notna(month_name_period):
        return month_name_period

    if _month_number(text) is not None and not _has_year_context(text):
        return pd.NaT

    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return pd.NaT

    return pd.Timestamp(parsed.year, parsed.month, 1)


def feedback_month_period(value, year_value=None):
    period = _month_period(value)
    if pd.notna(period):
        return period

    year = _numeric_year(year_value)
    month = _month_number(value)
    if year is not None and month is not None:
        return pd.Timestamp(year, month, 1)

    return pd.NaT


def format_feedback_month(value, year_value=None) -> str:
    period = feedback_month_period(value, year_value)
    if pd.notna(period):
        return period.strftime("%b %Y")

    month_number = _month_number(value)
    if month_number is not None:
        return calendar.month_abbr[month_number]

    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "none"}:
        return UNKNOWN_MONTH

    return text


def feedback_month_sort_value(value, year_value=None):
    period = feedback_month_period(value, year_value)
    if pd.notna(period):
        return period

    return pd.NaT


def add_feedback_month_columns(
    df: pd.DataFrame,
    source_col: Optional[str],
    year_col: Optional[str] = None,
) -> pd.DataFrame:
    if source_col and source_col in df.columns:
        if year_col and year_col in df.columns:
            df[FEEDBACK_MONTH_LABEL_COL] = df.apply(
                lambda row: format_feedback_month(row[source_col], row[year_col]),
                axis=1,
            )
            df[FEEDBACK_MONTH_SORT_COL] = df.apply(
                lambda row: feedback_month_sort_value(row[source_col], row[year_col]),
                axis=1,
            )
        else:
            df[FEEDBACK_MONTH_LABEL_COL] = df[source_col].apply(format_feedback_month)
            df[FEEDBACK_MONTH_SORT_COL] = df[source_col].apply(feedback_month_sort_value)
    return df


def ordered_feedback_months(df: pd.DataFrame) -> List[str]:
    if FEEDBACK_MONTH_LABEL_COL not in df.columns:
        return []

    columns = [FEEDBACK_MONTH_LABEL_COL]
    if FEEDBACK_MONTH_SORT_COL in df.columns:
        columns.append(FEEDBACK_MONTH_SORT_COL)

    months = df[columns].drop_duplicates(subset=[FEEDBACK_MONTH_LABEL_COL]).copy()
    months["__input_order__"] = range(len(months))
    months["__unknown__"] = months[FEEDBACK_MONTH_LABEL_COL].eq(UNKNOWN_MONTH)

    if FEEDBACK_MONTH_SORT_COL in months.columns:
        months["__missing_sort__"] = months[FEEDBACK_MONTH_SORT_COL].isna()
        months = months.sort_values(
            ["__unknown__", "__missing_sort__", FEEDBACK_MONTH_SORT_COL, "__input_order__"],
            na_position="last",
        )
    else:
        months = months.sort_values(["__unknown__", "__input_order__"])

    return months[FEEDBACK_MONTH_LABEL_COL].astype(str).tolist()



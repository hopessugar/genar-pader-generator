"""
data_loader.py — Load, validate, parse, and prepare the ICSR dataset.

Why this exists: Isolates all data ingestion, validation, and parsing concerns
so analysis functions receive a clean, predictable DataFrame. Downstream code
never deals with raw file I/O or schema issues.
"""

import pandas as pd
from dataclasses import dataclass


# Required columns — the system raises SchemaError if any are missing (DATA-02).
REQUIRED_COLUMNS = [
    "safetyreportid", "serious", "fulfillexpeditecriteria", "receivedate",
    "patient_patientonsetage", "patient_patientonsetageunit",
    "patient_patientsex", "occurcountry", "primarysource_reportercountry",
    "patient_reaction_reactionmeddrapt", "patient_reaction_reactionoutcome",
    "seriousnessdeath", "seriousnesslifethreatening",
    "seriousnesshospitalization", "seriousnessdisabling",
    "seriousnesscongenitalanomali", "seriousnessother",
    "primarysource_qualification", "reporttype",
]

# Age unit conversion allowlist (DATA-06).
# Only these units are valid; anything else -> "Unknown".
AGE_UNIT_CONVERSIONS = {
    "year": 1.0,
    "month": 1.0 / 12.0,
    "week": 1.0 / 52.0,
    "day": 1.0 / 365.25,
}

# Age group buckets (DATA-06) — in years.
AGE_GROUPS = [
    ("Neonate", 0, 1),
    ("Infant", 1, 2),
    ("Child", 2, 12),
    ("Adolescent", 12, 18),
    ("Adult", 18, 65),
    ("Elderly", 65, float("inf")),
]


class SchemaError(Exception):
    """Raised when required columns are missing from the dataset."""
    pass


@dataclass
class LoadedData:
    """Container for the validated, parsed dataset and derived metadata."""
    df: pd.DataFrame                    # Full DataFrame, validated and enriched
    cases: pd.DataFrame                 # Deduplicated by safetyreportid
    flagged_rows: pd.DataFrame          # Rows with reaction/outcome count mismatch
    flagged_row_indices: list[int]       # Index positions of flagged rows
    reporting_period: tuple[str, str]    # (start_date, end_date) as "YYYY-MM-DD"
    row_count: int                      # Total rows (1,068)
    case_count: int                     # Unique cases (1,024)
    flagged_count: int                  # Mismatched rows (~6)


def load_dataset(filepath: str) -> LoadedData:
    """
    Load, validate, parse, and prepare the ICSR dataset.

    Steps:
      1. Load Excel file
      2. Validate schema (DATA-02)
      3. Derive reporting period (DATA-03)
      4. Apply country fallback (DATA-05)
      5. Convert ages and bucket into age groups (DATA-06)
      6. Flag reaction/outcome mismatches (DATA-04)
      7. Normalize sex nulls to "Unknown"
      8. Deduplicate to case-level

    Returns LoadedData with all computed fields.
    """
    # Step 1: Load
    df = pd.read_excel(filepath)

    # Step 2: Schema validation (DATA-02)
    _validate_schema(df)

    # Step 3: Derive reporting period (DATA-03)
    reporting_period = _derive_reporting_period(df)

    # Step 4: Country fallback (DATA-05)
    # occurcountry is primary (where the event occurred, more clinically relevant).
    # primarysource_reportercountry fills the 7 nulls.
    df["country"] = df["occurcountry"].fillna(df["primarysource_reportercountry"])

    # Step 5: Age conversion and bucketing (DATA-06)
    df["age_years"] = df.apply(_convert_age_to_years, axis=1)
    df["age_group"] = df["age_years"].apply(_assign_age_group)

    # Step 6: Reaction/outcome mismatch flagging (DATA-04)
    flagged_mask = df.apply(_check_reaction_outcome_mismatch, axis=1)
    flagged_rows = df[flagged_mask].copy()
    flagged_row_indices = flagged_rows.index.tolist()

    # Step 7: Sex normalization — BEFORE dedup so cases inherits clean values
    df["patient_patientsex"] = df["patient_patientsex"].fillna("Unknown")

    # Step 8: Case dedup
    cases = df.drop_duplicates(subset="safetyreportid", keep="first").copy()

    return LoadedData(
        df=df,
        cases=cases,
        flagged_rows=flagged_rows,
        flagged_row_indices=flagged_row_indices,
        reporting_period=reporting_period,
        row_count=len(df),
        case_count=len(cases),
        flagged_count=len(flagged_rows),
    )


def _validate_schema(df: pd.DataFrame) -> None:
    """Check that all required columns exist (DATA-02)."""
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise SchemaError(
            f"Dataset is missing {len(missing)} required column(s): {missing}"
        )


def _derive_reporting_period(df: pd.DataFrame) -> tuple[str, str]:
    """
    Derive reporting period from receivedate min/max (DATA-03).
    receivedate is in YYYYMMDD integer format.
    """
    dates = pd.to_datetime(df["receivedate"].astype(str), format="%Y%m%d")
    start = dates.min().strftime("%Y-%m-%d")
    end = dates.max().strftime("%Y-%m-%d")
    return (start, end)


def _convert_age_to_years(row: pd.Series) -> float | None:
    """
    Convert age to years using the unit allowlist (DATA-06).
    Returns NaN if age is null, unit is missing, or unit is not in allowlist.
    """
    age = row["patient_patientonsetage"]
    unit = row["patient_patientonsetageunit"]

    if pd.isna(age):
        return float("nan")

    if pd.isna(unit) or str(unit).strip().lower() not in AGE_UNIT_CONVERSIONS:
        # Invalid or missing unit (includes "800" and other non-unit values)
        return float("nan")

    conversion = AGE_UNIT_CONVERSIONS[str(unit).strip().lower()]
    return float(age) * conversion


def _assign_age_group(age_years: float) -> str:
    """Assign age group from age in years, or 'Unknown' if NaN."""
    if pd.isna(age_years):
        return "Unknown"

    for group_name, lower, upper in AGE_GROUPS:
        if lower <= age_years < upper:
            return group_name

    return "Unknown"


def _check_reaction_outcome_mismatch(row: pd.Series) -> bool:
    """
    Check if a row has mismatched reaction/outcome comma-split counts (DATA-04).
    Returns True if counts don't match (i.e., row should be flagged).
    """
    reactions_str = str(row["patient_reaction_reactionmeddrapt"])
    outcomes_str = str(row["patient_reaction_reactionoutcome"])

    reaction_count = len(reactions_str.split(","))
    outcome_count = len(outcomes_str.split(","))

    return reaction_count != outcome_count

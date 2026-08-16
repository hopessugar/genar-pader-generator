"""
analysis.py — Deterministic analysis layer. Pure Python/pandas, zero LLM.

Why this exists: Contains all deterministic computation in pure Python, making
every number independently testable without LLM involvement. Each function
takes a DataFrame, returns a dict.

Convention:
  - Case-level functions take `cases` (deduplicated by safetyreportid).
  - Reaction-level functions take `df` (full DataFrame) + `flagged_indices`
    (rows to exclude due to reaction/outcome mismatch per DATA-04).
"""

import pandas as pd
from data_loader import LoadedData


def run_all_analyses(data: LoadedData, top_n: int = 20) -> dict:
    """
    Run all 15 analyses. Returns results keyed by analysis ID.
    This is the single entry point the pipeline calls.
    """
    return {
        "total_cases": total_cases(data.cases),
        "serious_breakdown": serious_breakdown(data.cases),
        "age_group_breakdown": age_group_breakdown(data.cases),
        "sex_breakdown": sex_breakdown(data.cases),
        "country_breakdown": country_breakdown(data.cases),
        "top_reactions": top_reactions(data.df, data.flagged_row_indices, top_n),
        "top_serious_reactions": top_serious_reactions(data.df, data.flagged_row_indices, top_n),
        "outcome_distribution": outcome_distribution(data.df, data.flagged_row_indices),
        "monthly_case_volume": monthly_case_volume(data.cases),
        "expedited_breakdown": expedited_breakdown(data.cases),
        "seriousness_criteria": seriousness_criteria(data.cases),
        "reporter_breakdown": reporter_breakdown(data.cases),
        "reactions_by_age": reactions_by_age(data.df, data.flagged_row_indices, top_n=5),
        "reactions_by_sex": reactions_by_sex(data.df, data.flagged_row_indices, top_n=5),
        "case_listing": case_listing(data.cases),
        # Metadata for evidence packets
        "_meta": {
            "row_count": data.row_count,
            "case_count": data.case_count,
            "flagged_count": data.flagged_count,
            "reporting_period": data.reporting_period,
        },
    }


# ---------------------------------------------------------------------------
# Case-level analyses (input: cases DataFrame, deduplicated by safetyreportid)
# ---------------------------------------------------------------------------

def total_cases(cases: pd.DataFrame) -> dict:
    """ANAL-01: Total case count (case-level)."""
    return {
        "analysis_id": "total_cases",
        "level": "case",
        "data": {
            "total": len(cases),
        },
    }


def serious_breakdown(cases: pd.DataFrame) -> dict:
    """ANAL-02: Serious vs. non-serious case breakdown (case-level)."""
    serious = (cases["serious"] == "serious").sum()
    non_serious = (cases["serious"] == "not serious").sum()
    total = len(cases)
    return {
        "analysis_id": "serious_breakdown",
        "level": "case",
        "data": {
            "serious": int(serious),
            "non_serious": int(non_serious),
            "total": int(total),
            "serious_pct": round(serious / total * 100, 1) if total > 0 else 0,
            "non_serious_pct": round(non_serious / total * 100, 1) if total > 0 else 0,
        },
    }


def age_group_breakdown(cases: pd.DataFrame) -> dict:
    """ANAL-03: Case breakdown by age group (case-level)."""
    counts = cases["age_group"].value_counts().to_dict()
    total = len(cases)
    breakdown = []
    for group, count in sorted(counts.items(), key=lambda x: -x[1]):
        breakdown.append({
            "age_group": group,
            "count": int(count),
            "pct": round(count / total * 100, 1) if total > 0 else 0,
        })
    return {
        "analysis_id": "age_group_breakdown",
        "level": "case",
        "data": {"total": int(total), "groups": breakdown},
    }


def sex_breakdown(cases: pd.DataFrame) -> dict:
    """ANAL-04: Case breakdown by sex (case-level)."""
    counts = cases["patient_patientsex"].value_counts().to_dict()
    total = len(cases)
    breakdown = []
    for sex, count in sorted(counts.items(), key=lambda x: -x[1]):
        breakdown.append({
            "sex": sex,
            "count": int(count),
            "pct": round(count / total * 100, 1) if total > 0 else 0,
        })
    return {
        "analysis_id": "sex_breakdown",
        "level": "case",
        "data": {"total": int(total), "groups": breakdown},
    }


def country_breakdown(cases: pd.DataFrame) -> dict:
    """ANAL-05: Case breakdown by country (case-level, using occurcountry with fallback)."""
    counts = cases["country"].value_counts().to_dict()
    total = len(cases)
    breakdown = []
    for country, count in sorted(counts.items(), key=lambda x: -x[1]):
        breakdown.append({
            "country": str(country),
            "count": int(count),
            "pct": round(count / total * 100, 1) if total > 0 else 0,
        })
    return {
        "analysis_id": "country_breakdown",
        "level": "case",
        "data": {"total": int(total), "countries": breakdown},
    }


def monthly_case_volume(cases: pd.DataFrame) -> dict:
    """ANAL-09: Monthly case volume over time (case-level)."""
    dates = pd.to_datetime(cases["receivedate"].astype(str), format="%Y%m%d")
    monthly = dates.dt.to_period("M").value_counts().sort_index()
    months = []
    for period, count in monthly.items():
        months.append({
            "month": str(period),
            "count": int(count),
        })
    return {
        "analysis_id": "monthly_case_volume",
        "level": "case",
        "data": {"months": months, "total_months": len(months)},
    }


def expedited_breakdown(cases: pd.DataFrame) -> dict:
    """ANAL-10: 15-day alert / expedited case breakdown (case-level)."""
    expedited = (cases["fulfillexpeditecriteria"] == "yes").sum()
    non_expedited = (cases["fulfillexpeditecriteria"] == "no").sum()
    total = len(cases)

    # Sub-breakdown of expedited cases by seriousness criteria
    expedited_cases = cases[cases["fulfillexpeditecriteria"] == "yes"]
    criteria_counts = {}
    for col in ["seriousnessdeath", "seriousnesslifethreatening",
                "seriousnesshospitalization", "seriousnessdisabling",
                "seriousnesscongenitalanomali", "seriousnessother"]:
        criteria_counts[col] = int((expedited_cases[col] == "yes").sum())

    return {
        "analysis_id": "expedited_breakdown",
        "level": "case",
        "data": {
            "expedited": int(expedited),
            "non_expedited": int(non_expedited),
            "total": int(total),
            "expedited_pct": round(expedited / total * 100, 1) if total > 0 else 0,
            "seriousness_criteria": criteria_counts,
        },
    }


def seriousness_criteria(cases: pd.DataFrame) -> dict:
    """ANAL-11: Seriousness criteria breakdown (case-level, flags not mutually exclusive)."""
    total = len(cases)
    criteria = {}
    labels = {
        "seriousnessdeath": "Death",
        "seriousnesslifethreatening": "Life-threatening",
        "seriousnesshospitalization": "Hospitalization",
        "seriousnessdisabling": "Disabling",
        "seriousnesscongenitalanomali": "Congenital anomaly",
        "seriousnessother": "Other medically important",
    }
    for col, label in labels.items():
        count = int((cases[col] == "yes").sum())
        criteria[col] = {
            "label": label,
            "count": count,
            "pct": round(count / total * 100, 1) if total > 0 else 0,
        }
    return {
        "analysis_id": "seriousness_criteria",
        "level": "case",
        "data": {"total": int(total), "criteria": criteria},
    }


def reporter_breakdown(cases: pd.DataFrame) -> dict:
    """ANAL-12: Reporter type breakdown (case-level)."""
    counts = cases["primarysource_qualification"].value_counts().to_dict()
    total = len(cases)
    breakdown = []
    for reporter, count in sorted(counts.items(), key=lambda x: -x[1]):
        breakdown.append({
            "reporter_type": str(reporter),
            "count": int(count),
            "pct": round(count / total * 100, 1) if total > 0 else 0,
        })
    return {
        "analysis_id": "reporter_breakdown",
        "level": "case",
        "data": {"total": int(total), "reporters": breakdown},
    }


def case_listing(cases: pd.DataFrame) -> dict:
    """ANAL-15: Structured case listing for all cases."""
    listing = []
    for _, row in cases.iterrows():
        listing.append({
            "safetyreportid": str(row["safetyreportid"]),
            "reactions": str(row["patient_reaction_reactionmeddrapt"]),
            "seriousness": str(row["serious"]),
            "receivedate": str(row["receivedate"]),
            "country": str(row["country"]),
            "outcomes": str(row["patient_reaction_reactionoutcome"]),
        })
    return {
        "analysis_id": "case_listing",
        "level": "case",
        "data": {"total": len(listing), "cases": listing},
    }


# ---------------------------------------------------------------------------
# Reaction-level analyses (input: full df, excluding flagged rows)
# ---------------------------------------------------------------------------

def _explode_reactions(df: pd.DataFrame, flagged_indices: list[int]) -> pd.DataFrame:
    """
    Exclude flagged rows (DATA-04), split reactions by comma, explode.
    Returns a DataFrame with one reaction per row plus all original columns.
    """
    clean = df.drop(index=flagged_indices, errors="ignore").copy()
    clean = clean.assign(
        reaction=clean["patient_reaction_reactionmeddrapt"].str.split(",")
    ).explode("reaction")
    clean["reaction"] = clean["reaction"].str.strip()
    return clean


def _explode_outcomes(df: pd.DataFrame, flagged_indices: list[int]) -> pd.DataFrame:
    """
    Exclude flagged rows, split outcomes by comma, explode.
    Returns a DataFrame with one outcome per row.
    """
    clean = df.drop(index=flagged_indices, errors="ignore").copy()
    clean = clean.assign(
        outcome=clean["patient_reaction_reactionoutcome"].str.split(",")
    ).explode("outcome")
    clean["outcome"] = clean["outcome"].str.strip()
    return clean


def top_reactions(df: pd.DataFrame, flagged_indices: list[int], n: int = 20) -> dict:
    """ANAL-06: Most common reactions overall (reaction-level)."""
    exploded = _explode_reactions(df, flagged_indices)
    counts = exploded["reaction"].value_counts().head(n)
    reactions = []
    for reaction, count in counts.items():
        reactions.append({"reaction": str(reaction), "count": int(count)})
    return {
        "analysis_id": "top_reactions",
        "level": "reaction",
        "data": {
            "total_reactions_counted": len(exploded),
            "flagged_rows_excluded": len(flagged_indices),
            "top_n": n,
            "reactions": reactions,
        },
    }


def top_serious_reactions(df: pd.DataFrame, flagged_indices: list[int], n: int = 20) -> dict:
    """ANAL-07: Most common serious reactions (reaction-level)."""
    serious_df = df[df["serious"] == "serious"]
    exploded = _explode_reactions(serious_df, flagged_indices)
    counts = exploded["reaction"].value_counts().head(n)
    reactions = []
    for reaction, count in counts.items():
        reactions.append({"reaction": str(reaction), "count": int(count)})
    return {
        "analysis_id": "top_serious_reactions",
        "level": "reaction",
        "data": {
            "total_serious_reactions_counted": len(exploded),
            "flagged_rows_excluded": len(flagged_indices),
            "top_n": n,
            "reactions": reactions,
        },
    }


def outcome_distribution(df: pd.DataFrame, flagged_indices: list[int]) -> dict:
    """ANAL-08: Outcome distribution (reaction-level)."""
    exploded = _explode_outcomes(df, flagged_indices)
    counts = exploded["outcome"].value_counts()
    total = len(exploded)
    outcomes = []
    for outcome, count in counts.items():
        outcomes.append({
            "outcome": str(outcome),
            "count": int(count),
            "pct": round(count / total * 100, 1) if total > 0 else 0,
        })
    return {
        "analysis_id": "outcome_distribution",
        "level": "reaction",
        "data": {
            "total_outcomes_counted": int(total),
            "flagged_rows_excluded": len(flagged_indices),
            "outcomes": outcomes,
        },
    }


def reactions_by_age(df: pd.DataFrame, flagged_indices: list[int], top_n: int = 5) -> dict:
    """ANAL-13: Top reactions within each age group (cross-tabulation)."""
    exploded = _explode_reactions(df, flagged_indices)
    result = {}
    for group in exploded["age_group"].unique():
        group_data = exploded[exploded["age_group"] == group]
        top = group_data["reaction"].value_counts().head(top_n)
        result[str(group)] = [
            {"reaction": str(r), "count": int(c)} for r, c in top.items()
        ]
    return {
        "analysis_id": "reactions_by_age",
        "level": "reaction",
        "data": {
            "flagged_rows_excluded": len(flagged_indices),
            "top_n_per_group": top_n,
            "groups": result,
        },
    }


def reactions_by_sex(df: pd.DataFrame, flagged_indices: list[int], top_n: int = 5) -> dict:
    """ANAL-14: Top reactions within each sex category (cross-tabulation)."""
    exploded = _explode_reactions(df, flagged_indices)
    result = {}
    for sex in exploded["patient_patientsex"].unique():
        sex_data = exploded[exploded["patient_patientsex"] == sex]
        top = sex_data["reaction"].value_counts().head(top_n)
        result[str(sex)] = [
            {"reaction": str(r), "count": int(c)} for r, c in top.items()
        ]
    return {
        "analysis_id": "reactions_by_sex",
        "level": "reaction",
        "data": {
            "flagged_rows_excluded": len(flagged_indices),
            "top_n_per_group": top_n,
            "groups": result,
        },
    }

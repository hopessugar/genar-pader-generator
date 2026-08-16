"""
config.py — Report type definitions and section-to-analysis mapping.

Why this exists: Makes the pipeline report-type-agnostic. PADER is just the
first config. Future report types (PSUR, DSUR) would be new configs, not new
code paths.
"""

from dataclasses import dataclass, field


@dataclass
class SectionConfig:
    """Configuration for a single report section."""
    section_id: str              # e.g., "narrative_summary"
    section_name: str            # e.g., "Narrative Summary and Analysis"
    section_number: int          # e.g., 2
    required_analyses: list[str] # e.g., ["total_cases", "serious_breakdown", ...]
    prompt_template: str         # e.g., "prompts/section_narrative_summary.txt"
    uses_llm: bool = True        # False for sections like history_of_actions


@dataclass
class ReportConfig:
    """Configuration for a complete report type."""
    report_type: str             # "PADER"
    product_name: str            # "Bisoprolol"
    sections: list[SectionConfig] = field(default_factory=list)
    top_n_reactions: int = 20
    dataset_path: str = ""


# ---------------------------------------------------------------------------
# PADER Configuration — the first (and currently only) report type.
# Adding PSUR/DSUR later means adding a new ReportConfig here, not new code.
# ---------------------------------------------------------------------------

PADER_SECTIONS = [
    SectionConfig(
        section_id="reporting_period",
        section_name="Reporting Period",
        section_number=1,
        required_analyses=[],  # Uses reporting_period from LoadedData directly
        prompt_template="prompts/section_reporting_period.txt",
        uses_llm=True,
    ),
    SectionConfig(
        section_id="narrative_summary",
        section_name="Narrative Summary and Analysis",
        section_number=2,
        required_analyses=[
            "total_cases", "serious_breakdown",
            "top_reactions", "top_serious_reactions",
            "outcome_distribution", "monthly_case_volume",
        ],
        prompt_template="prompts/section_narrative_summary.txt",
        uses_llm=True,
    ),
    SectionConfig(
        section_id="summary_analysis",
        section_name="Summary Analysis of Cases",
        section_number=3,
        required_analyses=[
            "total_cases", "serious_breakdown",
            "age_group_breakdown", "sex_breakdown",
            "country_breakdown", "outcome_distribution",
            "seriousness_criteria", "reporter_breakdown",
        ],
        prompt_template="prompts/section_summary_analysis.txt",
        uses_llm=True,
    ),
    SectionConfig(
        section_id="reaction_analysis",
        section_name="Reaction / Adverse Event Analysis",
        section_number=4,
        required_analyses=[
            "top_reactions", "top_serious_reactions",
            "reactions_by_age", "reactions_by_sex",
            "monthly_case_volume",
        ],
        prompt_template="prompts/section_reaction_analysis.txt",
        uses_llm=True,
    ),
    SectionConfig(
        section_id="serious_cases",
        section_name="Serious Cases / 15-Day Alerts",
        section_number=5,
        required_analyses=[
            "serious_breakdown", "expedited_breakdown",
            "seriousness_criteria",
        ],
        prompt_template="prompts/section_serious_cases.txt",
        uses_llm=True,
    ),
    SectionConfig(
        section_id="trends",
        section_name="Trends and Important Observations",
        section_number=6,
        required_analyses=[
            "monthly_case_volume", "country_breakdown",
            "top_reactions",
        ],
        prompt_template="prompts/section_trends.txt",
        uses_llm=True,
    ),
    SectionConfig(
        section_id="history_of_actions",
        section_name="History of Actions",
        section_number=7,
        required_analyses=[],
        prompt_template="prompts/section_history_of_actions.txt",
        uses_llm=False,  # Static text, no LLM needed
    ),
    SectionConfig(
        section_id="case_listing",
        section_name="Case Index / Listing",
        section_number=8,
        required_analyses=["case_listing"],
        prompt_template="prompts/section_case_listing.txt",
        uses_llm=False,  # Structured table, no LLM needed
    ),
]

PADER_CONFIG = ReportConfig(
    report_type="PADER",
    product_name="Bisoprolol",
    sections=PADER_SECTIONS,
    top_n_reactions=20,
    dataset_path="",  # Set at runtime via CLI arg
)

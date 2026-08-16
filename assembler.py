"""
assembler.py — Stitch generated sections into a complete Markdown report.

Why this exists: Handles document-level formatting concerns (headings, TOC,
CSV output) that don't belong in generation or analysis code.
"""

import csv
from pathlib import Path
from datetime import datetime
from config import ReportConfig


def assemble_report(
    sections: dict[str, str],
    report_config: ReportConfig,
    reporting_period: tuple[str, str],
    output_path: str = "output/report.md",
) -> str:
    """
    Assemble the final report from individually generated sections.
    Returns full Markdown text and writes to file.
    """
    lines = []

    # Title
    lines.append(f"# Periodic Adverse Drug Experience Report (PADER)")
    lines.append(f"## {report_config.product_name}")
    lines.append("")
    lines.append(f"**Period covered:** {reporting_period[0]} to {reporting_period[1]}")
    lines.append(f"**Report type:** {report_config.report_type}")
    lines.append(f"**Date of this report:** {datetime.now().strftime('%Y-%m-%d')}")
    lines.append(f"**Regulatory basis:** 21 CFR 314.80")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Table of Contents
    lines.append("## Table of Contents\n")
    for section_config in report_config.sections:
        lines.append(
            f"{section_config.section_number}. "
            f"[{section_config.section_name}]"
            f"(#{section_config.section_id})"
        )
    lines.append("")
    lines.append("---")
    lines.append("")

    # Sections
    for section_config in report_config.sections:
        sid = section_config.section_id
        lines.append(
            f"## {section_config.section_number}. {section_config.section_name} "
            f"{{#{sid}}}"
        )
        lines.append("")

        section_text = sections.get(sid, "*Section not generated.*")
        lines.append(section_text)
        lines.append("")
        lines.append("---")
        lines.append("")

    # Footer
    lines.append("## Data Limitations\n")
    lines.append("The following limitations apply to this report:\n")
    lines.append("- **SOC-level analysis**: Unavailable. The dataset contains only "
                 "MedDRA Preferred Terms (PTs), not System Organ Class (SOC) mapping. "
                 "All reaction analyses are reported at the PT level.")
    lines.append("- **Expectedness**: Out of scope. No product label/CCDS was supplied, "
                 "so labelled/unlabelled classification could not be performed.")
    lines.append("- **History of actions**: No action data was supplied with this dataset.")
    lines.append("- **Cumulative counts**: Not available. All counts represent the "
                 "current reporting interval only (no prior-period data).")
    lines.append("- **Flagged rows**: Approximately 6 of 1,068 rows (0.6%) were "
                 "excluded from reaction-level analyses due to reaction/outcome "
                 "count mismatches caused by MedDRA PTs containing embedded commas "
                 "(e.g., \"Hallucination, visual\"). These rows are fully included "
                 "in all case-level analyses.")
    lines.append("")

    report_text = "\n".join(lines)

    # Write to file
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report_text, encoding="utf-8")

    return report_text


def write_case_listing_csv(
    case_listing_data: dict,
    output_path: str = "output/case_listing.csv",
) -> None:
    """Write full case listing to CSV (ANAL-15)."""
    cases = case_listing_data.get("cases", [])
    if not cases:
        return

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["safetyreportid", "reactions", "seriousness", "receivedate",
                  "country", "outcomes"]

    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cases)


def build_case_listing_section(
    case_listing_data: dict,
    preview_count: int = 15,
) -> str:
    """
    Build the case listing section: inline preview table + link to CSV.
    """
    cases = case_listing_data.get("cases", [])
    total = case_listing_data.get("total", len(cases))

    lines = []

    # Intro text from template
    lines.append(
        "This section contains the case index for the reporting period. "
        "An inline preview is shown below; the full listing of all cases "
        "is available in the accompanying `case_listing.csv` file.\n"
    )
    lines.append(
        "A reviewer can use the case listing to trace any aggregate figure "
        "in this report back to the individual cases that contributed to it.\n"
    )

    # Inline preview table
    preview = cases[:preview_count]
    lines.append(f"**Preview** (first {len(preview)} of {total} cases):\n")
    lines.append("| Case ID | Reaction(s) | Seriousness | Receive Date | Country | Outcome(s) |")
    lines.append("|---------|-------------|-------------|--------------|---------|------------|")

    for case in preview:
        # Truncate long reaction strings for readability
        reactions = case.get("reactions", "")
        if len(reactions) > 60:
            reactions = reactions[:57] + "..."
        outcomes = case.get("outcomes", "")
        if len(outcomes) > 40:
            outcomes = outcomes[:37] + "..."

        lines.append(
            f"| {case.get('safetyreportid', '')} "
            f"| {reactions} "
            f"| {case.get('seriousness', '')} "
            f"| {case.get('receivedate', '')} "
            f"| {case.get('country', '')} "
            f"| {outcomes} |"
        )

    lines.append("")
    lines.append(f"**Full listing**: See [case_listing.csv](case_listing.csv) "
                 f"({total} cases total)")

    return "\n".join(lines)

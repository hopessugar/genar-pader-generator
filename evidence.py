"""
evidence.py — Per-section evidence packet builder.

Why this exists: Decouples "what data exists" from "what data this section needs,"
enforcing the principle that the LLM never sees more than its section requires.
"""

import json
from config import ReportConfig, SectionConfig


def build_evidence_packets(
    analyses: dict,
    report_config: ReportConfig,
    reporting_period: tuple[str, str],
) -> dict[str, dict]:
    """
    Build evidence packets for all sections defined in the report config.
    Returns {section_id: evidence_packet_dict}.
    """
    packets = {}
    for section in report_config.sections:
        packets[section.section_id] = build_section_packet(
            section, analyses, reporting_period, report_config.product_name
        )
    return packets


def build_section_packet(
    section_config: SectionConfig,
    analyses: dict,
    reporting_period: tuple[str, str],
    product_name: str,
) -> dict:
    """
    Build one section's evidence packet from its required analyses.
    Only includes the analyses listed in section_config.required_analyses.
    """
    meta = analyses.get("_meta", {})

    packet = {
        "section_id": section_config.section_id,
        "section_name": section_config.section_name,
        "reporting_period_start": reporting_period[0],
        "reporting_period_end": reporting_period[1],
        "product_name": product_name,
    }

    # Pull only the required analyses into the packet
    for analysis_id in section_config.required_analyses:
        if analysis_id in analyses:
            # Include just the data portion, not the wrapper metadata
            packet[analysis_id] = analyses[analysis_id]["data"]
        else:
            packet[analysis_id] = {"error": f"Analysis '{analysis_id}' not found"}

    # Add data quality notes relevant to all sections
    packet["data_notes"] = [
        f"Total rows in dataset: {meta.get('row_count', 'N/A')}, "
        f"unique cases: {meta.get('case_count', 'N/A')}",
        f"Flagged rows excluded from reaction-level analyses: "
        f"{meta.get('flagged_count', 'N/A')} (reaction/outcome count mismatch)",
        "SOC-level analysis unavailable (no SOC field in dataset; "
        "reactions reported at MedDRA Preferred Term level only)",
        "Expectedness assessment out of scope (no product label/CCDS supplied)",
    ]

    return packet


def format_packet_for_prompt(packet: dict) -> str:
    """Serialize evidence packet as formatted JSON for injection into prompts."""
    return json.dumps(packet, indent=2, ensure_ascii=False)

"""
review.py — Human review gate (review.json batch mode).

Why this exists: Enables human oversight of generated content against source
evidence before finalization — a regulatory necessity in spirit.
"""

import json
from pathlib import Path
from dataclasses import dataclass


@dataclass
class ReviewResult:
    """Result of human review for one section."""
    section_id: str
    status: str          # "approved" | "flagged" | "pending"
    comment: str | None  # Optional reviewer comment


def write_review_file(
    sections: dict[str, str],
    evidence_packets: dict[str, dict],
    output_path: str = "output/review.json",
) -> None:
    """
    Write review.json with generated text + evidence for each section.
    Human edits this file to approve or flag sections.
    """
    review_data = {"sections": {}}

    for section_id, text in sections.items():
        review_data["sections"][section_id] = {
            "generated_text": text,
            "evidence_packet": evidence_packets.get(section_id, {}),
            "status": "pending",
            "comment": None,
        }

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(review_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def read_review_file(
    path: str = "output/review.json",
) -> dict[str, ReviewResult]:
    """
    Read human-edited review.json. Returns per-section ReviewResult.
    If file doesn't exist, returns empty dict.
    """
    review_path = Path(path)
    if not review_path.exists():
        return {}

    data = json.loads(review_path.read_text(encoding="utf-8"))
    results = {}

    for section_id, section_data in data.get("sections", {}).items():
        results[section_id] = ReviewResult(
            section_id=section_id,
            status=section_data.get("status", "pending"),
            comment=section_data.get("comment"),
        )

    return results


def get_flagged_sections(
    review_results: dict[str, ReviewResult],
) -> list[str]:
    """Return list of section_ids that were flagged for regeneration."""
    return [
        sid for sid, result in review_results.items()
        if result.status == "flagged"
    ]


def auto_approve_all(
    sections: dict[str, str],
) -> dict[str, ReviewResult]:
    """Auto-approve all sections (used with --auto-approve flag)."""
    return {
        sid: ReviewResult(section_id=sid, status="approved", comment=None)
        for sid in sections
    }

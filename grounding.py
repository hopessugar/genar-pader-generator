"""
grounding.py — Automated grounding check.

Why this exists: Provides automated verification that generated text only
contains numbers present in the evidence packet — the primary quality gate.
This is the closest thing to real evaluation of "is this report actually
correct?" that's achievable in V0.
"""

import re
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict


@dataclass
class GroundingResult:
    """Grounding check result for one section."""
    section_id: str
    passed: bool
    numbers_in_text: list[str] = field(default_factory=list)
    grounded: list[str] = field(default_factory=list)
    ungrounded: list[str] = field(default_factory=list)
    evidence_numbers: list[str] = field(default_factory=list)


@dataclass
class GroundingReport:
    """Aggregate grounding check report."""
    results: list[GroundingResult] = field(default_factory=list)
    overall_pass: bool = True
    summary: str = ""


def check_grounding(
    sections: dict[str, str],
    evidence_packets: dict[str, dict],
) -> GroundingReport:
    """
    Check all sections for grounding. Returns pass/fail per section.

    For each section:
    1. Extract all numbers from the generated text
    2. Extract all numbers from the evidence packet (typed values AND strings)
    3. Any number in text that isn't in the packet = ungrounded
    """
    results = []

    for section_id, text in sections.items():
        packet = evidence_packets.get(section_id, {})

        text_numbers = _extract_numbers(text)
        packet_numbers = _extract_numbers_from_packet(packet)

        grounded = text_numbers & packet_numbers
        ungrounded = text_numbers - packet_numbers

        result = GroundingResult(
            section_id=section_id,
            passed=len(ungrounded) == 0,
            numbers_in_text=sorted([str(n) for n in text_numbers]),
            grounded=sorted([str(n) for n in grounded]),
            ungrounded=sorted([str(n) for n in ungrounded]),
            evidence_numbers=sorted([str(n) for n in packet_numbers]),
        )
        results.append(result)

    overall_pass = all(r.passed for r in results)
    passed_count = sum(1 for r in results if r.passed)
    total_count = len(results)

    summary = (
        f"Grounding check: {passed_count}/{total_count} sections passed. "
        + ("ALL SECTIONS GROUNDED." if overall_pass else
           f"UNGROUNDED NUMBERS FOUND in {total_count - passed_count} section(s).")
    )

    return GroundingReport(
        results=results,
        overall_pass=overall_pass,
        summary=summary,
    )


def write_grounding_report(
    report: GroundingReport,
    output_path: str = "output/grounding_report.json",
) -> None:
    """Write grounding report to JSON file."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "overall_pass": report.overall_pass,
        "summary": report.summary,
        "results": [asdict(r) for r in report.results],
    }

    output.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Number extraction
# ---------------------------------------------------------------------------

# Regex to match numbers in text: integers, decimals, comma-formatted, percentages
_NUMBER_PATTERN = re.compile(r'[\d,]+\.?\d*')


def _extract_numbers(text: str) -> set[float]:
    """
    Extract all numbers from text, normalize to float set.
    Handles: "1,024" → 1024.0, "99.9%" → 99.9, "1,023" → 1023.0
    """
    raw = _NUMBER_PATTERN.findall(text)
    numbers = set()
    for n in raw:
        try:
            cleaned = n.replace(",", "").rstrip(".")
            if cleaned:
                numbers.add(float(cleaned))
        except ValueError:
            continue
    return numbers


def _extract_numbers_from_packet(packet: dict) -> set[float]:
    """
    Recursively extract all numeric values from evidence packet.

    Walks the dict/list structure:
    - Collects all int/float typed values directly
    - For string values, runs the SAME _extract_numbers() regex to pull
      numbers from strings like "2024-12-27" → {2024, 12, 27}

    This prevents false-positive ungrounded flags on date components
    and any other numbers embedded in string fields.
    """
    numbers = set()
    _walk_packet(packet, numbers)
    return numbers


def _walk_packet(obj, numbers: set[float]) -> None:
    """Recursively walk a nested dict/list and extract all numbers."""
    if isinstance(obj, (int, float)):
        if not isinstance(obj, bool):  # bool is subclass of int in Python
            numbers.add(float(obj))
    elif isinstance(obj, str):
        # Extract numbers from string values too (handles dates, IDs, etc.)
        numbers.update(_extract_numbers(obj))
    elif isinstance(obj, dict):
        for value in obj.values():
            _walk_packet(value, numbers)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            _walk_packet(item, numbers)

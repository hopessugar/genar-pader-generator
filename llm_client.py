"""
llm_client.py — LLM API wrapper with provider abstraction and fallback.

Why this exists: Wraps the LLM API call with provider abstraction and fallback
logic, so the rest of the pipeline is LLM-provider-agnostic.
"""

import os
import json
from pathlib import Path
from config import ReportConfig, SectionConfig
from evidence import format_packet_for_prompt


# Base directory for prompt files
PROMPTS_DIR = Path(__file__).parent / "prompts"


def generate_section(
    section_id: str,
    evidence_packet: dict,
    section_config: SectionConfig,
    use_llm: bool = True,
) -> str:
    """
    Generate prose for one report section.

    If uses_llm is False on the section config (e.g., history_of_actions,
    case_listing), returns the static template text directly.
    If use_llm is False globally or API is unavailable, falls back to
    formatted evidence packet rendering.
    """
    # Sections that don't use LLM at all — return static template
    if not section_config.uses_llm:
        return _load_static_template(section_config.prompt_template)

    # LLM-generated sections
    if use_llm:
        try:
            return _call_llm(section_id, evidence_packet, section_config)
        except Exception as e:
            print(f"  [WARNING] LLM call failed for '{section_id}': {e}")
            print(f"  [WARNING] Falling back to template rendering.")
            return _fallback_render(section_id, evidence_packet)
    else:
        return _fallback_render(section_id, evidence_packet)


def generate_all_sections(
    evidence_packets: dict[str, dict],
    report_config: ReportConfig,
    use_llm: bool = True,
) -> dict[str, str]:
    """
    Generate all sections. Returns {section_id: markdown_text}.
    """
    sections = {}
    for section_config in report_config.sections:
        sid = section_config.section_id
        print(f"  Generating section: {section_config.section_name}...")
        packet = evidence_packets.get(sid, {})
        sections[sid] = generate_section(sid, packet, section_config, use_llm)
    return sections


def _call_llm(
    section_id: str,
    evidence_packet: dict,
    section_config: SectionConfig,
) -> str:
    """Make a Gemini API call for one section."""
    from google import genai
    from google.genai import types

    # Load prompts
    system_prompt = _load_prompt("system.txt")
    section_template = _load_prompt_from_path(section_config.prompt_template)

    # Format the section prompt with evidence packet
    formatted_packet = format_packet_for_prompt(evidence_packet)
    user_message = section_template.replace("{evidence_packet}", formatted_packet)

    # API configuration from environment
    model_name = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
    api_key = os.environ.get("GEMINI_API_KEY", "")

    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY not set. Set it in .env or environment, "
            "or use --no-llm for template fallback."
        )

    client = genai.Client(api_key=api_key)
    
    response = client.models.generate_content(
        model=model_name,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.2,
            max_output_tokens=2000,
        )
    )

    return response.text


def _load_prompt(filename: str) -> str:
    """Load a prompt file from the prompts/ directory."""
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8")


def _load_prompt_from_path(relative_path: str) -> str:
    """Load a prompt file from a path relative to the project root."""
    path = Path(__file__).parent / relative_path
    return path.read_text(encoding="utf-8")


def _load_static_template(template_path: str) -> str:
    """Load a static template file (for non-LLM sections)."""
    return _load_prompt_from_path(template_path)


def _fallback_render(section_id: str, evidence_packet: dict) -> str:
    """
    Render evidence packet as formatted Markdown (LLM-06 fallback).
    Used when LLM is unavailable or explicitly skipped.
    No prose generation — just structured data presentation.
    """
    lines = []

    for key, value in evidence_packet.items():
        if key in ("section_id", "section_name", "data_notes"):
            continue

        if isinstance(value, dict):
            lines.append(f"**{_format_key(key)}**:\n")
            lines.append(_render_dict(value, indent=0))
        elif isinstance(value, list):
            lines.append(f"**{_format_key(key)}**:\n")
            for item in value:
                if isinstance(item, dict):
                    parts = [f"{k}: {v}" for k, v in item.items()]
                    lines.append(f"- {', '.join(parts)}")
                else:
                    lines.append(f"- {item}")
            lines.append("")
        else:
            lines.append(f"**{_format_key(key)}**: {value}\n")

    # Add data notes
    notes = evidence_packet.get("data_notes", [])
    if notes:
        lines.append("\n**Data Notes**:\n")
        for note in notes:
            lines.append(f"- {note}")

    return "\n".join(lines)


def _format_key(key: str) -> str:
    """Convert snake_case key to Title Case."""
    return key.replace("_", " ").title()


def _render_dict(d: dict, indent: int = 0) -> str:
    """Recursively render a dict as indented Markdown list."""
    lines = []
    prefix = "  " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            lines.append(f"{prefix}- **{_format_key(str(k))}**:")
            lines.append(_render_dict(v, indent + 1))
        elif isinstance(v, list):
            lines.append(f"{prefix}- **{_format_key(str(k))}**:")
            for item in v:
                if isinstance(item, dict):
                    parts = [f"{ik}: {iv}" for ik, iv in item.items()]
                    lines.append(f"{prefix}  - {', '.join(parts)}")
                else:
                    lines.append(f"{prefix}  - {item}")
        else:
            lines.append(f"{prefix}- {_format_key(str(k))}: {v}")
    return "\n".join(lines)

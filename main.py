"""
main.py — Entry point for the GenAR PADER Report Generator.

Executes the end-to-end pipeline:
1. Load and parse dataset
2. Run deterministic analyses
3. Build evidence packets
4. Generate sections (LLM or template fallback)
5. Review gate (generate review.json, wait for approval, or auto-approve)
6. Grounding check
7. Assemble final report
"""

import argparse
import sys
import json
from dotenv import load_dotenv

from config import PADER_CONFIG
from data_loader import load_dataset
from analysis import run_all_analyses
from evidence import build_evidence_packets
from llm_client import generate_all_sections, generate_section
from review import write_review_file, read_review_file, get_flagged_sections, auto_approve_all
from grounding import check_grounding, write_grounding_report
from assembler import assemble_report, write_case_listing_csv, build_case_listing_section


def main():
    parser = argparse.ArgumentParser(description="GenAR PADER Report Generator")
    parser.add_argument("--dataset", type=str, required=True,
                        help="Path to the ICSR dataset Excel file")
    parser.add_argument("--no-llm", action="store_true",
                        help="Skip LLM API calls and use formatted template fallback")
    parser.add_argument("--auto-approve", action="store_true",
                        help="Skip human review gate, auto-approve all sections")
    parser.add_argument("--resume-review", action="store_true",
                        help="Resume pipeline from existing review.json (regenerates flagged sections)")
    
    args = parser.parse_args()

    # Load environment variables (e.g., ANTHROPIC_API_KEY)
    load_dotenv()

    # Configure report
    config = PADER_CONFIG
    config.dataset_path = args.dataset

    print(f"Starting pipeline for {config.report_type} - {config.product_name}")

    # Phase 1: Data & Analysis
    print(f"\n[1/7] Loading and validating dataset from: {args.dataset}")
    try:
        data = load_dataset(args.dataset)
    except Exception as e:
        print(f"ERROR loading dataset: {e}")
        sys.exit(1)
    
    print(f"      Rows: {data.row_count} | Unique Cases: {data.case_count}")
    print(f"      Reporting Period: {data.reporting_period[0]} to {data.reporting_period[1]}")
    print(f"      Flagged rows (mismatched reactions/outcomes): {data.flagged_count}")

    print("\n[2/7] Running deterministic analyses...")
    analyses = run_all_analyses(data, top_n=config.top_n_reactions)

    print("\n[3/7] Building evidence packets...")
    evidence_packets = build_evidence_packets(analyses, config, data.reporting_period)

    # Save evidence packets for audit
    import os
    os.makedirs("output", exist_ok=True)
    with open("output/evidence_packets.json", "w", encoding="utf-8") as f:
        json.dump(evidence_packets, f, indent=2, ensure_ascii=False)
    print("      Saved to output/evidence_packets.json")

    # Phase 2: Generation & Review
    sections = {}

    if args.resume_review:
        print("\n[4/7] Resuming from existing review.json...")
        review_results = read_review_file()
        if not review_results:
            print("ERROR: --resume-review passed but output/review.json not found.")
            sys.exit(1)
        
        # Load previously generated text
        with open("output/review.json", "r", encoding="utf-8") as f:
            review_data = json.load(f)
            for sid, sdata in review_data.get("sections", {}).items():
                sections[sid] = sdata.get("generated_text", "")

        flagged = get_flagged_sections(review_results)
        if flagged:
            print(f"      Found {len(flagged)} flagged section(s) to regenerate:")
            for sid in flagged:
                print(f"        - {sid}")
                # Regenerate flagged section
                section_config = next(s for s in config.sections if s.section_id == sid)
                sections[sid] = generate_section(
                    sid, evidence_packets.get(sid, {}), section_config, not args.no_llm
                )
            
            # Re-write review file and stop again (unless auto-approve is on)
            if not args.auto_approve:
                write_review_file(sections, evidence_packets)
                print("\n      Regeneration complete. review.json updated.")
                print("      Please review the changes. Run with --resume-review again to continue.")
                sys.exit(0)
        else:
            print("      No flagged sections found. Proceeding to assembly.")
            # Note: If there are sections marked "pending", we will proceed if auto-approve is true,
            # or we might want to warn. For simplicity, we just proceed.
            if any(r.status == "pending" for r in review_results.values()):
                if not args.auto_approve:
                    print("      WARNING: Some sections are still 'pending'. Use --auto-approve to bypass.")
                    sys.exit(0)
    else:
        print("\n[4/7] Generating sections...")
        use_llm = not args.no_llm
        if use_llm:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                print("      WARNING: ANTHROPIC_API_KEY not found. LLM calls will fail.")
                print("      Run with --no-llm to use template fallback.")
        
        sections = generate_all_sections(evidence_packets, config, use_llm)

        # Generate special case listing section
        print("      Generating Case Index / Listing inline preview...")
        sections["case_listing"] = build_case_listing_section(analyses["case_listing"]["data"])

        if args.auto_approve:
            print("      --auto-approve flag present. Skipping human review gate.")
            write_review_file(sections, evidence_packets)
            # update review.json with "approved" status for record
            review_data = json.loads(open("output/review.json", encoding="utf-8").read())
            for sid in review_data["sections"]:
                review_data["sections"][sid]["status"] = "approved"
            with open("output/review.json", "w", encoding="utf-8") as f:
                json.dump(review_data, f, indent=2, ensure_ascii=False)
        else:
            print("\n[5/7] Review Gate (Action Required)")
            write_review_file(sections, evidence_packets)
            print("      Generated sections written to output/review.json")
            print("      Please review the generated text against the evidence packets.")
            print("      Change status from 'pending' to 'approved' or 'flagged'.")
            print("      When ready, run this script again with: --resume-review")
            sys.exit(0)

    # Phase 3: Grounding & Assembly
    print("\n[6/7] Running automated grounding check...")
    # Exclude case_listing and history_of_actions from grounding check as they are static/templates
    sections_to_check = {
        sid: text for sid, text in sections.items() 
        if sid not in ["case_listing", "history_of_actions"]
    }
    
    grounding_report = check_grounding(sections_to_check, evidence_packets)
    write_grounding_report(grounding_report)
    print(f"      {grounding_report.summary}")
    print("      Detailed results saved to output/grounding_report.json")

    print("\n[7/7] Assembling final report...")
    assemble_report(sections, config, data.reporting_period)
    print("      Report written to output/report.md")

    write_case_listing_csv(analyses["case_listing"]["data"])
    print("      Case listing written to output/case_listing.csv")

    print("\nPipeline completed successfully!")

if __name__ == "__main__":
    import os # need os for env check
    main()

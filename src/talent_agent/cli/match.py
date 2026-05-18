"""Match CLI: run the pipeline from command line."""

from __future__ import annotations

import argparse
import asyncio
import sys

from talent_agent.graph.pipeline import close_qdrant, run_pipeline


def main():
    parser = argparse.ArgumentParser(description="Match a JD against indexed projects")
    parser.add_argument("--jd", type=str, help="Path to JD text file")
    parser.add_argument("--jd-text", type=str, help="JD text directly")
    parser.add_argument("--intent", default="full_loop", choices=["match_only", "full_loop", "improve_only", "resume_only", "interview_only"])
    args = parser.parse_args()

    if args.jd:
        with open(args.jd, encoding="utf-8") as f:
            jd_text = f.read()
    elif args.jd_text:
        jd_text = args.jd_text
    else:
        print("Reading JD from stdin (paste and press Ctrl+D / Ctrl+Z)...")
        jd_text = sys.stdin.read()

    if not jd_text.strip():
        print("Error: empty JD text")
        sys.exit(1)

    try:
        session = asyncio.run(run_pipeline(jd_text, intent=args.intent))
    finally:
        close_qdrant()

    if session.parsed:
        print(f"\n{'='*60}")
        print(f"Role: {session.parsed.role} @ {session.parsed.company}")
        print(f"Must-have: {[s.name for s in session.parsed.must_skills]}")
        print(f"Plus: {[s.name for s in session.parsed.plus_skills]}")

    if session.match:
        print(f"\n{'='*60}")
        print("Top matches:")
        for i, m in enumerate(session.match.matches[:3]):
            print(
                f"  #{i+1} {m.project.name} — weighted {m.weighted_score:.0%} "
                f"(must {m.coverage:.0%} / plus {m.plus_coverage:.0%})"
            )
            print(f"      Matched must: {m.matched_skills}")
            print(f"      Matched plus: {m.matched_plus_skills}")
            print(f"      Missing must: {m.missing_skills}")

    if session.plan:
        print(f"\n{'='*60}")
        print("Improvement tasks:")
        for t in session.plan.tasks:
            print(f"  [{t.effort_days}d] {t.title}")
            print(f"       → {t.resume_impact}")

    if session.resume:
        print(f"\n{'='*60}")
        print(f"Resume: {session.resume.project_title}")
        print(f"Stack: {session.resume.stack_line}")
        for b in session.resume.star_bullets:
            print(f"  - {b}")


if __name__ == "__main__":
    main()

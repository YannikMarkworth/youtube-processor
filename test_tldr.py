#!/usr/bin/env python3
"""
Test script: Generates TLDRs for a few random videos WITHOUT writing anything.
Shows results for review so you can judge quality before batch-processing.

Usage:
    python test_tldr.py              # 5 random videos without TLDR
    python test_tldr.py --count 10   # 10 random videos
"""
import argparse
import json
import random
import re
import sys
from pathlib import Path

import yaml

import config
from classify_videos import _call_gemini, _call_openai, call_ai

TLDR_PROMPT_TEMPLATE = """You are generating TLDRs for YouTube video summaries.

For each video below, write a single-sentence TLDR (max 150 characters) that captures the core message.
The TLDR should be informative and specific — avoid generic descriptions.
Write the TLDR in the same language as the summary.

Respond with a JSON array where each entry has "video_id" and "tldr" keys.

Videos:
{videos_json}
"""


def find_videos_without_tldr(summaries_dir, max_count=5):
    """Finds summary files that have no tldr field in frontmatter."""
    candidates = []
    for f in summaries_dir.rglob("*.md"):
        try:
            content = f.read_text(encoding="utf-8")
        except Exception:
            continue

        m = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
        if not m:
            continue

        try:
            fm = yaml.safe_load(m.group(1))
        except yaml.YAMLError:
            continue

        if fm and not fm.get("tldr"):
            # Extract the summary body (after frontmatter)
            body = content[m.end():].strip()
            candidates.append({
                "filepath": f,
                "frontmatter": fm,
                "body": body[:800],  # First 800 chars of summary for context
            })

    random.shuffle(candidates)
    return candidates[:max_count]


def generate_tldrs(videos):
    """Sends videos to AI and returns generated TLDRs."""
    videos_for_prompt = []
    for v in videos:
        videos_for_prompt.append({
            "video_id": v["frontmatter"].get("video_id", "unknown"),
            "title": v["frontmatter"].get("title", "Untitled"),
            "channel": v["frontmatter"].get("channel", ""),
            "summary_excerpt": v["body"],
        })

    prompt = TLDR_PROMPT_TEMPLATE.format(videos_json=json.dumps(videos_for_prompt, ensure_ascii=False, indent=2))
    raw = call_ai(prompt, purpose="TLDR test generation", json_mode=True)
    if not raw:
        return None

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Error parsing AI response: {e}")
        print(f"Raw response:\n{raw[:500]}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Test TLDR generation (dry run)")
    parser.add_argument("--count", type=int, default=5, help="Number of videos to test (default: 5)")
    args = parser.parse_args()

    summaries_dir = config.SUMMARIES_DIR
    if not summaries_dir.exists():
        print(f"Error: Summaries directory not found: {summaries_dir}")
        sys.exit(1)

    print(f"Scanning {summaries_dir} for videos without TLDR...")
    videos = find_videos_without_tldr(summaries_dir, max_count=args.count)

    if not videos:
        print("All videos already have TLDRs!")
        return

    print(f"Found {len(videos)} videos without TLDR. Generating test TLDRs...\n")
    results = generate_tldrs(videos)

    if not results:
        print("Failed to generate TLDRs.")
        sys.exit(1)

    # Display results
    result_map = {r["video_id"]: r["tldr"] for r in results}

    print("=" * 70)
    print("TLDR PREVIEW (nothing was written to disk)")
    print("=" * 70)

    for v in videos:
        vid = v["frontmatter"].get("video_id", "unknown")
        title = v["frontmatter"].get("title", "Untitled")
        tldr = result_map.get(vid, "— no TLDR generated —")
        channel = v["frontmatter"].get("channel", "")

        print(f"\n{'─' * 70}")
        print(f"  Title:   {title}")
        print(f"  Channel: {channel}")
        print(f"  TLDR:    {tldr}")
        print(f"  Chars:   {len(tldr)}")

    print(f"\n{'─' * 70}")
    print(f"\n✓ {len(results)} TLDRs generated (dry run — no files modified)")


if __name__ == "__main__":
    main()

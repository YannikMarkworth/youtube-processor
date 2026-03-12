#!/usr/bin/env python3
"""
Generate TLDRs for YouTube video summaries.

Modes:
    python test_tldr.py                  # Dry run: preview 5 random TLDRs
    python test_tldr.py --count 10       # Dry run: preview 10 random TLDRs
    python test_tldr.py --write          # Write TLDRs into frontmatter (all videos)
    python test_tldr.py --write --count 20  # Write TLDRs for 20 videos per batch
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

For each video below, write a single-sentence TLDR (max 150 characters) that captures the SPECIFIC core insight or conclusion.

RULES:
- Be SPECIFIC: Include concrete details, names, numbers, or conclusions from the summary.
- NO filler phrases: Never start with "Learn", "Discover", "Find out", "Entdecke", "Erfahre", "Lerne".
- State the insight DIRECTLY as a fact or conclusion, not as an invitation to learn.
- Write in the same language as the summary.

BAD examples (too vague):
- "Learn to run effective weekly team meetings by focusing on five essential elements"
- "Entdecke, wie Googles Nano Banana beeindruckende KI-Bilder erstellt"

GOOD examples (specific):
- "Weekly team meetings work best with: wins, metrics, priorities, blockers, and action items"
- "Gemini 2.5 Flash erzeugt fotorealistische Bilder und übertrifft Midjourney bei Text-Rendering"

Respond with a JSON array where each entry has "video_id" and "tldr" keys.

Videos:
{videos_json}
"""

BATCH_SIZE = 10  # Videos per AI call


def find_videos_without_tldr(summaries_dir, max_count=None):
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
            body = content[m.end():].strip()
            candidates.append({
                "filepath": f,
                "frontmatter": fm,
                "body": body[:800],
                "raw_content": content,
                "fm_match": m,
            })

    random.shuffle(candidates)
    if max_count:
        return candidates[:max_count]
    return candidates


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
    raw = call_ai(prompt, purpose="TLDR generation", json_mode=True)
    if not raw:
        return None

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Error parsing AI response: {e}")
        print(f"Raw response:\n{raw[:500]}")
        return None


def write_tldr_to_file(video, tldr):
    """Inserts tldr field into the frontmatter of a summary file."""
    content = video["raw_content"]
    m = video["fm_match"]
    fm_text = m.group(1)

    # Insert tldr after the first line of frontmatter (or at end)
    fm_lines = fm_text.split("\n")
    insert_idx = 1  # After first field
    # Try to insert after 'title' line for consistent placement
    for i, line in enumerate(fm_lines):
        if line.startswith("title:"):
            insert_idx = i + 1
            break

    # Escape quotes in TLDR value
    escaped_tldr = tldr.replace('"', '\\"')
    fm_lines.insert(insert_idx, f'tldr: "{escaped_tldr}"')

    new_fm = "\n".join(fm_lines)
    new_content = f"---\n{new_fm}\n---{content[m.end():]}"

    video["filepath"].write_text(new_content, encoding="utf-8")


def display_results(videos, result_map, dry_run=True):
    """Display generated TLDRs."""
    mode = "PREVIEW (dry run)" if dry_run else "WRITTEN"
    print(f"\n{'=' * 70}")
    print(f"  TLDR {mode}")
    print(f"{'=' * 70}")

    for v in videos:
        vid = v["frontmatter"].get("video_id", "unknown")
        title = v["frontmatter"].get("title", "Untitled")
        tldr = result_map.get(vid)
        if not tldr:
            continue
        channel = v["frontmatter"].get("channel", "")

        print(f"\n{'─' * 70}")
        print(f"  Title:   {title}")
        print(f"  Channel: {channel}")
        print(f"  TLDR:    {tldr}")
        print(f"  Chars:   {len(tldr)}")

    print(f"\n{'─' * 70}")


def main():
    parser = argparse.ArgumentParser(description="Generate TLDRs for video summaries")
    parser.add_argument("--count", type=int, default=None,
                        help="Number of videos to process (default: 5 for dry run, all for --write)")
    parser.add_argument("--write", action="store_true",
                        help="Actually write TLDRs into summary files")
    args = parser.parse_args()

    summaries_dir = config.SUMMARIES_DIR
    if not summaries_dir.exists():
        print(f"Error: Summaries directory not found: {summaries_dir}")
        sys.exit(1)

    # Default count: 5 for dry run, unlimited for write mode
    max_count = args.count if args.count else (5 if not args.write else None)

    print(f"Scanning {summaries_dir} for videos without TLDR...")
    videos = find_videos_without_tldr(summaries_dir, max_count=max_count)

    if not videos:
        print("All videos already have TLDRs!")
        return

    print(f"Found {len(videos)} videos without TLDR.")
    if args.write:
        print(f"Mode: WRITE (will modify files)")
    else:
        print(f"Mode: DRY RUN (preview only)")

    # Process in batches
    total_written = 0
    total_failed = 0

    for batch_start in range(0, len(videos), BATCH_SIZE):
        batch = videos[batch_start:batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (len(videos) + BATCH_SIZE - 1) // BATCH_SIZE

        print(f"\n[Batch {batch_num}/{total_batches}] Generating TLDRs for {len(batch)} videos...")
        results = generate_tldrs(batch)

        if not results:
            print(f"  Failed to generate TLDRs for this batch.")
            total_failed += len(batch)
            continue

        result_map = {r["video_id"]: r["tldr"] for r in results}

        if args.write:
            for v in batch:
                vid = v["frontmatter"].get("video_id", "unknown")
                tldr = result_map.get(vid)
                if not tldr:
                    total_failed += 1
                    continue
                try:
                    write_tldr_to_file(v, tldr)
                    total_written += 1
                except Exception as e:
                    print(f"  Error writing {v['filepath'].name}: {e}")
                    total_failed += 1

        display_results(batch, result_map, dry_run=not args.write)

    # Final summary
    print(f"\n{'=' * 70}")
    if args.write:
        print(f"Done. {total_written} TLDRs written, {total_failed} failed.")
    else:
        print(f"Done. {len(videos)} TLDRs previewed (dry run — no files modified).")
        print(f"Run with --write to apply.")


if __name__ == "__main__":
    main()

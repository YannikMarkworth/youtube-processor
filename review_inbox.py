"""
Inbox Review Script
===================
Analyzes videos in the "Inbox" category and uses AI to propose taxonomy
expansions or reclassifications. After user confirmation, updates
categories.txt and reclassifies the affected videos.

Usage:
    python review_inbox.py                  # Interactive review
    python review_inbox.py --dry-run        # Preview without changes
    python review_inbox.py --auto           # Apply AI suggestions without confirmation

Requires: Same .env config as main.py (API keys, AI_PROVIDER, etc.)
"""

import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

import yaml
import config

# --- Conditional AI imports ---
if config.AI_PROVIDER == 'openai':
    import openai
elif config.AI_PROVIDER == 'gemini':
    from google import genai


# ==============================================================================
# --- TAXONOMY HELPERS ---
# ==============================================================================

def load_taxonomy(taxonomy_path):
    """Parses categories.txt into a flat list of category paths."""
    taxonomy_path = Path(taxonomy_path)
    if not taxonomy_path.exists():
        print(f"Error: Taxonomy file not found: {taxonomy_path}")
        sys.exit(1)

    lines = taxonomy_path.read_text(encoding="utf-8").splitlines()
    categories = []
    stack = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        indent = len(line) - len(line.lstrip())
        level = indent // 2
        stack = stack[:level]
        stack.append(stripped)
        categories.append(" > ".join(stack))

    return categories


def rebuild_categories_file(taxonomy_path, new_paths):
    """Rebuilds categories.txt from a flat list of category paths."""
    taxonomy_path = Path(taxonomy_path)

    # Build tree structure to produce properly indented output
    tree = {}
    for path in new_paths:
        parts = [p.strip() for p in path.split(" > ")]
        node = tree
        for part in parts:
            if part not in node:
                node[part] = {}
            node = node[part]

    lines = []
    def write_tree(node, depth=0):
        for i, (name, children) in enumerate(node.items()):
            lines.append("  " * depth + name)
            write_tree(children, depth + 1)
            # Add blank line after top-level categories
            if depth == 0:
                lines.append("")

    write_tree(tree)

    taxonomy_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


# ==============================================================================
# --- FILE SCANNING ---
# ==============================================================================

def find_inbox_videos(summaries_dir):
    """Finds all videos categorized as 'Inbox'."""
    summaries_dir = Path(summaries_dir)
    inbox_videos = []

    for filepath in sorted(summaries_dir.rglob("*– Summary.md")):
        try:
            content = filepath.read_text(encoding="utf-8")
        except Exception:
            continue

        match = re.match(r"^---\n(.*?)\n---\n?(.*)", content, re.DOTALL)
        if not match:
            continue

        try:
            fm = yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            continue

        if not fm:
            continue

        category = str(fm.get("category", "") or "").strip()
        if category.lower() == "inbox" or not category:
            # Extract summary excerpt
            body = match.group(2).strip()
            summary_match = re.search(r'## AI Summary\s*\n+(.*?)(?=\n## |\Z)', body, re.DOTALL)
            excerpt = ""
            if summary_match:
                words = summary_match.group(1).strip().split()
                excerpt = " ".join(words[:150])

            inbox_videos.append({
                "filepath": str(filepath),
                "title": fm.get("title", filepath.stem),
                "channel": fm.get("channel", "Unknown"),
                "excerpt": excerpt,
            })

    return inbox_videos


# ==============================================================================
# --- AI CALLS ---
# ==============================================================================

def call_ai(prompt, purpose="inbox review", json_mode=False):
    """Sends a prompt to the configured AI provider."""
    if config.AI_PROVIDER == 'openai':
        return _call_openai(prompt, purpose)
    elif config.AI_PROVIDER == 'gemini':
        return _call_gemini(prompt, purpose, json_mode=json_mode)
    else:
        print(f"Error: Unsupported AI_PROVIDER '{config.AI_PROVIDER}'")
        return None


def _call_openai(prompt, purpose):
    if not config.OPENAI_API_KEY:
        print("Error: OpenAI API Key missing.")
        return None
    try:
        client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=16000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"OpenAI API call failed for {purpose}: {e}")
        return None


def _call_gemini(prompt, purpose, json_mode=False):
    if not config.GEMINI_API_KEY:
        print("Error: Gemini API Key missing.")
        return None
    try:
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        gen_config = {
            "max_output_tokens": 16000,
            "temperature": 0.3,
        }
        if json_mode:
            gen_config["response_mime_type"] = "application/json"
        response = client.models.generate_content(
            model=f"models/{config.GEMINI_MODEL_NAME}",
            contents=prompt,
            config=gen_config,
        )
        return response.text.strip()
    except Exception as e:
        print(f"Gemini API call failed for {purpose}: {e}")
        return None


# ==============================================================================
# --- INBOX ANALYSIS ---
# ==============================================================================

INBOX_REVIEW_PROMPT = """You are analyzing uncategorized YouTube videos to improve a taxonomy.

CURRENT TAXONOMY:
{taxonomy}

INBOX VIDEOS (these don't fit any existing category):
{video_list}

Your task:
1. Group the inbox videos by topic/theme.
2. For each group, decide:
   a) Can these videos fit into an EXISTING category from the taxonomy? If yes, which one?
   b) Or do they need a NEW category/subcategory? If yes, propose one that fits the taxonomy style.

RULES:
- Only propose new categories if there are 3+ videos that would belong there.
- New categories should use the same naming style as existing ones (English, concise).
- Prefer adding subcategories under existing top-level categories over creating new top-level ones.
- If a group has fewer than 3 videos, assign them to the closest existing category.

Respond with a JSON object:
{{
  "reclassify": [
    {{"titles": ["Video Title 1", "Video Title 2"], "target_category": "Existing > Category > Path"}}
  ],
  "new_categories": [
    {{
      "path": "Parent > New Subcategory",
      "titles": ["Video Title 3", "Video Title 4", "Video Title 5"],
      "reason": "Brief explanation why this category is needed"
    }}
  ],
  "keep_inbox": ["Video Title 6"]
}}

Only output the JSON object, no other text."""


def analyze_inbox(inbox_videos, taxonomy_paths):
    """Sends inbox videos to AI for clustering and taxonomy suggestions."""
    if not inbox_videos:
        return None

    taxonomy_text = "\n".join(f"- {p}" for p in taxonomy_paths)

    video_lines = []
    for i, v in enumerate(inbox_videos, 1):
        video_lines.append(f"{i}. Title: {v['title']}")
        video_lines.append(f"   Channel: {v['channel']}")
        if v['excerpt']:
            words = v['excerpt'].split()
            short = " ".join(words[:60])
            video_lines.append(f"   Summary: {short}")
        video_lines.append("")

    video_list = "\n".join(video_lines)

    prompt = INBOX_REVIEW_PROMPT.format(
        taxonomy=taxonomy_text,
        video_list=video_list,
    )

    response = call_ai(prompt, "inbox analysis", json_mode=True)
    if not response:
        return None

    # Parse JSON response
    cleaned = re.sub(r'```(?:json)?\s*\n?', '', response)
    cleaned = cleaned.replace('```', '')

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"Failed to parse AI response: {e}")
        return None


# ==============================================================================
# --- FRONTMATTER UPDATE ---
# ==============================================================================

def split_category_path(category_path):
    """Splits 'A > B > C' into {'category': 'A', 'subcategory': 'B', 'topic': 'C'}."""
    parts = [p.strip() for p in category_path.split(" > ")]
    return {
        "category": parts[0] if len(parts) > 0 else "",
        "subcategory": parts[1] if len(parts) > 1 else "",
        "topic": parts[2] if len(parts) > 2 else "",
    }


def reclassify_video(filepath, category):
    """Updates the category fields in a video's YAML frontmatter."""
    filepath = Path(filepath)
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  Error reading {filepath.name}: {e}")
        return False

    yaml_match = re.match(r'^(---\n)(.*?)(\n---)', content, re.DOTALL)
    if not yaml_match:
        return False

    try:
        fm = yaml.safe_load(yaml_match.group(2))
        if fm is None:
            fm = {}
    except yaml.YAMLError:
        return False

    cat_parts = split_category_path(category)
    fm["category"] = cat_parts["category"]
    fm["subcategory"] = cat_parts["subcategory"]
    fm["topic"] = cat_parts["topic"]

    new_yaml = yaml.dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False)
    rest_of_file = content[yaml_match.end():]
    new_content = f"---\n{new_yaml}---{rest_of_file}"

    try:
        filepath.write_text(new_content, encoding="utf-8")
        return True
    except Exception as e:
        print(f"  Error writing {filepath.name}: {e}")
        return False


def find_video_by_title(title, inbox_videos):
    """Matches a title to a video in the inbox list."""
    title_lower = title.lower().strip()
    for v in inbox_videos:
        if v['title'].lower().strip() == title_lower:
            return v
    for v in inbox_videos:
        if title_lower in v['title'].lower() or v['title'].lower() in title_lower:
            return v
    return None


# ==============================================================================
# --- MAIN ---
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Review Inbox videos and propose taxonomy changes.")
    parser.add_argument("--dry-run", action="store_true", help="Preview suggestions without applying changes")
    parser.add_argument("--auto", action="store_true", help="Apply all AI suggestions without confirmation")
    args = parser.parse_args()

    taxonomy_path = config.BASE_DIR / "categories.txt"

    print("=" * 60)
    print("Inbox Review")
    print(f"AI Provider: {config.AI_PROVIDER.upper()}")
    print("=" * 60)

    # Load taxonomy
    taxonomy_paths = load_taxonomy(taxonomy_path)
    print(f"Loaded {len(taxonomy_paths)} category paths.")

    # Find inbox videos
    print("Scanning for Inbox videos...")
    inbox_videos = find_inbox_videos(config.SUMMARIES_DIR)
    print(f"Found {len(inbox_videos)} Inbox videos.")

    if not inbox_videos:
        print("No Inbox videos found. Nothing to review.")
        return

    # Analyze with AI
    print("\nAnalyzing Inbox videos with AI...")
    suggestions = analyze_inbox(inbox_videos, taxonomy_paths)

    if not suggestions:
        print("AI analysis returned no results.")
        return

    # Display results
    print(f"\n{'=' * 60}")
    print("AI SUGGESTIONS")
    print(f"{'=' * 60}")

    reclassify = suggestions.get("reclassify", [])
    new_cats = suggestions.get("new_categories", [])
    keep = suggestions.get("keep_inbox", [])

    if reclassify:
        print(f"\n--- Reclassify to existing categories ({sum(len(r['titles']) for r in reclassify)} videos) ---")
        for r in reclassify:
            print(f"\n  -> {r['target_category']}")
            for t in r.get("titles", []):
                print(f"     - {t[:70]}")

    if new_cats:
        print(f"\n--- New categories to add ({len(new_cats)}) ---")
        for nc in new_cats:
            print(f"\n  + {nc['path']}")
            print(f"    Reason: {nc.get('reason', 'N/A')}")
            for t in nc.get("titles", []):
                print(f"     - {t[:70]}")

    if keep:
        print(f"\n--- Keep in Inbox ({len(keep)} videos) ---")
        for t in keep:
            print(f"  - {t[:70]}")

    if args.dry_run:
        print("\n--- DRY RUN complete. No changes made. ---")
        return

    # Confirmation
    if not args.auto:
        print(f"\n{'=' * 60}")
        response = input("Apply these changes? [y/N/s(elective)] ").strip().lower()
        if response == 's':
            # Selective mode: confirm each group
            confirmed_reclassify = []
            confirmed_new_cats = []

            for r in reclassify:
                ans = input(f"  Reclassify {len(r['titles'])} videos to '{r['target_category']}'? [y/N] ").strip().lower()
                if ans == 'y':
                    confirmed_reclassify.append(r)

            for nc in new_cats:
                ans = input(f"  Add new category '{nc['path']}' ({len(nc['titles'])} videos)? [y/N] ").strip().lower()
                if ans == 'y':
                    confirmed_new_cats.append(nc)

            reclassify = confirmed_reclassify
            new_cats = confirmed_new_cats
        elif response != 'y':
            print("Aborted.")
            return

    # Apply changes
    total_reclassified = 0
    total_failed = 0

    # 1. Add new categories to taxonomy
    if new_cats:
        print("\nUpdating categories.txt...")
        all_paths = set(taxonomy_paths)
        for nc in new_cats:
            new_path = nc["path"]
            # Add the new path and all parent paths
            parts = [p.strip() for p in new_path.split(" > ")]
            for i in range(1, len(parts) + 1):
                all_paths.add(" > ".join(parts[:i]))

        # Sort paths for consistent output
        sorted_paths = sorted(all_paths)
        rebuild_categories_file(taxonomy_path, sorted_paths)
        print(f"  Added {len(new_cats)} new category paths.")

    # 2. Reclassify videos to existing categories
    if reclassify:
        print("\nReclassifying videos...")
        for r in reclassify:
            target = r["target_category"]
            for title in r.get("titles", []):
                video = find_video_by_title(title, inbox_videos)
                if not video:
                    print(f"  Could not match: '{title[:60]}...'")
                    total_failed += 1
                    continue
                if reclassify_video(video["filepath"], target):
                    total_reclassified += 1
                    print(f"  {title[:50]}... -> {target}")
                else:
                    total_failed += 1

    # 3. Reclassify videos into new categories
    if new_cats:
        print("\nClassifying videos into new categories...")
        for nc in new_cats:
            target = nc["path"]
            for title in nc.get("titles", []):
                video = find_video_by_title(title, inbox_videos)
                if not video:
                    print(f"  Could not match: '{title[:60]}...'")
                    total_failed += 1
                    continue
                if reclassify_video(video["filepath"], target):
                    total_reclassified += 1
                    print(f"  {title[:50]}... -> {target}")
                else:
                    total_failed += 1

    print(f"\n{'=' * 60}")
    print(f"Inbox Review complete!")
    print(f"  Reclassified: {total_reclassified}")
    print(f"  Failed:       {total_failed}")
    print(f"  Kept in Inbox: {len(keep)}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()

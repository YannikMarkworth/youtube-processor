"""
Video Classification Script
============================
Reads existing summary files and classifies each video into the taxonomy
defined in categories.txt. Updates the YAML frontmatter of each summary
file with the assigned category.

Usage:
    python classify_videos.py                  # Full run
    python classify_videos.py --dry-run        # Preview without API calls or file changes
    python classify_videos.py --limit 50       # Only process first 50 unclassified files
    python classify_videos.py --batch-size 30  # Videos per API batch (default: 40)
    python classify_videos.py --reclassify     # Re-classify all videos (even already classified ones)

Requires: Same .env config as main.py (API keys, AI_PROVIDER, etc.)
"""

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path

import yaml
import config


# ==============================================================================
# --- FORMAT HELPERS ---
# ==============================================================================

def split_category_path(category_path):
    """Splits 'A > B > C' into {'category': 'A', 'subcategory': 'B', 'topic': 'C'}."""
    parts = [p.strip() for p in category_path.split(" > ")]
    return {
        "category": parts[0] if len(parts) > 0 else "",
        "subcategory": parts[1] if len(parts) > 1 else "",
        "topic": parts[2] if len(parts) > 2 else "",
    }


def format_iso_date(date_str):
    """Converts '2024-01-15T12:30:00Z' to '2024-01-15'. Passes through already-clean dates."""
    if not date_str or date_str == "N/A":
        return date_str
    # Already in YYYY-MM-DD format
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return date_str
    # ISO 8601 timestamp — take just the date part
    m = re.match(r'^(\d{4}-\d{2}-\d{2})', date_str)
    return m.group(1) if m else date_str


def format_iso_duration(duration_str):
    """Converts 'PT1H23M45S' to '1:23:45' or 'PT11M58S' to '11:58'. Passes through already-clean values."""
    if not duration_str or duration_str == "N/A":
        return duration_str
    # Already in MM:SS or H:MM:SS format
    if re.match(r'^\d+:\d{2}(:\d{2})?$', duration_str):
        return duration_str
    # ISO 8601 duration
    m = re.match(r'^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$', duration_str)
    if not m:
        return duration_str
    hours = int(m.group(1) or 0)
    minutes = int(m.group(2) or 0)
    seconds = int(m.group(3) or 0)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"

# --- Conditional AI imports (same pattern as ai_utils.py) ---
if config.AI_PROVIDER == 'openai':
    import openai
elif config.AI_PROVIDER == 'gemini':
    from google import genai


# ==============================================================================
# --- TAXONOMY LOADING ---
# ==============================================================================

def load_taxonomy(taxonomy_path):
    """
    Parses categories.txt (indent-based) into a flat list of category paths.
    E.g. "Pen & Paper / TTRPGs > Spielleiter (DM) > Session Prep & Tools"
    """
    taxonomy_path = Path(taxonomy_path)
    if not taxonomy_path.exists():
        print(f"Error: Taxonomy file not found: {taxonomy_path}")
        sys.exit(1)

    lines = taxonomy_path.read_text(encoding="utf-8").splitlines()
    categories = []
    stack = []  # [(indent_level, name), ...]

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Count leading spaces (2 spaces per level)
        indent = len(line) - len(line.lstrip())
        level = indent // 2

        # Trim stack to current level
        stack = stack[:level]
        stack.append(stripped)

        # Build full path
        categories.append(" > ".join(stack))

    return categories


# ==============================================================================
# --- FILE SCANNING ---
# ==============================================================================

def scan_summary_files(summaries_dir, limit=None, reclassify=False, fix_only=False, taxonomy_set=None):
    """
    Scans for summary files. Returns list of dicts with file info.
    Skips already-classified files unless reclassify=True.
    If fix_only=True, only returns uncategorized or inconsistent files.
    """
    summaries_dir = Path(summaries_dir)
    if not summaries_dir.exists():
        print(f"Error: Summaries directory not found: {summaries_dir}")
        sys.exit(1)

    summary_files = sorted(summaries_dir.rglob("*– Summary.md"))
    print(f"Found {len(summary_files)} summary files total.")

    results = []
    skipped = 0
    for filepath in summary_files:
        info = extract_file_info(filepath)
        if not info:
            continue

        if fix_only:
            # Only include uncategorized or inconsistent files
            cat = info.get("existing_category")
            full_path = info.get("full_category_path")
            if not cat:
                results.append(info)  # uncategorized
            elif taxonomy_set and full_path and full_path not in taxonomy_set:
                results.append(info)  # inconsistent
            else:
                skipped += 1
            continue

        # Skip already classified unless reclassify
        if not reclassify and info.get("existing_category"):
            skipped += 1
            continue

        results.append(info)

    if skipped:
        if fix_only:
            print(f"Skipped {skipped} correctly-classified files.")
        else:
            print(f"Skipped {skipped} already-classified files (use --reclassify to redo).")

    if limit:
        results = results[:limit]
        print(f"Limited to {limit} files.")

    print(f"Will classify {len(results)} files.")
    return results


def extract_file_info(filepath):
    """Extracts title, excerpt, and existing category from a summary file."""
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception as e:
        logging.warning(f"Could not read {filepath}: {e}")
        return None

    # Parse YAML frontmatter
    existing_category = None
    full_category_path = None
    title = "Unknown"
    yaml_match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if yaml_match:
        try:
            fm = yaml.safe_load(yaml_match.group(1))
            if fm:
                title = fm.get("title", "Unknown")
                existing_category = fm.get("category")
                # Reconstruct full path for fix-only consistency checking
                parts = [str(fm.get(k, "") or "").strip()
                         for k in ("category", "subcategory", "topic")]
                parts = [p for p in parts if p]
                full_category_path = " > ".join(parts) if parts else None
        except yaml.YAMLError:
            pass
    else:
        title_match = re.search(r'\*\*Title:\*\*\s*(.+)', content)
        if title_match:
            title = title_match.group(1).strip()

    # Extract playlist from folder name
    playlist = filepath.parent.name

    # Extract AI Summary excerpt (~200 words)
    summary_match = re.search(r'## AI Summary\s*\n+(.*?)(?=\n## |\Z)', content, re.DOTALL)
    excerpt = ""
    if summary_match:
        words = summary_match.group(1).strip().split()
        excerpt = " ".join(words[:200])

    if not excerpt:
        return None

    return {
        "filepath": str(filepath),
        "title": title,
        "playlist": playlist,
        "excerpt": excerpt,
        "existing_category": existing_category,
        "full_category_path": full_category_path,
    }


# ==============================================================================
# --- AI CALLS ---
# ==============================================================================

def call_ai(prompt, purpose="classification", json_mode=False):
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
            temperature=0.2,
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
            "temperature": 0.2,
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
# --- CLASSIFICATION ---
# ==============================================================================

CLASSIFY_PROMPT_TEMPLATE = """You are classifying YouTube videos into a predefined taxonomy.

TAXONOMY (use EXACTLY one of these categories per video — copy the full path precisely):
{taxonomy}

VIDEOS TO CLASSIFY:
{video_list}

For each video, assign the MOST SPECIFIC matching category from the taxonomy above.
Use the EXACT category path string from the list — do not invent new categories.
If no category fits well, use the closest parent category.

DISAMBIGUATION RULES (use these when a video touches multiple categories):
1. Purpose over Tool: Ask "What is the end goal?" A video about Obsidian FOR D&D prep → Tabletop RPGs > Spielleiter. A video about ComfyUI for generating film images → Technologie, KI & Personal Knowledge Management > Künstliche Intelligenz (KI) > Media Creation.
2. Creating vs. Consuming: If someone analyzes a Game of Thrones character to teach YOU how to write better characters → Storytelling & Creative Writing. If it's a lore deep-dive to understand the show → Entertainment & Filmanalyse.
3. One folder only: Each video gets exactly ONE category. Use the most specific matching level.

Respond with a JSON array. Each entry must have "title" and "category" keys.
The "category" value must be copied exactly from the taxonomy list above.

Example:
[
  {{"title": "Video Title 1", "category": "Technologie, KI & Personal Knowledge Management > Künstliche Intelligenz (KI) > Produktivität & LLMs"}},
  {{"title": "Video Title 2", "category": "Magic: The Gathering (MTG) > Commander (EDH) > Deck Techs & Builds"}}
]

Only output the JSON array, no other text."""


def create_batches(items, batch_size):
    """Splits items into batches."""
    return [items[i:i + batch_size] for i in range(0, len(items), batch_size)]


def format_batch_for_prompt(batch):
    """Formats a batch of video infos for the classification prompt."""
    lines = []
    for i, item in enumerate(batch, 1):
        lines.append(f"{i}. Title: {item['title']}")
        lines.append(f"   Playlist: {item['playlist']}")
        words = item['excerpt'].split()
        short_excerpt = " ".join(words[:80])
        lines.append(f"   Summary: {short_excerpt}")
        lines.append("")
    return "\n".join(lines)


def parse_batch_response(response):
    """Parses the JSON array from the AI response, recovering truncated JSON."""
    if not response:
        return []

    cleaned = re.sub(r'```(?:json)?\s*\n?', '', response)
    cleaned = cleaned.replace('```', '')

    json_match = re.search(r'\[.*\]', cleaned, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    array_start = cleaned.find('[')
    if array_start == -1:
        print("  Warning: Could not find JSON array in response.")
        return []

    truncated = cleaned[array_start:]
    last_brace = truncated.rfind('}')
    if last_brace == -1:
        return []

    partial = truncated[:last_brace + 1] + ']'
    try:
        data = json.loads(partial)
        print(f"  (Recovered {len(data)} items from truncated response)")
        return data
    except json.JSONDecodeError as e:
        print(f"  Warning: Failed to parse JSON: {e}")
        return []


def match_title_to_file(title, batch):
    """Fuzzy-matches an AI-returned title to a file in the batch."""
    title_lower = title.lower().strip()
    for item in batch:
        if item['title'].lower().strip() == title_lower:
            return item
    # Partial match fallback
    for item in batch:
        if title_lower in item['title'].lower() or item['title'].lower() in title_lower:
            return item
    return None


# ==============================================================================
# --- FRONTMATTER UPDATE ---
# ==============================================================================

def convert_old_format_and_set_category(filepath, content, category):
    """Converts old inline-metadata format to YAML frontmatter and sets category."""
    def extract_inline(key, text):
        m = re.search(rf'\*\*{key}:\*\*\s*(.+)', text)
        return m.group(1).strip() if m else ""

    title = extract_inline("Title", content) or "Unknown"
    video_url = extract_inline("Video URL", content)
    channel_raw = extract_inline("Channel", content)
    uploaded = extract_inline("Uploaded", content)
    duration = extract_inline("Duration", content)
    playlist_raw = extract_inline("Playlist", content)

    # Extract video_id from URL
    vid_match = re.search(r'[?&]v=([a-zA-Z0-9_-]{11})', video_url or "")
    video_id = vid_match.group(1) if vid_match else ""

    # Clean wiki link markers for YAML values
    channel = re.sub(r'\[\[▶️\s*|\]\]', '', channel_raw).strip()
    playlist = re.sub(r'\[\[Playlist\s*|\]\]', '', playlist_raw).strip()

    # Split category into 3 levels
    cat_parts = split_category_path(category)

    # Build frontmatter
    fm = {"title": title, "video_id": video_id, "video_url": video_url,
          "channel": channel, "uploaded": format_iso_date(uploaded),
          "duration": format_iso_duration(duration),
          "playlist": playlist,
          "category": cat_parts["category"],
          "subcategory": cat_parts["subcategory"],
          "topic": cat_parts["topic"]}

    # Prepend YAML frontmatter to existing content (keep everything as-is)
    new_yaml = yaml.dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False)
    new_content = f"---\n{new_yaml}---\n\n{content}"

    try:
        filepath.write_text(new_content, encoding="utf-8")
        print(f"  Converted old format → YAML: {filepath.name}")
        return True
    except Exception as e:
        print(f"  Error writing converted file {filepath.name}: {e}")
        return False


def update_frontmatter_category(filepath, category):
    """Updates the 'category' field in the YAML frontmatter of a summary file."""
    filepath = Path(filepath)
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  Error reading {filepath.name}: {e}")
        return False

    yaml_match = re.match(r'^(---\n)(.*?)(\n---)', content, re.DOTALL)
    if not yaml_match:
        return convert_old_format_and_set_category(filepath, content, category)

    try:
        fm = yaml.safe_load(yaml_match.group(2))
        if fm is None:
            fm = {}
    except yaml.YAMLError as e:
        print(f"  Error parsing YAML in {filepath.name}: {e}")
        return False

    # Split category into 3 levels
    cat_parts = split_category_path(category)
    fm["category"] = cat_parts["category"]
    fm["subcategory"] = cat_parts["subcategory"]
    fm["topic"] = cat_parts["topic"]

    # Normalize date and duration formats while we're at it
    if "uploaded" in fm:
        fm["uploaded"] = format_iso_date(str(fm["uploaded"]))
    if "duration" in fm:
        fm["duration"] = format_iso_duration(str(fm["duration"]))

    # Rebuild file
    new_yaml = yaml.dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False)
    rest_of_file = content[yaml_match.end():]
    new_content = f"---\n{new_yaml}---{rest_of_file}"

    try:
        filepath.write_text(new_content, encoding="utf-8")
        return True
    except Exception as e:
        print(f"  Error writing {filepath.name}: {e}")
        return False


# ==============================================================================
# --- MAIN ---
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Classify videos using the taxonomy from categories.txt.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without API calls or file changes")
    parser.add_argument("--limit", type=int, default=None, help="Only process first N unclassified files")
    parser.add_argument("--batch-size", type=int, default=40, help="Videos per API batch (default: 40)")
    parser.add_argument("--reclassify", action="store_true", help="Re-classify all videos, even already classified ones")
    parser.add_argument("--fix-only", action="store_true", help="Only re-classify uncategorized or inconsistent videos")
    args = parser.parse_args()

    print("=" * 60)
    print("Video Classification")
    print(f"AI Provider: {config.AI_PROVIDER.upper()}")
    print(f"Summaries Dir: {config.SUMMARIES_DIR}")
    print("=" * 60)

    # Load taxonomy
    taxonomy_path = config.BASE_DIR / "categories.txt"
    categories = load_taxonomy(taxonomy_path)
    print(f"\nLoaded {len(categories)} categories from {taxonomy_path}")

    # Build taxonomy set for fix-only mode
    taxonomy_set = set(categories) if args.fix_only else None

    # Scan files
    files = scan_summary_files(config.SUMMARIES_DIR, limit=args.limit, reclassify=args.reclassify,
                               fix_only=args.fix_only, taxonomy_set=taxonomy_set)
    if not files:
        print("No files to classify. Done.")
        sys.exit(0)

    if args.dry_run:
        print(f"\n--- DRY RUN ---")
        print(f"Would classify {len(files)} files.")
        print(f"\nFirst 5 files:")
        for f in files[:5]:
            print(f"  - {f['title']}")
        print(f"\nTaxonomy ({len(categories)} categories):")
        for c in categories[:10]:
            print(f"  - {c}")
        if len(categories) > 10:
            print(f"  ... and {len(categories) - 10} more")
        print("\n--- DRY RUN complete. No API calls or file changes made. ---")
        return

    # Process in batches
    batches = create_batches(files, args.batch_size)
    print(f"\nSplit {len(files)} videos into {len(batches)} batches of ~{args.batch_size}.")

    taxonomy_text = "\n".join(f"- {c}" for c in categories)
    total_classified = 0
    total_failed = 0

    for i, batch in enumerate(batches, 1):
        print(f"\nBatch {i}/{len(batches)} ({len(batch)} videos)...")
        video_list = format_batch_for_prompt(batch)
        prompt = CLASSIFY_PROMPT_TEMPLATE.format(
            taxonomy=taxonomy_text,
            video_list=video_list,
        )

        response = call_ai(prompt, f"batch {i} classification", json_mode=True)
        if not response:
            print(f"  Warning: Batch {i} failed. Skipping.")
            total_failed += len(batch)
            continue

        parsed = parse_batch_response(response)
        print(f"  Got {len(parsed)} classifications.")

        # Apply classifications
        for item in parsed:
            title = item.get("title", "")
            category = item.get("category", "")
            matched_file = match_title_to_file(title, batch)

            if not matched_file:
                print(f"  Could not match: '{title[:60]}...'")
                total_failed += 1
                continue

            if not category:
                print(f"  No category for: '{title[:60]}...'")
                total_failed += 1
                continue

            success = update_frontmatter_category(matched_file['filepath'], category)
            if success:
                total_classified += 1
                logging.info(f"Classified '{title}' -> {category}")
            else:
                total_failed += 1

        # Rate limiting
        if i < len(batches):
            time.sleep(2)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Classification complete!")
    print(f"  Classified: {total_classified}")
    print(f"  Failed:     {total_failed}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()

"""
Video Retagging Script
======================
Scans existing summary files and assigns tags to videos that have no tags.
Uses the AI provider configured in .env to generate 3-5 tags per video.

Usage:
    python retag_videos.py                  # Full run
    python retag_videos.py --dry-run        # Preview without API calls or file changes
    python retag_videos.py --limit 50       # Only process first 50 untagged files
    python retag_videos.py --batch-size 30  # Videos per API batch (default: 40)
    python retag_videos.py --retag          # Re-tag all videos (even already tagged ones)

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

# --- Conditional AI imports (same pattern as classify_videos.py) ---
if config.AI_PROVIDER == 'openai':
    import openai
elif config.AI_PROVIDER == 'gemini':
    from google import genai


# ==============================================================================
# --- TAG NORMALIZATION (shared with ai_utils.py) ---
# ==============================================================================

def normalize_tag(tag):
    """Normalizes a tag: lowercase, hyphenated, no duplicates or trailing punctuation."""
    tag = tag.strip().lower()
    tag = re.sub(r'[\s_]+', '-', tag)
    tag = re.sub(r'-{2,}', '-', tag)
    tag = tag.strip('-')
    tag = re.sub(r'[.,;:!?]+$', '', tag)
    return tag


# ==============================================================================
# --- FILE SCANNING ---
# ==============================================================================

def scan_untagged_files(summaries_dir, limit=None, retag=False):
    """Scans for summary files missing tags. Returns list of dicts with file info."""
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

        # Skip already tagged unless retag
        if not retag and info.get("existing_tags"):
            skipped += 1
            continue

        results.append(info)

    if skipped:
        print(f"Skipped {skipped} already-tagged files (use --retag to redo).")

    if limit:
        results = results[:limit]
        print(f"Limited to {limit} files.")

    print(f"Will tag {len(results)} files.")
    return results


def extract_file_info(filepath):
    """Extracts title, excerpt, category, and existing tags from a summary file."""
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception as e:
        logging.warning(f"Could not read {filepath}: {e}")
        return None

    existing_tags = []
    title = "Unknown"
    category = ""
    yaml_match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if yaml_match:
        try:
            fm = yaml.safe_load(yaml_match.group(1))
            if fm:
                title = fm.get("title", "Unknown")
                tags = fm.get("tags", [])
                if tags is None:
                    tags = []
                if isinstance(tags, str):
                    tags = [t.strip() for t in tags.split(",") if t.strip()]
                existing_tags = tags
                # Reconstruct category path
                parts = [str(fm.get(k, "") or "").strip()
                         for k in ("category", "subcategory", "topic")]
                category = " > ".join(p for p in parts if p)
        except yaml.YAMLError:
            pass
    else:
        title_match = re.search(r'\*\*Title:\*\*\s*(.+)', content)
        if title_match:
            title = title_match.group(1).strip()

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
        "category": category,
        "excerpt": excerpt,
        "existing_tags": existing_tags,
    }


# ==============================================================================
# --- AI CALLS ---
# ==============================================================================

def call_ai(prompt, purpose="tagging", json_mode=False):
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
# --- TAGGING ---
# ==============================================================================

RETAG_PROMPT_TEMPLATE = """You are assigning tags to YouTube videos to make them searchable.

RULES:
- Assign 3-5 tags per video
- Tags MUST be lowercase and hyphenated (e.g., "character-creation", "budget-tips", "ai-tools")
- Use general, reusable concepts — NOT video-specific phrases or proper nouns
- Do NOT repeat the category name as a tag
- Prefer terms that would help someone search across different categories

VIDEOS TO TAG:
{video_list}

Respond with a JSON array. Each entry must have "title" and "tags" keys.

Example:
[
  {{"title": "Video Title 1", "tags": ["worldbuilding", "session-prep", "dm-tips"]}},
  {{"title": "Video Title 2", "tags": ["budget-investing", "compound-interest", "financial-literacy"]}}
]

Only output the JSON array, no other text."""


def create_batches(items, batch_size):
    """Splits items into batches."""
    return [items[i:i + batch_size] for i in range(0, len(items), batch_size)]


def format_batch_for_prompt(batch):
    """Formats a batch of video infos for the tagging prompt."""
    lines = []
    for i, item in enumerate(batch, 1):
        lines.append(f"{i}. Title: {item['title']}")
        if item.get('category'):
            lines.append(f"   Category: {item['category']}")
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
    for item in batch:
        if title_lower in item['title'].lower() or item['title'].lower() in title_lower:
            return item
    return None


# ==============================================================================
# --- FRONTMATTER UPDATE ---
# ==============================================================================

def update_frontmatter_tags(filepath, tags):
    """Updates the 'tags' field in the YAML frontmatter of a summary file."""
    filepath = Path(filepath)
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  Error reading {filepath.name}: {e}")
        return False

    yaml_match = re.match(r'^(---\n)(.*?)(\n---)', content, re.DOTALL)
    if not yaml_match:
        print(f"  No YAML frontmatter in {filepath.name}. Skipping.")
        return False

    try:
        fm = yaml.safe_load(yaml_match.group(2))
        if fm is None:
            fm = {}
    except yaml.YAMLError as e:
        print(f"  Error parsing YAML in {filepath.name}: {e}")
        return False

    # Normalize and set tags
    fm["tags"] = [normalize_tag(t) for t in tags if normalize_tag(t)]

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
    parser = argparse.ArgumentParser(description="Assign tags to videos using AI.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without API calls or file changes")
    parser.add_argument("--limit", type=int, default=None, help="Only process first N untagged files")
    parser.add_argument("--batch-size", type=int, default=40, help="Videos per API batch (default: 40)")
    parser.add_argument("--retag", action="store_true", help="Re-tag all videos, even already tagged ones")
    args = parser.parse_args()

    print("=" * 60)
    print("Video Retagging")
    print(f"AI Provider: {config.AI_PROVIDER.upper()}")
    print(f"Summaries Dir: {config.SUMMARIES_DIR}")
    print("=" * 60)

    # Scan files
    files = scan_untagged_files(config.SUMMARIES_DIR, limit=args.limit, retag=args.retag)
    if not files:
        print("No files to tag. Done.")
        sys.exit(0)

    if args.dry_run:
        print(f"\n--- DRY RUN ---")
        print(f"Would tag {len(files)} files.")
        print(f"\nFirst 5 files:")
        for f in files[:5]:
            print(f"  - {f['title']}")
            if f.get('category'):
                print(f"    Category: {f['category']}")
        print("\n--- DRY RUN complete. No API calls or file changes made. ---")
        return

    # Process in batches
    batches = create_batches(files, args.batch_size)
    print(f"\nSplit {len(files)} videos into {len(batches)} batches of ~{args.batch_size}.")

    total_tagged = 0
    total_failed = 0

    for i, batch in enumerate(batches, 1):
        print(f"\nBatch {i}/{len(batches)} ({len(batch)} videos)...")
        video_list = format_batch_for_prompt(batch)
        prompt = RETAG_PROMPT_TEMPLATE.format(video_list=video_list)

        response = call_ai(prompt, f"batch {i} tagging", json_mode=True)
        if not response:
            print(f"  Warning: Batch {i} failed. Skipping.")
            total_failed += len(batch)
            continue

        parsed = parse_batch_response(response)
        print(f"  Got {len(parsed)} tag assignments.")

        for item in parsed:
            title = item.get("title", "")
            tags = item.get("tags", [])
            matched_file = match_title_to_file(title, batch)

            if not matched_file:
                print(f"  Could not match: '{title[:60]}...'")
                total_failed += 1
                continue

            if not tags:
                print(f"  No tags for: '{title[:60]}...'")
                total_failed += 1
                continue

            success = update_frontmatter_tags(matched_file['filepath'], tags)
            if success:
                total_tagged += 1
                tag_str = ", ".join(tags[:5])
                logging.info(f"Tagged '{title}' -> [{tag_str}]")
            else:
                total_failed += 1

        # Rate limiting
        if i < len(batches):
            time.sleep(2)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Tagging complete!")
    print(f"  Tagged:  {total_tagged}")
    print(f"  Failed:  {total_failed}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()

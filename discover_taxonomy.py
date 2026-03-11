"""
Taxonomy Discovery Script
=========================
Reads existing summary files, sends batches to the AI for clustering,
and outputs a unified category taxonomy to categories.txt.

Usage:
    python discover_taxonomy.py                  # Full run
    python discover_taxonomy.py --dry-run        # Preview without API calls
    python discover_taxonomy.py --limit 100      # Only process first 100 files
    python discover_taxonomy.py --batch-size 30  # Smaller batches (default: 50)

Requires: Same .env config as main.py (API keys, AI_PROVIDER, etc.)
"""

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path

import config

# --- Conditional AI imports (same pattern as ai_utils.py) ---
if config.AI_PROVIDER == 'openai':
    import openai
elif config.AI_PROVIDER == 'gemini':
    from google import genai


# ==============================================================================
# --- FILE SCANNING ---
# ==============================================================================

def scan_summary_files(summaries_dir, limit=None):
    """
    Scans the summaries directory for all summary files.
    Returns a list of dicts with extracted info from each file.
    """
    summaries_dir = Path(summaries_dir)
    if not summaries_dir.exists():
        print(f"Error: Summaries directory not found: {summaries_dir}")
        sys.exit(1)

    summary_files = sorted(summaries_dir.rglob("*– Summary.md"))
    print(f"Found {len(summary_files)} summary files.")

    if limit:
        summary_files = summary_files[:limit]
        print(f"Limited to {limit} files.")

    results = []
    for filepath in summary_files:
        info = extract_summary_info(filepath)
        if info:
            results.append(info)

    print(f"Successfully extracted info from {len(results)} files.")
    return results


def extract_summary_info(filepath):
    """
    Extracts key information from a summary file for taxonomy clustering.
    Returns a dict with title, playlist, and a short excerpt.
    """
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception as e:
        logging.warning(f"Could not read {filepath}: {e}")
        return None

    # Determine playlist from folder name
    playlist = filepath.parent.name

    # Try to extract title from YAML frontmatter or inline markdown
    title = "Unknown"
    # Check for YAML frontmatter
    yaml_match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if yaml_match:
        for line in yaml_match.group(1).splitlines():
            if line.startswith("title:"):
                title = line.split(":", 1)[1].strip().strip('"\'')
                break
    else:
        # Check for old inline format: **Title:** ...
        title_match = re.search(r'\*\*Title:\*\*\s*(.+)', content)
        if title_match:
            title = title_match.group(1).strip()

    # Extract the AI Summary section (first ~300 words for context)
    summary_match = re.search(r'## AI Summary\s*\n+(.*?)(?=\n## |\Z)', content, re.DOTALL)
    excerpt = ""
    if summary_match:
        full_summary = summary_match.group(1).strip()
        # Take first ~300 words
        words = full_summary.split()
        excerpt = " ".join(words[:300])

    if not excerpt:
        return None

    return {
        "title": title,
        "playlist": playlist,
        "excerpt": excerpt,
    }


# ==============================================================================
# --- AI CALLS ---
# ==============================================================================

def call_ai(prompt, purpose="taxonomy", json_mode=False):
    """Sends a prompt to the configured AI provider and returns the response."""
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
# --- TAXONOMY DISCOVERY ---
# ==============================================================================

BATCH_PROMPT_TEMPLATE = """Analyze these video summaries and suggest hierarchical categories for each one.

For each video, assign:
1. A hierarchical CATEGORY using " > " as separator (e.g. "Gaming > MTG > Deckbuilding", "Gaming > D&D > DM Tips", "Finance > ETFs")
2. Be SPECIFIC — use 2-3 levels of hierarchy to capture what the video is actually about
3. For niche topics (MTG, D&D, specific games, etc.), include the specific sub-topic (e.g. "Commander", "Draft", "Character Creation", "DM Tips")
4. Use consistent naming — e.g. always "MTG" not "Magic: The Gathering", always "D&D" not "Dungeons & Dragons"

Videos to categorize:

{video_list}

Respond with a JSON array. Each entry should have "title" and "category" keys. Example:
[
  {{"title": "Video Title 1", "category": "Science > Physics"}},
  {{"title": "Video Title 2", "category": "Gaming > MTG"}}
]

Only output the JSON array, no other text."""


AGGREGATION_PROMPT_TEMPLATE = """You are designing a category taxonomy for a YouTube video library of {total_videos} videos.

Below you see raw category labels that were auto-generated per video, with their occurrence counts.
Your job is NOT to simply deduplicate these labels. Instead, analyze them to understand what content actually exists, and then design a taxonomy that would be genuinely useful for organizing and browsing these videos.

Think about it like this: If someone were browsing this video library, what categories and sub-categories would help them find what they're looking for?

Guidelines:
- Use up to 3 levels of hierarchy (Main > Sub > Detail), using " > " as separator
- Where a topic area has enough content to warrant it, create specific sub-categories that reflect real content differences
  For example, if there are many MTG videos, don't just say "Gaming > Card Games" — break it down into what types of MTG content exist (deckbuilding, draft, commander, gameplay, etc.)
- Likewise for D&D: distinguish DM tips, character creation, combat tactics, worldbuilding, etc.
- For smaller topic areas, broader categories are fine
- Use English for category names
- Use short, consistent names (e.g. always "MTG" not "Magic: The Gathering", always "D&D" not "Dungeons & Dragons")
- The taxonomy should feel natural and useful, not mechanical

Raw category data (category: count):
{category_counts}

Output the final taxonomy as a simple list, one category per line. Use " > " for hierarchy.
Only output the category list, no other text."""


def create_batches(summaries, batch_size):
    """Splits summaries into batches."""
    batches = []
    for i in range(0, len(summaries), batch_size):
        batches.append(summaries[i:i + batch_size])
    return batches


def format_batch_for_prompt(batch):
    """Formats a batch of summaries for the clustering prompt."""
    lines = []
    for i, item in enumerate(batch, 1):
        lines.append(f"{i}. Title: {item['title']}")
        lines.append(f"   Playlist: {item['playlist']}")
        # Shorten excerpt to ~100 words per video to stay within token limits
        words = item['excerpt'].split()
        short_excerpt = " ".join(words[:100])
        lines.append(f"   Summary: {short_excerpt}")
        lines.append("")
    return "\n".join(lines)


def parse_batch_response(response):
    """Parses the JSON array from the AI response, recovering truncated JSON."""
    if not response:
        return []

    # Strip markdown code fences (```json ... ``` or ``` ... ```)
    cleaned = re.sub(r'```(?:json)?\s*\n?', '', response)
    cleaned = cleaned.replace('```', '')

    # Try to find a complete JSON array first
    json_match = re.search(r'\[.*\]', cleaned, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            return data
        except json.JSONDecodeError:
            pass

    # Fallback: try to recover truncated JSON (response cut off before closing ])
    array_start = cleaned.find('[')
    if array_start == -1:
        print("  Warning: Could not find JSON array in response.")
        print(f"  Response preview: {response[:500]}")
        return []

    truncated = cleaned[array_start:]
    # Find the last complete object (ending with })
    last_brace = truncated.rfind('}')
    if last_brace == -1:
        print("  Warning: No complete JSON objects found in truncated response.")
        return []

    # Take everything up to and including the last complete }, then close the array
    partial = truncated[:last_brace + 1] + ']'
    try:
        data = json.loads(partial)
        print(f"  (Recovered {len(data)} items from truncated response)")
        return data
    except json.JSONDecodeError as e:
        print(f"  Warning: Failed to parse JSON (even with recovery): {e}")
        print(f"  Response preview: {response[:500]}")
        return []


def run_discovery(summaries, batch_size, dry_run=False):
    """
    Main discovery workflow:
    1. Send batches to AI for categorization
    2. Collect all category assignments
    3. Aggregate into a clean taxonomy
    """
    batches = create_batches(summaries, batch_size)
    print(f"\nSplit {len(summaries)} videos into {len(batches)} batches of ~{batch_size}.")

    if dry_run:
        print("\n--- DRY RUN: Showing first batch prompt ---\n")
        if batches:
            video_list = format_batch_for_prompt(batches[0])
            prompt = BATCH_PROMPT_TEMPLATE.format(video_list=video_list)
            print(prompt[:2000])
            print(f"\n... (prompt truncated, full length: {len(prompt)} chars)")
        print("\n--- DRY RUN complete. No API calls made. ---")
        return None

    # Step 1: Categorize each batch
    all_categories = []
    for i, batch in enumerate(batches, 1):
        print(f"\nProcessing batch {i}/{len(batches)} ({len(batch)} videos)...")
        video_list = format_batch_for_prompt(batch)
        prompt = BATCH_PROMPT_TEMPLATE.format(video_list=video_list)

        response = call_ai(prompt, f"batch {i} categorization", json_mode=True)
        if response:
            print(f"  Response preview: {response[:300]}")
            parsed = parse_batch_response(response)
            all_categories.extend(parsed)
            print(f"  Got {len(parsed)} category assignments.")
        else:
            print(f"  Warning: Batch {i} failed. Skipping.")

        # Rate limiting between batches
        if i < len(batches):
            time.sleep(2)

    if not all_categories:
        print("\nError: No categories were extracted. Check your API configuration.")
        return None

    print(f"\nCollected {len(all_categories)} total category assignments.")

    # Step 2: Count category frequencies
    category_counts = {}
    for item in all_categories:
        cat = item.get("category", "Unknown")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    # Sort by frequency
    sorted_cats = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
    print(f"\nFound {len(sorted_cats)} unique categories. Top 20:")
    for cat, count in sorted_cats[:20]:
        print(f"  {count:4d}x  {cat}")

    # Save raw categories for reference
    raw_output_path = config.BASE_DIR / "taxonomy_raw_categories.json"
    with open(raw_output_path, "w", encoding="utf-8") as f:
        json.dump(all_categories, f, ensure_ascii=False, indent=2)
    print(f"\nRaw categories saved to: {raw_output_path}")

    # Step 3: Aggregate into clean taxonomy
    print("\nAggregating into clean taxonomy...")
    category_counts_text = "\n".join(f"{cat}: {count}" for cat, count in sorted_cats)
    agg_prompt = AGGREGATION_PROMPT_TEMPLATE.format(
        total_videos=len(all_categories),
        category_counts=category_counts_text
    )

    taxonomy = call_ai(agg_prompt, "taxonomy aggregation")
    if not taxonomy:
        print("Error: Aggregation failed. Using raw categories as fallback.")
        taxonomy = "\n".join(cat for cat, _ in sorted_cats)

    return taxonomy


# ==============================================================================
# --- MAIN ---
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Discover taxonomy from existing video summaries.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making API calls")
    parser.add_argument("--limit", type=int, default=None, help="Only process first N files")
    parser.add_argument("--batch-size", type=int, default=50, help="Videos per API batch (default: 50)")
    args = parser.parse_args()

    print("=" * 60)
    print("Taxonomy Discovery")
    print(f"AI Provider: {config.AI_PROVIDER.upper()}")
    print(f"Summaries Dir: {config.SUMMARIES_DIR}")
    print("=" * 60)

    # Step 1: Scan files
    summaries = scan_summary_files(config.SUMMARIES_DIR, limit=args.limit)
    if not summaries:
        print("No summary files found. Nothing to do.")
        sys.exit(0)

    # Step 2: Run discovery
    taxonomy = run_discovery(summaries, args.batch_size, dry_run=args.dry_run)

    if taxonomy is None:
        sys.exit(0)

    # Step 3: Save taxonomy
    output_path = config.BASE_DIR / "categories.txt"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(taxonomy)

    print(f"\n{'=' * 60}")
    print(f"Taxonomy saved to: {output_path}")
    print(f"{'=' * 60}")
    print(f"\nContent:\n")
    print(taxonomy)
    print(f"\nYou can edit {output_path} to adjust categories before using them.")


if __name__ == "__main__":
    main()

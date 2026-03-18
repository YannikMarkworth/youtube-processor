"""
Taxonomy & Tag Analysis Script
===============================
Analyzes the current category taxonomy and tag distribution across all
video summaries. Produces a detailed report to help evaluate, revise,
and improve the category hierarchy.

Usage:
    python analyze_taxonomy.py                  # Full analysis
    python analyze_taxonomy.py --top 30         # Show top 30 items per section
    python analyze_taxonomy.py --output-dir .   # Save reports elsewhere

Requires: Same .env config as main.py (only for file paths, no API keys needed).
"""

import argparse
import json
import re
import statistics
from collections import Counter
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

import yaml

import config


# ==============================================================================
# --- HELPERS (inlined from browse.py and classify_videos.py to avoid
#     heavy imports like Flask or conditional AI SDK imports) ---
# ==============================================================================

def parse_frontmatter(filepath):
    """Reads a summary .md file and returns (frontmatter_dict, body_text).
    Origin: browse.py:35-52"""
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return None, None

    match = re.match(r"^---\n(.*?)\n---\n?(.*)", content, re.DOTALL)
    if not match:
        return None, content

    try:
        fm = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        fm = {}

    body = match.group(2).strip()
    return fm or {}, body


def load_taxonomy(taxonomy_path):
    """Parses categories.txt (indent-based) into a flat list of category paths.
    Origin: classify_videos.py:85-115"""
    taxonomy_path = Path(taxonomy_path)
    if not taxonomy_path.exists():
        print(f"Warning: Taxonomy file not found: {taxonomy_path}")
        return []

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


# ==============================================================================
# --- DATA LOADING ---
# ==============================================================================

def load_all_video_data(summaries_dir):
    """Scans all summary files and extracts frontmatter data."""
    summaries_dir = Path(summaries_dir)
    if not summaries_dir.exists():
        print(f"Error: Summaries directory not found: {summaries_dir}")
        return []

    videos = []
    for filepath in sorted(summaries_dir.rglob("*– Summary.md")):
        fm, _ = parse_frontmatter(filepath)
        if fm is None:
            continue

        # Coerce tags to list
        tags = fm.get("tags", [])
        if tags is None:
            tags = []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        # Reconstruct full category path from separate fields
        cat = str(fm.get("category", "") or "").strip()
        subcat = str(fm.get("subcategory", "") or "").strip()
        topic = str(fm.get("topic", "") or "").strip()

        parts = [p for p in [cat, subcat, topic] if p]
        full_path = " > ".join(parts) if parts else ""

        videos.append({
            "filepath": str(filepath),
            "filename": filepath.name,
            "title": fm.get("title", filepath.stem),
            "channel": fm.get("channel", "Unknown"),
            "playlist": fm.get("playlist", filepath.parent.name),
            "category": cat,
            "subcategory": subcat,
            "topic": topic,
            "full_category_path": full_path,
            "tags": tags,
        })

    return videos


def build_taxonomy_tree(taxonomy_paths):
    """Builds a nested dict from flat taxonomy paths for tree display."""
    tree = {}
    for path in taxonomy_paths:
        parts = [p.strip() for p in path.split(" > ")]
        node = tree
        for part in parts:
            if part not in node:
                node[part] = {}
            node = node[part]
    return tree


# ==============================================================================
# --- CATEGORY ANALYSIS ---
# ==============================================================================

def analyze_category_distribution(videos, taxonomy_paths):
    """Analyzes how videos are distributed across categories."""
    taxonomy_set = set(taxonomy_paths)

    counts_by_full_path = Counter()
    counts_by_category = Counter()
    counts_by_subcategory = Counter()
    counts_by_topic = Counter()
    uncategorized = []
    inconsistent = []

    for v in videos:
        fp = v["full_category_path"]
        if not fp:
            uncategorized.append(v)
            continue

        counts_by_full_path[fp] += 1

        if v["category"]:
            counts_by_category[v["category"]] += 1
        if v["subcategory"]:
            sub_path = f"{v['category']} > {v['subcategory']}"
            counts_by_subcategory[sub_path] += 1
        if v["topic"]:
            topic_path = fp
            counts_by_topic[topic_path] += 1

        # Check if the full path matches any taxonomy entry
        if fp not in taxonomy_set:
            # Also check partial paths (category only, category > subcategory)
            cat_only = v["category"]
            cat_sub = f"{v['category']} > {v['subcategory']}" if v["subcategory"] else ""
            if fp not in taxonomy_set and cat_sub not in taxonomy_set and cat_only not in taxonomy_set:
                inconsistent.append(v)

    # Find unused taxonomy paths
    unused = [p for p in taxonomy_paths if counts_by_full_path.get(p, 0) == 0]

    return {
        "counts_by_full_path": counts_by_full_path,
        "counts_by_category": counts_by_category,
        "counts_by_subcategory": counts_by_subcategory,
        "counts_by_topic": counts_by_topic,
        "uncategorized": uncategorized,
        "inconsistent": inconsistent,
        "unused_paths": unused,
    }


def analyze_category_balance(counts_by_full_path):
    """Computes balance statistics for category distribution."""
    if not counts_by_full_path:
        return {"total": 0, "mean": 0, "median": 0, "stdev": 0,
                "over_represented": [], "under_represented": []}

    values = list(counts_by_full_path.values())
    total = sum(values)
    mean = statistics.mean(values)
    median = statistics.median(values)
    stdev = statistics.stdev(values) if len(values) > 1 else 0

    over_threshold = mean + 1.5 * stdev
    under_threshold = max(1, mean - stdev)

    over = [(cat, count) for cat, count in counts_by_full_path.most_common()
            if count > over_threshold]
    under = [(cat, count) for cat, count in counts_by_full_path.most_common()
             if 0 < count < under_threshold]

    return {
        "total_videos": total,
        "categories_with_videos": len(values),
        "mean": round(mean, 1),
        "median": median,
        "stdev": round(stdev, 1),
        "over_represented": over,
        "under_represented": under,
    }


# ==============================================================================
# --- TAG ANALYSIS ---
# ==============================================================================

def analyze_tag_frequency(videos):
    """Analyzes tag frequency and per-video distribution."""
    tag_counts = Counter()
    tags_per_video = []

    for v in videos:
        tags = v["tags"]
        tags_per_video.append(len(tags))
        for tag in tags:
            tag_counts[str(tag).lower()] += 1

    # Per-video stats
    if tags_per_video:
        stats = {
            "min": min(tags_per_video),
            "max": max(tags_per_video),
            "mean": round(statistics.mean(tags_per_video), 1),
            "median": statistics.median(tags_per_video),
        }
    else:
        stats = {"min": 0, "max": 0, "mean": 0, "median": 0}

    # Histogram buckets
    histogram = Counter()
    for count in tags_per_video:
        bucket = str(count) if count <= 6 else "7+"
        histogram[bucket] += 1

    # Singletons
    singletons = sorted([tag for tag, count in tag_counts.items() if count == 1])

    return {
        "tag_counts": tag_counts,
        "tags_per_video_stats": stats,
        "tags_per_video_histogram": histogram,
        "singletons": singletons,
        "total_unique_tags": len(tag_counts),
        "total_tag_usages": sum(tag_counts.values()),
    }


def find_similar_tags(tag_counts, threshold=0.80):
    """Finds near-duplicate tags using trigram pre-filtering + SequenceMatcher."""
    tags = list(tag_counts.keys())
    if len(tags) < 2:
        return []

    # Build trigram index for pre-filtering
    trigram_index = {}
    for tag in tags:
        for i in range(len(tag) - 2):
            tri = tag[i:i + 3]
            if tri not in trigram_index:
                trigram_index[tri] = set()
            trigram_index[tri].add(tag)

    seen = set()
    similar_pairs = []

    for tag in tags:
        # Gather candidates that share at least one trigram
        candidates = set()
        for i in range(len(tag) - 2):
            tri = tag[i:i + 3]
            if tri in trigram_index:
                candidates.update(trigram_index[tri])
        candidates.discard(tag)

        for other in candidates:
            pair = tuple(sorted([tag, other]))
            if pair in seen:
                continue
            seen.add(pair)

            ratio = SequenceMatcher(None, tag, other).ratio()
            if ratio >= threshold:
                similar_pairs.append({
                    "tag_a": pair[0],
                    "tag_b": pair[1],
                    "similarity": round(ratio, 2),
                    "count_a": tag_counts[pair[0]],
                    "count_b": tag_counts[pair[1]],
                })

    similar_pairs.sort(key=lambda x: x["similarity"], reverse=True)
    return similar_pairs


# ==============================================================================
# --- CROSS-ANALYSIS ---
# ==============================================================================

def analyze_tag_category_correlation(videos, top_n=20):
    """Shows which tags appear most in which categories and vice versa."""
    # Top tags → categories
    tag_counts = Counter()
    tag_to_cats = {}
    cat_to_tags = {}

    for v in videos:
        cat = v["category"] or "(uncategorized)"
        for tag in v["tags"]:
            tag_lower = str(tag).lower()
            tag_counts[tag_lower] += 1

            if tag_lower not in tag_to_cats:
                tag_to_cats[tag_lower] = Counter()
            tag_to_cats[tag_lower][cat] += 1

            if cat not in cat_to_tags:
                cat_to_tags[cat] = Counter()
            cat_to_tags[cat][tag_lower] += 1

    top_tags = [t for t, _ in tag_counts.most_common(top_n)]
    top_tag_cats = {tag: tag_to_cats[tag].most_common(5) for tag in top_tags if tag in tag_to_cats}

    top_cats = Counter()
    for v in videos:
        if v["category"]:
            top_cats[v["category"]] += 1
    top_cat_names = [c for c, _ in top_cats.most_common(top_n)]
    top_cat_tags = {cat: cat_to_tags[cat].most_common(10) for cat in top_cat_names if cat in cat_to_tags}

    return {
        "top_tag_categories": top_tag_cats,
        "top_category_tags": top_cat_tags,
    }


def find_split_candidates(videos, min_videos=10, min_tag_diversity=8):
    """Finds categories that might need splitting (many videos + diverse tags)."""
    cat_data = {}
    for v in videos:
        # Use subcategory level (category > subcategory) for split analysis
        if v["subcategory"]:
            key = f"{v['category']} > {v['subcategory']}"
        elif v["category"]:
            key = v["category"]
        else:
            continue

        if key not in cat_data:
            cat_data[key] = {"count": 0, "tags": set()}
        cat_data[key]["count"] += 1
        for tag in v["tags"]:
            cat_data[key]["tags"].add(str(tag).lower())

    candidates = []
    for cat, data in cat_data.items():
        if data["count"] >= min_videos and len(data["tags"]) >= min_tag_diversity:
            candidates.append({
                "category": cat,
                "video_count": data["count"],
                "unique_tags": len(data["tags"]),
                "top_tags": Counter(
                    str(tag).lower()
                    for v in videos
                    if (f"{v['category']} > {v['subcategory']}" if v["subcategory"] else v["category"]) == cat
                    for tag in v["tags"]
                ).most_common(10),
            })

    candidates.sort(key=lambda x: x["unique_tags"], reverse=True)
    return candidates


def suggest_new_subcategories(videos, min_frequency=3):
    """Finds frequent tags within categories that could become subcategories."""
    # Group tags by category (top-level only for categories without deep nesting)
    cat_tags = {}
    for v in videos:
        cat = v["category"]
        if not cat:
            continue

        # Check if this video has a topic (deepest level) — if not, the category
        # could benefit from more specific subcategories
        if not v["topic"]:
            key = v["full_category_path"]
            if key not in cat_tags:
                cat_tags[key] = Counter()
            for tag in v["tags"]:
                cat_tags[key][str(tag).lower()] += 1

    suggestions = []
    for cat_path, tag_counter in cat_tags.items():
        frequent = [(tag, count) for tag, count in tag_counter.most_common()
                     if count >= min_frequency]
        if frequent:
            suggestions.append({
                "category": cat_path,
                "suggested_tags": frequent[:10],
            })

    suggestions.sort(key=lambda x: len(x["suggested_tags"]), reverse=True)
    return suggestions


# ==============================================================================
# --- REPORT FORMATTING ---
# ==============================================================================

def format_report(videos, taxonomy_paths, taxonomy_tree, cat_dist, cat_balance,
                  tag_freq, similar_tags, tag_cat_corr, split_candidates,
                  new_subcats, top_n):
    """Formats the complete analysis report as a string."""
    lines = []

    def section(num, title):
        lines.append("")
        lines.append(f"{'=' * 70}")
        lines.append(f"  {num}. {title}")
        lines.append(f"{'=' * 70}")
        lines.append("")

    def hr():
        lines.append(f"  {'-' * 66}")

    # Header
    lines.append("=" * 70)
    lines.append("  TAXONOMY & TAG ANALYSIS REPORT")
    lines.append(f"  Generated: {date.today().isoformat()}")
    lines.append(f"  Videos analyzed: {len(videos)}  |  Taxonomy paths: {len(taxonomy_paths)}")
    lines.append("=" * 70)

    # --- 1. Category Tree with Counts ---
    section(1, "CATEGORY TREE WITH COUNTS")

    # Count videos at each node (including children)
    path_direct_counts = cat_dist["counts_by_full_path"]

    def print_tree(tree, prefix="", depth=0):
        for name in tree:
            # Build the full path for this node
            parts = prefix.split(" > ") if prefix else []
            parts.append(name)
            full_path = " > ".join(parts)

            direct = path_direct_counts.get(full_path, 0)

            # Sum all descendant counts
            total = sum(c for p, c in path_direct_counts.items()
                        if p == full_path or p.startswith(full_path + " > "))

            indent = "  " * depth
            count_str = f"[{total}]" if total > 0 else "[0]"
            direct_str = f" (direct: {direct})" if tree[name] and direct > 0 else ""
            line = f"  {indent}{name}"
            padding = max(1, 60 - len(line))
            lines.append(f"{line}{' ' * padding}{count_str:>6}{direct_str}")

            if tree[name]:
                print_tree(tree[name], full_path, depth + 1)

    print_tree(taxonomy_tree)

    # --- 2. Uncategorized Videos ---
    section(2, f"UNCATEGORIZED VIDEOS ({len(cat_dist['uncategorized'])})")
    if cat_dist["uncategorized"]:
        for v in cat_dist["uncategorized"][:top_n]:
            lines.append(f"  - \"{v['title'][:70]}\"")
            lines.append(f"    File: {Path(v['filepath']).name}")
        if len(cat_dist["uncategorized"]) > top_n:
            lines.append(f"  ... and {len(cat_dist['uncategorized']) - top_n} more")
    else:
        lines.append("  None — all videos are categorized.")

    # --- 3. Inconsistent Categories ---
    section(3, f"INCONSISTENT CATEGORIES ({len(cat_dist['inconsistent'])})")
    lines.append("  Videos with categories not matching any entry in categories.txt:")
    lines.append("")
    if cat_dist["inconsistent"]:
        seen_paths = Counter()
        for v in cat_dist["inconsistent"]:
            seen_paths[v["full_category_path"]] += 1
        for path, count in seen_paths.most_common():
            lines.append(f"  {count:4d}x  \"{path}\"")
    else:
        lines.append("  None — all categories match the taxonomy.")

    # --- 4. Unused Categories ---
    section(4, f"UNUSED CATEGORIES ({len(cat_dist['unused_paths'])})")
    lines.append("  Categories defined in categories.txt with 0 videos:")
    lines.append("")
    if cat_dist["unused_paths"]:
        for p in cat_dist["unused_paths"]:
            lines.append(f"  - {p}")
    else:
        lines.append("  None — all categories have at least one video.")

    # --- 5. Category Balance ---
    section(5, "CATEGORY BALANCE")
    b = cat_balance
    lines.append(f"  Total videos (categorized): {b['total_videos']}")
    lines.append(f"  Categories with videos:     {b['categories_with_videos']}")
    lines.append(f"  Mean:   {b['mean']} videos/category")
    lines.append(f"  Median: {b['median']}")
    lines.append(f"  Std Dev: {b['stdev']}")
    lines.append("")

    if b["over_represented"]:
        lines.append("  Over-represented (> mean + 1.5σ):")
        hr()
        for cat, count in b["over_represented"]:
            lines.append(f"  {count:4d}  {cat}")
        lines.append("")

    if b["under_represented"]:
        lines.append("  Under-represented (< mean - 1σ, excl. empty):")
        hr()
        for cat, count in b["under_represented"][:top_n]:
            lines.append(f"  {count:4d}  {cat}")

    # --- 6. Tag Frequency ---
    section(6, f"TAG FREQUENCY (Top {top_n})")
    lines.append(f"  Total unique tags: {tag_freq['total_unique_tags']}")
    lines.append(f"  Total tag usages:  {tag_freq['total_tag_usages']}")
    lines.append("")

    max_count = tag_freq["tag_counts"].most_common(1)[0][1] if tag_freq["tag_counts"] else 1
    for tag, count in tag_freq["tag_counts"].most_common(top_n):
        bar_len = int(30 * count / max_count)
        bar = "█" * bar_len
        lines.append(f"  {count:4d}  {tag:<35s} {bar}")

    # --- 7. Tags per Video ---
    section(7, "TAGS PER VIDEO DISTRIBUTION")
    s = tag_freq["tags_per_video_stats"]
    lines.append(f"  Min: {s['min']}  Max: {s['max']}  Mean: {s['mean']}  Median: {s['median']}")
    lines.append("")

    hist = tag_freq["tags_per_video_histogram"]
    max_hist = max(hist.values()) if hist else 1
    for bucket in ["0", "1", "2", "3", "4", "5", "6", "7+"]:
        count = hist.get(bucket, 0)
        bar_len = int(40 * count / max_hist) if max_hist > 0 else 0
        bar = "█" * bar_len
        lines.append(f"  {bucket:>3s} tags: {count:4d} videos  {bar}")

    # --- 8. Singleton Tags ---
    section(8, f"SINGLETON TAGS ({len(tag_freq['singletons'])} total)")
    lines.append("  Tags that appear only once (consolidation candidates):")
    lines.append("")
    singletons = tag_freq["singletons"]
    if singletons:
        # Display in wrapped lines
        line_buf = "  "
        for tag in singletons:
            if len(line_buf) + len(tag) + 2 > 70:
                lines.append(line_buf)
                line_buf = "  "
            line_buf += tag + ", "
        if line_buf.strip():
            lines.append(line_buf.rstrip(", "))
    else:
        lines.append("  None.")

    # --- 9. Similar/Duplicate Tags ---
    section(9, f"SIMILAR/DUPLICATE TAGS ({len(similar_tags)} pairs)")
    if similar_tags:
        for pair in similar_tags[:top_n]:
            lines.append(
                f"  \"{pair['tag_a']}\" ({pair['count_a']}x) "
                f"<-> \"{pair['tag_b']}\" ({pair['count_b']}x)  "
                f"[similarity: {pair['similarity']}]"
            )
        if len(similar_tags) > top_n:
            lines.append(f"  ... and {len(similar_tags) - top_n} more pairs")
    else:
        lines.append("  No near-duplicate tags found.")

    # --- 10. Tag-Category Correlation ---
    section(10, f"TAG-CATEGORY CORRELATION (Top {top_n} tags)")
    for tag, cats in list(tag_cat_corr["top_tag_categories"].items())[:top_n]:
        total = sum(c for _, c in cats)
        lines.append(f"  Tag: \"{tag}\" ({total} total)")
        for cat, count in cats:
            lines.append(f"    {count:4d}  {cat}")
        lines.append("")

    # --- 11. Split Candidates ---
    section(11, f"CATEGORIES THAT MAY NEED SPLITTING ({len(split_candidates)})")
    lines.append("  Categories with many videos AND high tag diversity:")
    lines.append("")
    if split_candidates:
        lines.append(f"  {'Category':<45s} {'Videos':>7s} {'Tags':>6s}")
        hr()
        for c in split_candidates[:top_n]:
            lines.append(f"  {c['category']:<45s} {c['video_count']:>7d} {c['unique_tags']:>6d}")
            top_tags_str = ", ".join(f"{t}({n})" for t, n in c["top_tags"][:5])
            lines.append(f"    Top tags: {top_tags_str}")
    else:
        lines.append("  None found.")

    # --- 12. Potential New Subcategories ---
    section(12, f"POTENTIAL NEW SUBCATEGORIES ({len(new_subcats)} categories)")
    lines.append("  Frequent tags in categories without topic-level classification:")
    lines.append("")
    if new_subcats:
        for s in new_subcats[:top_n]:
            lines.append(f"  Under \"{s['category']}\":")
            for tag, count in s["suggested_tags"]:
                lines.append(f"    {count:4d}x  \"{tag}\"")
            lines.append("")
    else:
        lines.append("  No suggestions — all videos have full 3-level categorization.")

    lines.append("")
    lines.append("=" * 70)
    lines.append("  END OF REPORT")
    lines.append("=" * 70)

    return "\n".join(lines)


def build_json_data(videos, cat_dist, cat_balance, tag_freq, similar_tags,
                    tag_cat_corr, split_candidates, new_subcats):
    """Builds a JSON-serializable dict of all analysis results."""
    return {
        "summary": {
            "total_videos": len(videos),
            "categorized": len(videos) - len(cat_dist["uncategorized"]),
            "uncategorized": len(cat_dist["uncategorized"]),
            "inconsistent": len(cat_dist["inconsistent"]),
            "unused_categories": len(cat_dist["unused_paths"]),
            "total_unique_tags": tag_freq["total_unique_tags"],
            "singleton_tags": len(tag_freq["singletons"]),
            "similar_tag_pairs": len(similar_tags),
        },
        "category_counts": dict(cat_dist["counts_by_full_path"].most_common()),
        "category_balance": cat_balance,
        "uncategorized_videos": [
            {"title": v["title"], "file": Path(v["filepath"]).name}
            for v in cat_dist["uncategorized"]
        ],
        "inconsistent_categories": dict(
            Counter(v["full_category_path"] for v in cat_dist["inconsistent"]).most_common()
        ),
        "unused_categories": cat_dist["unused_paths"],
        "tag_frequency": dict(tag_freq["tag_counts"].most_common()),
        "tags_per_video": tag_freq["tags_per_video_stats"],
        "singleton_tags": tag_freq["singletons"],
        "similar_tags": similar_tags,
        "split_candidates": [
            {"category": c["category"], "videos": c["video_count"], "unique_tags": c["unique_tags"]}
            for c in split_candidates
        ],
        "new_subcategory_suggestions": [
            {"category": s["category"], "tags": [{"tag": t, "count": c} for t, c in s["suggested_tags"]]}
            for s in new_subcats
        ],
    }


# ==============================================================================
# --- MAIN ---
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Analyze taxonomy coverage and tag distribution across video summaries."
    )
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Directory for report files (default: project root)")
    parser.add_argument("--top", type=int, default=20,
                        help="Number of top items to show per section (default: 20)")
    args = parser.parse_args()

    output_dir = args.output_dir or config.BASE_DIR

    # Load data
    print("Loading taxonomy...")
    taxonomy_path = config.BASE_DIR / "categories.txt"
    taxonomy_paths = load_taxonomy(taxonomy_path)
    taxonomy_tree = build_taxonomy_tree(taxonomy_paths)
    print(f"  {len(taxonomy_paths)} category paths loaded.")

    print("Loading video summaries...")
    videos = load_all_video_data(config.SUMMARIES_DIR)
    print(f"  {len(videos)} videos loaded.")

    if not videos:
        print("No videos found. Nothing to analyze.")
        return

    # Run analyses
    print("Analyzing categories...")
    cat_dist = analyze_category_distribution(videos, taxonomy_paths)

    print("Analyzing category balance...")
    cat_balance = analyze_category_balance(cat_dist["counts_by_full_path"])

    print("Analyzing tags...")
    tag_freq = analyze_tag_frequency(videos)

    print("Finding similar tags...")
    similar = find_similar_tags(tag_freq["tag_counts"])

    print("Analyzing tag-category correlation...")
    tag_cat_corr = analyze_tag_category_correlation(videos, args.top)

    print("Finding split candidates...")
    splits = find_split_candidates(videos)

    print("Suggesting new subcategories...")
    new_subcats = suggest_new_subcategories(videos)

    # Format report
    print("Generating report...\n")
    report = format_report(
        videos, taxonomy_paths, taxonomy_tree, cat_dist, cat_balance,
        tag_freq, similar, tag_cat_corr, splits, new_subcats, args.top
    )
    print(report)

    # Save report
    report_path = output_dir / "taxonomy_analysis_report.txt"
    report_path.write_text(report, encoding="utf-8")
    print(f"\nReport saved to: {report_path}")

    # Save JSON data
    json_path = output_dir / "taxonomy_analysis_data.json"
    json_data = build_json_data(
        videos, cat_dist, cat_balance, tag_freq, similar,
        tag_cat_corr, splits, new_subcats
    )
    json_path.write_text(json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"JSON data saved to: {json_path}")


if __name__ == "__main__":
    main()

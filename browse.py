"""
Browse – Local web interface for YouTube Processor summaries.
=============================================================
Start with:  python browse.py
Then open:   http://localhost:5000

Uses the same config.py paths as the main processor.
"""

import json
import os
import random
import re
import time
import yaml
import markdown
from collections import Counter
from pathlib import Path
from flask import Flask, render_template, request, jsonify
from markupsafe import Markup

import config

app = Flask(__name__)

# ==============================================================================
# --- CACHING LAYER ---
# ==============================================================================

_VIDEO_CACHE = []           # In-memory list of video dicts (without body)
_CACHE_MTIME_MAP = {}       # filepath -> mtime for incremental refresh
_LAST_REFRESH = 0           # Timestamp of last refresh
_CACHE_FILE = Path(config.SUMMARIES_DIR) / "_video_index.json"
REFRESH_INTERVAL = 60       # Seconds between incremental refreshes


def parse_frontmatter(filepath):
    """Reads a summary .md file and returns (frontmatter_dict, body_text)."""
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


def _video_dict_from_file(filepath, summaries_dir):
    """Parse a single summary file into a video metadata dict (no body)."""
    fm, _ = parse_frontmatter(filepath)
    if fm is None:
        return None

    rel_path = filepath.relative_to(summaries_dir)
    file_id = str(rel_path).replace("/", "__").replace("\\", "__")

    return {
        "id": file_id,
        "path": str(filepath),
        "playlist_folder": filepath.parent.name,
        "title": fm.get("title", filepath.stem),
        "video_id": fm.get("video_id", ""),
        "video_url": fm.get("video_url", ""),
        "channel": fm.get("channel", "Unknown"),
        "channel_id": fm.get("channel_id", ""),
        "uploaded": str(fm.get("uploaded", "")),
        "duration": fm.get("duration", ""),
        "playlist": fm.get("playlist", filepath.parent.name),
        "category": fm.get("category", ""),
        "subcategory": fm.get("subcategory", ""),
        "topic": fm.get("topic", ""),
        "tags": fm.get("tags", []),
        "tldr": fm.get("tldr", ""),
        "difficulty": fm.get("difficulty", ""),
        "language": fm.get("language", ""),
        "processed_date": str(fm.get("processed_date", "")),
        "mtime": os.path.getmtime(str(filepath)),
    }


def build_index():
    """Full scan: parse all summary files, populate cache and write JSON."""
    global _VIDEO_CACHE, _CACHE_MTIME_MAP, _LAST_REFRESH

    summaries_dir = Path(config.SUMMARIES_DIR)
    if not summaries_dir.exists():
        _VIDEO_CACHE = []
        _CACHE_MTIME_MAP = {}
        _LAST_REFRESH = time.time()
        return

    videos = []
    mtime_map = {}
    files = list(summaries_dir.rglob("*– Summary.md"))
    total = len(files)

    for i, filepath in enumerate(sorted(files)):
        if (i + 1) % 500 == 0:
            print(f"  Indexing... {i + 1}/{total}")
        vid = _video_dict_from_file(filepath, summaries_dir)
        if vid:
            mtime_map[vid["path"]] = vid["mtime"]
            videos.append(vid)

    _VIDEO_CACHE = videos
    _CACHE_MTIME_MAP = mtime_map
    _LAST_REFRESH = time.time()

    # Write JSON cache (without mtime field)
    try:
        cache_data = [{k: v for k, v in vid.items() if k != "mtime"} for vid in videos]
        _CACHE_FILE.write_text(json.dumps(cache_data, ensure_ascii=False, indent=None), encoding="utf-8")
    except Exception as e:
        print(f"Warning: Could not write cache file: {e}")


def load_index_from_cache():
    """Try to load index from JSON cache file. Returns True if successful."""
    global _VIDEO_CACHE, _CACHE_MTIME_MAP, _LAST_REFRESH

    if not _CACHE_FILE.exists():
        return False

    try:
        data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        _VIDEO_CACHE = data
        # Rebuild mtime map from actual files
        _CACHE_MTIME_MAP = {}
        for vid in _VIDEO_CACHE:
            path = vid.get("path", "")
            if os.path.exists(path):
                _CACHE_MTIME_MAP[path] = os.path.getmtime(path)
        _LAST_REFRESH = time.time()
        return True
    except Exception:
        return False


def refresh_index():
    """Incremental refresh: check for new/changed/deleted files."""
    global _VIDEO_CACHE, _CACHE_MTIME_MAP, _LAST_REFRESH

    now = time.time()
    if now - _LAST_REFRESH < REFRESH_INTERVAL:
        return

    summaries_dir = Path(config.SUMMARIES_DIR)
    if not summaries_dir.exists():
        return

    current_files = {}
    for filepath in summaries_dir.rglob("*– Summary.md"):
        path_str = str(filepath)
        current_files[path_str] = os.path.getmtime(path_str)

    cached_paths = set(_CACHE_MTIME_MAP.keys())
    current_paths = set(current_files.keys())

    new_paths = current_paths - cached_paths
    deleted_paths = cached_paths - current_paths
    changed_paths = {p for p in current_paths & cached_paths
                     if current_files[p] != _CACHE_MTIME_MAP.get(p, 0)}

    if not new_paths and not deleted_paths and not changed_paths:
        _LAST_REFRESH = now
        return

    # Remove deleted
    if deleted_paths:
        _VIDEO_CACHE = [v for v in _VIDEO_CACHE if v["path"] not in deleted_paths]
        for p in deleted_paths:
            _CACHE_MTIME_MAP.pop(p, None)

    # Update changed
    for path_str in changed_paths:
        filepath = Path(path_str)
        vid = _video_dict_from_file(filepath, summaries_dir)
        if vid:
            _VIDEO_CACHE = [v for v in _VIDEO_CACHE if v["path"] != path_str]
            _VIDEO_CACHE.append(vid)
            _CACHE_MTIME_MAP[path_str] = current_files[path_str]

    # Add new
    for path_str in new_paths:
        filepath = Path(path_str)
        vid = _video_dict_from_file(filepath, summaries_dir)
        if vid:
            _VIDEO_CACHE.append(vid)
            _CACHE_MTIME_MAP[path_str] = current_files[path_str]

    _LAST_REFRESH = now

    if new_paths or deleted_paths or changed_paths:
        print(f"Index refreshed: +{len(new_paths)} new, ~{len(changed_paths)} changed, -{len(deleted_paths)} deleted")
        # Rewrite cache file
        try:
            cache_data = [{k: v for k, v in vid.items() if k != "mtime"} for vid in _VIDEO_CACHE]
            _CACHE_FILE.write_text(json.dumps(cache_data, ensure_ascii=False, indent=None), encoding="utf-8")
        except Exception:
            pass


def get_cached_videos():
    """Return the cached video list, refreshing if needed."""
    refresh_index()
    return _VIDEO_CACHE


def get_video_body(file_id):
    """Load the full body of a single video on demand."""
    videos = get_cached_videos()
    video = next((v for v in videos if v["id"] == file_id), None)
    if not video:
        return None, None

    filepath = Path(video["path"])
    _, body = parse_frontmatter(filepath)
    video_with_body = dict(video)
    video_with_body["body"] = body or ""
    return video_with_body, body


# ==============================================================================
# --- FILTER & SORT HELPERS ---
# ==============================================================================

def get_filter_options(videos):
    """Extracts unique playlists, channels, and categories for filter dropdowns."""
    playlists = sorted({v["playlist"] for v in videos if v["playlist"]})
    channels = sorted({v["channel"] for v in videos if v["channel"] and v["channel"] != "Unknown"})
    categories = sorted({v["category"] for v in videos if v["category"]})
    return playlists, channels, categories


def get_top_categories(videos):
    """Extract unique top-level categories for the chip bar."""
    cats = sorted({v["category"] for v in videos if v["category"]})
    return cats


def apply_filters(videos, q="", playlist="", channel="", category=""):
    """Apply search and filter criteria to video list."""
    filtered = videos

    if q:
        q_lower = q.lower()
        filtered = [v for v in filtered if
                    q_lower in v["title"].lower() or
                    q_lower in v["channel"].lower() or
                    q_lower in v["tldr"].lower() or
                    q_lower in v["playlist"].lower() or
                    q_lower in v["category"].lower() or
                    q_lower in v.get("subcategory", "").lower() or
                    q_lower in v.get("topic", "").lower() or
                    any(q_lower in str(t).lower() for t in v["tags"])]

    if playlist:
        filtered = [v for v in filtered if v["playlist"] == playlist]
    if channel:
        filtered = [v for v in filtered if v["channel"] == channel]
    if category:
        filtered = [v for v in filtered if v["category"] == category]

    return filtered


def apply_sort(videos, sort_by="uploaded", sort_dir="desc"):
    """Sort video list by given field and direction."""
    if sort_by in ("title", "channel", "uploaded", "playlist", "category", "duration"):
        videos.sort(key=lambda v: str(v.get(sort_by, "")).lower(), reverse=(sort_dir == "desc"))
    return videos


def compute_stats(videos):
    """Compute statistics for the dashboard."""
    category_counts = Counter(v["category"] for v in videos if v["category"])
    channel_counts = Counter(v["channel"] for v in videos if v["channel"] and v["channel"] != "Unknown")
    language_counts = Counter(v["language"] for v in videos if v["language"])
    difficulty_counts = Counter(v["difficulty"] for v in videos if v["difficulty"])

    # Videos per month
    month_counts = Counter()
    for v in videos:
        uploaded = v.get("uploaded", "")
        if len(uploaded) >= 7:
            month_counts[uploaded[:7]] += 1

    return {
        "total": len(videos),
        "categories": category_counts.most_common(20),
        "top_channels": channel_counts.most_common(15),
        "languages": language_counts.most_common(10),
        "difficulties": difficulty_counts.most_common(),
        "per_month": sorted(month_counts.items())[-24:] if month_counts else [],
    }


# ==============================================================================
# --- TEMPLATE FILTERS ---
# ==============================================================================

@app.template_filter("markdown")
def markdown_filter(text):
    """Converts markdown text to HTML for display in templates."""
    if not text:
        return ""
    html = markdown.markdown(text, extensions=["fenced_code", "tables", "nl2br"])
    return Markup(html)


# ==============================================================================
# --- ROUTES ---
# ==============================================================================

@app.route("/")
def index():
    """Main page – video grid with search, category chips, and filters."""
    videos = get_cached_videos()
    playlists, channels, categories = get_filter_options(videos)
    top_categories = get_top_categories(videos)

    # Apply filters from query params
    q = request.args.get("q", "").strip()
    playlist_filter = request.args.get("playlist", "")
    channel_filter = request.args.get("channel", "")
    category_filter = request.args.get("category", "")
    sort_by = request.args.get("sort", "uploaded")
    sort_dir = request.args.get("dir", "desc")

    filtered = apply_filters(videos, q.lower() if q else "", playlist_filter, channel_filter, category_filter)
    filtered = apply_sort(filtered, sort_by, sort_dir)

    # Recently processed (latest 8 by processed_date)
    recent = sorted(videos, key=lambda v: v.get("processed_date", ""), reverse=True)[:8]

    # Page 1 for server-side render
    per_page = 48
    page1 = filtered[:per_page]

    return render_template("index.html",
                           videos=page1,
                           total=len(videos),
                           shown=len(filtered),
                           playlists=playlists,
                           channels=channels,
                           categories=categories,
                           top_categories=top_categories,
                           recent=recent,
                           q=q,
                           playlist_filter=playlist_filter,
                           channel_filter=channel_filter,
                           category_filter=category_filter,
                           sort_by=sort_by,
                           sort_dir=sort_dir,
                           has_more=len(filtered) > per_page)


@app.route("/video/<path:file_id>")
def video_detail(file_id):
    """Detail page – shows full summary for a video."""
    video, body = get_video_body(file_id)
    if not video:
        return "Video not found", 404
    return render_template("detail.html", video=video)


@app.route("/api/videos")
def api_videos():
    """Paginated JSON API endpoint for videos."""
    videos = get_cached_videos()

    # Apply filters
    q = request.args.get("q", "").strip().lower()
    playlist_filter = request.args.get("playlist", "")
    channel_filter = request.args.get("channel", "")
    category_filter = request.args.get("category", "")
    sort_by = request.args.get("sort", "uploaded")
    sort_dir = request.args.get("dir", "desc")

    filtered = apply_filters(videos, q, playlist_filter, channel_filter, category_filter)
    filtered = apply_sort(filtered, sort_by, sort_dir)

    # Pagination
    page = max(1, request.args.get("page", 1, type=int))
    per_page = min(96, max(1, request.args.get("per_page", 48, type=int)))
    total = len(filtered)
    pages = max(1, (total + per_page - 1) // per_page)
    start = (page - 1) * per_page
    end = start + per_page

    page_videos = filtered[start:end]
    # Remove mtime and body from response
    clean = [{k: v for k, v in vid.items() if k not in ("mtime", "body")} for vid in page_videos]

    return jsonify({
        "videos": clean,
        "total": total,
        "page": page,
        "pages": pages,
        "per_page": per_page,
        "has_next": page < pages,
    })


@app.route("/api/random")
def api_random():
    """Return N random videos for discovery."""
    videos = get_cached_videos()
    n = min(12, max(1, request.args.get("n", 8, type=int)))
    picks = random.sample(videos, min(n, len(videos))) if videos else []
    clean = [{k: v for k, v in vid.items() if k not in ("mtime", "body")} for vid in picks]
    return jsonify({"videos": clean})


@app.route("/api/stats")
def api_stats():
    """Return statistics for the dashboard."""
    videos = get_cached_videos()
    stats = compute_stats(videos)
    return jsonify(stats)


@app.route("/stats")
def stats_page():
    """Statistics dashboard page."""
    videos = get_cached_videos()
    stats = compute_stats(videos)
    top_categories = get_top_categories(videos)
    return render_template("stats.html", stats=stats, top_categories=top_categories)


# ==============================================================================
# --- MAIN ---
# ==============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("YouTube Processor – Browse")
    print(f"Summaries Dir: {config.SUMMARIES_DIR}")
    print("=" * 60)

    # Try loading from cache file first
    if load_index_from_cache():
        print(f"Loaded {len(_VIDEO_CACHE)} videos from cache.")
        print("Starting incremental refresh in background...")
        # Do a full rebuild to catch any changes
        build_index()
        print(f"Index rebuilt: {len(_VIDEO_CACHE)} videos.")
    else:
        print("Building index from scratch (first run)...")
        build_index()
        print(f"Indexed {len(_VIDEO_CACHE)} videos.")

    print(f"\nOpening: http://localhost:5000")
    print("Press Ctrl+C to stop.\n")

    app.run(debug=True, port=5000)

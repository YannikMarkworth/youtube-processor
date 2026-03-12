"""
Browse – Local web interface for YouTube Processor summaries.
=============================================================
Start with:  python browse.py
Then open:   http://localhost:5000

Uses the same config.py paths as the main processor.
"""

import re
import yaml
import markdown
from pathlib import Path
from flask import Flask, render_template, request, jsonify
from markupsafe import Markup

import config

app = Flask(__name__)


@app.template_filter("markdown")
def markdown_filter(text):
    """Converts markdown text to HTML for display in templates."""
    if not text:
        return ""
    html = markdown.markdown(text, extensions=["fenced_code", "tables", "nl2br"])
    return Markup(html)


# ==============================================================================
# --- DATA LOADING ---
# ==============================================================================

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


def load_all_summaries():
    """Scans SUMMARIES_DIR and returns a list of video dicts."""
    summaries_dir = Path(config.SUMMARIES_DIR)
    if not summaries_dir.exists():
        return []

    videos = []
    for filepath in sorted(summaries_dir.rglob("*– Summary.md")):
        fm, body = parse_frontmatter(filepath)
        if fm is None:
            continue

        # Build a stable ID from the file path relative to summaries dir
        rel_path = filepath.relative_to(summaries_dir)
        file_id = str(rel_path).replace("/", "__").replace("\\", "__")

        videos.append({
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
            "tags": fm.get("tags", []),
            "tldr": fm.get("tldr", ""),
            "difficulty": fm.get("difficulty", ""),
            "language": fm.get("language", ""),
            "processed_date": str(fm.get("processed_date", "")),
            "body": body,
        })

    return videos


def get_filter_options(videos):
    """Extracts unique playlists, channels, and categories for filter dropdowns."""
    playlists = sorted({v["playlist"] for v in videos if v["playlist"]})
    channels = sorted({v["channel"] for v in videos if v["channel"] and v["channel"] != "Unknown"})
    categories = sorted({v["category"] for v in videos if v["category"]})
    return playlists, channels, categories


# ==============================================================================
# --- ROUTES ---
# ==============================================================================

@app.route("/")
def index():
    """Main page – video list with search and filters."""
    videos = load_all_summaries()
    playlists, channels, categories = get_filter_options(videos)

    # Apply filters from query params
    q = request.args.get("q", "").strip().lower()
    playlist_filter = request.args.get("playlist", "")
    channel_filter = request.args.get("channel", "")
    category_filter = request.args.get("category", "")
    sort_by = request.args.get("sort", "uploaded")
    sort_dir = request.args.get("dir", "desc")

    filtered = videos

    if q:
        filtered = [v for v in filtered if
                    q in v["title"].lower() or
                    q in v["channel"].lower() or
                    q in v["tldr"].lower() or
                    q in v["playlist"].lower() or
                    q in v["category"].lower() or
                    any(q in str(t).lower() for t in v["tags"])]

    if playlist_filter:
        filtered = [v for v in filtered if v["playlist"] == playlist_filter]
    if channel_filter:
        filtered = [v for v in filtered if v["channel"] == channel_filter]
    if category_filter:
        filtered = [v for v in filtered if v["category"] == category_filter]

    # Sort
    if sort_by in ("title", "channel", "uploaded", "playlist", "category", "duration"):
        filtered.sort(key=lambda v: str(v.get(sort_by, "")).lower(), reverse=(sort_dir == "desc"))

    return render_template("index.html",
                           videos=filtered,
                           total=len(videos),
                           shown=len(filtered),
                           playlists=playlists,
                           channels=channels,
                           categories=categories,
                           q=request.args.get("q", ""),
                           playlist_filter=playlist_filter,
                           channel_filter=channel_filter,
                           category_filter=category_filter,
                           sort_by=sort_by,
                           sort_dir=sort_dir)


@app.route("/video/<path:file_id>")
def video_detail(file_id):
    """Detail page – shows full summary for a video."""
    videos = load_all_summaries()
    video = next((v for v in videos if v["id"] == file_id), None)
    if not video:
        return "Video not found", 404
    return render_template("detail.html", video=video)


@app.route("/api/videos")
def api_videos():
    """JSON API endpoint for all videos (for potential future use)."""
    videos = load_all_summaries()
    # Remove body from list response to keep it lightweight
    return jsonify([{k: v for k, v in vid.items() if k != "body"} for vid in videos])


# ==============================================================================
# --- MAIN ---
# ==============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("YouTube Processor – Browse")
    print(f"Summaries Dir: {config.SUMMARIES_DIR}")
    print("=" * 60)

    videos = load_all_summaries()
    print(f"Found {len(videos)} summary files.")
    print(f"\nOpening: http://localhost:5000")
    print("Press Ctrl+C to stop.\n")

    app.run(debug=True, port=5000)

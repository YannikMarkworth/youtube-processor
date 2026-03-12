import config
import logging
import re
import yaml
from datetime import datetime
from pathlib import Path


def format_iso_date(date_str):
    """Converts '2024-01-15T12:30:00Z' to '2024-01-15'. Passes through already-clean dates."""
    if not date_str or date_str == "N/A":
        return date_str
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return date_str
    m = re.match(r'^(\d{4}-\d{2}-\d{2})', date_str)
    return m.group(1) if m else date_str


def format_iso_duration(duration_str):
    """Converts 'PT1H23M45S' to '1:23:45' or 'PT11M58S' to '11:58'. Passes through already-clean values."""
    if not duration_str or duration_str == "N/A":
        return duration_str
    if re.match(r'^\d+:\d{2}(:\d{2})?$', duration_str):
        return duration_str
    m = re.match(r'^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$', duration_str)
    if not m:
        return duration_str
    hours = int(m.group(1) or 0)
    minutes = int(m.group(2) or 0)
    seconds = int(m.group(3) or 0)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"

# --- Filename Handling ---

def clean_filename(name_part): # Renamed 'title' to 'name_part' for generic use
    """
    Removes or replaces characters invalid in filenames/directory names
    across common OS (including '#') and limits the length.
    Also strips leading/trailing spaces and underscores.
    """
    if not name_part:
        name_part = "untitled"
    # Remove characters invalid in Windows/Unix filenames: \ / * ? : " < > | #
    cleaned_name = re.sub(r'[\\/*?:"<>|#]', "", name_part)
    
    max_len = 100 # Arbitrary limit
    if len(cleaned_name) > max_len:
        cleaned_name = cleaned_name[:max_len]
        
    cleaned_name = cleaned_name.strip('_ ') # Strip spaces and underscores
    
    if not cleaned_name: # Ensure not empty after cleaning
        cleaned_name = "cleaned_untitled"
    return cleaned_name

def generate_filename_component(playlist_name_for_filename, video_id, title):
    """
    Creates the main component for filenames:
    'Playlist Name For Filename – Cleaned Video Title – VIDEO_ID'.
    The '.md' or ' – Summary.md' suffix is added later.
    The playlist_name_for_filename should already be cleaned if necessary for filename usage.
    """
    cleaned_title = clean_filename(title)
    # Filename Structure: Playlist Name – Cleaned Title – VIDEO_ID
    return f"{playlist_name_for_filename} – {cleaned_title} – {video_id}"

# --- File Existence Checks ---

def check_summary_exists(video_id, cleaned_playlist_foldername): # MODIFIED: added cleaned_playlist_foldername
    """
    Checks if a summary file matching the pattern '* – VIDEO_ID – Summary.md'
    exists in the specified playlist subfolder within the summaries directory.

    Args:
        video_id (str): The YouTube video ID to check for.
        cleaned_playlist_foldername (str): The name of the subfolder (cleaned playlist name).

    Returns:
        bool: True if a matching summary file exists, False otherwise.
    """
    playlist_summary_subfolder = config.SUMMARIES_DIR / cleaned_playlist_foldername
    if not playlist_summary_subfolder.exists():
        return False # Folder doesn't exist, so summary can't exist

    # Search for any file in that subfolder that contains " – VIDEO_ID – Summary.md"
    # The beginning part (playlist name & title) can vary slightly due to cleaning nuances
    # or if a file was manually renamed, so video_id is the most reliable part.
    search_pattern = f"*– {video_id} – Summary.md" # Relaxed search for the crucial parts
    
    glob_generator = playlist_summary_subfolder.glob(search_pattern)
    found_file = next(glob_generator, None)
    exists = found_file is not None
    if exists:
        logging.debug(f"Summary file found for {video_id} in folder '{cleaned_playlist_foldername}': {found_file}")
    else:
        logging.debug(f"No summary file found matching pattern '{search_pattern}' for {video_id} in folder '{cleaned_playlist_foldername}'")
    return exists

# --- File Reading --- (No changes needed in read_transcript_from_file)
def read_transcript_from_file(transcript_filepath):
    transcript_filepath = Path(transcript_filepath)
    if not transcript_filepath.exists():
        logging.warning(f"Attempted to read non-existent transcript file: {transcript_filepath}")
        return None
    try:
        with open(transcript_filepath, "r", encoding="utf-8") as f: lines = f.readlines()
        content_started, yaml_delimiters_found, transcript_lines = False, 0, []
        for line in lines:
            if line.strip() == '---':
                yaml_delimiters_found += 1
                if yaml_delimiters_found == 2: content_started = True
                continue 
            if content_started: transcript_lines.append(line)
        if not transcript_lines:
             logging.warning(f"Could not extract transcript content (post-YAML) from {transcript_filepath}")
             return None
        return "".join(transcript_lines).strip()
    except Exception as e:
        logging.error(f"Error reading transcript file {transcript_filepath}: {e}")
        return None

# --- File Writing ---

def create_transcript_file(video_details, transcript, transcript_filepath):
    """
    Creates or overwrites the transcript Markdown file.
    The transcript_filepath should include the playlist subfolder.
    """
    if not video_details or transcript is None:
        logging.error("Cannot create transcript file: Missing video_details or transcript is None.")
        return False
    transcript_filepath = Path(transcript_filepath)
    try:
        logging.info(f"Writing transcript file: {transcript_filepath}")
        print(f"Saving transcript file: {transcript_filepath.relative_to(config.OUTPUT_DIR)}")
        metadata = {
            "title": video_details.get("title", "N/A"), "video_id": video_details.get("videoId", "N/A"),
            "video_url": video_details.get("videoUrl", "N/A"), "channel": video_details.get("channelTitle", "N/A"),
            "channel_id": video_details.get("channelId", "N/A"), "upload_date": video_details.get("publishedAt", "N/A"),
            "duration": video_details.get("duration", "N/A"),
        }
        # Ensure the subfolder exists
        transcript_filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(transcript_filepath, "w", encoding="utf-8") as f:
            f.write("---\n"); yaml.dump(metadata, f, allow_unicode=True, default_flow_style=False, sort_keys=False); f.write("---\n\n")
            description = video_details.get('description', '').strip()
            if description: f.write("## Description\n\n" + description + "\n\n---\n\n")
            f.write("## Transcript\n\n" + (transcript if transcript else "*Transcript not available or empty.*"))
        logging.info(f"Successfully wrote transcript file: {transcript_filepath}")
        return True
    except Exception as e:
        logging.error(f"Error writing transcript file {transcript_filepath}: {e}")
        print(f"Error writing transcript file {transcript_filepath.name}: {e}")
        return False

def create_summary_file(video_details, summary, summary_filepath, transcript_filename_component, display_playlist_name="N/A", ai_metadata=None):
    """
    Creates or overwrites the summary Markdown file with YAML frontmatter.
    The summary_filepath should include the playlist subfolder.
    transcript_filename_component is the actual filename of the transcript.
    ai_metadata is an optional dict with keys like tldr, category, tags, difficulty, language.
    """
    if not video_details or summary is None:
        logging.error("Cannot create summary file: Missing video_details or summary is None.")
        return False
    summary_filepath = Path(summary_filepath)
    link_target_transcript_name = transcript_filename_component.removesuffix('.md')
    if ai_metadata is None:
        ai_metadata = {}

    try:
        logging.info(f"Writing summary file: {summary_filepath}")
        print(f"Saving summary file: {summary_filepath.relative_to(config.OUTPUT_DIR)}")
        summary_filepath.parent.mkdir(parents=True, exist_ok=True)

        channel_title = video_details.get('channelTitle', 'N/A')

        # Build YAML frontmatter metadata
        frontmatter = {
            "title": video_details.get("title", "Untitled Video"),
            "video_id": video_details.get("videoId", "N/A"),
            "video_url": video_details.get("videoUrl", "N/A"),
            "channel": channel_title,
            "channel_id": video_details.get("channelId", "N/A"),
            "uploaded": format_iso_date(video_details.get("publishedAt", "N/A")),
            "duration": format_iso_duration(video_details.get("duration", "N/A")),
            "playlist": display_playlist_name,
        }

        # Add AI-generated metadata if available
        if ai_metadata.get("tldr"):
            frontmatter["tldr"] = ai_metadata["tldr"]
        if ai_metadata.get("category"):
            # Split "A > B > C" into separate fields for Obsidian Bases
            parts = [p.strip() for p in ai_metadata["category"].split(" > ")]
            frontmatter["category"] = parts[0] if len(parts) > 0 else ""
            frontmatter["subcategory"] = parts[1] if len(parts) > 1 else ""
            frontmatter["topic"] = parts[2] if len(parts) > 2 else ""
        if ai_metadata.get("tags"):
            frontmatter["tags"] = ai_metadata["tags"]
        if ai_metadata.get("difficulty"):
            frontmatter["difficulty"] = ai_metadata["difficulty"]
        if ai_metadata.get("language"):
            frontmatter["language"] = ai_metadata["language"]

        frontmatter["processed_date"] = datetime.now().strftime("%Y-%m-%d")

        with open(summary_filepath, "w", encoding="utf-8") as f:
            # Write YAML frontmatter
            f.write("---\n")
            yaml.dump(frontmatter, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            f.write("---\n\n")

            # Write video info block
            video_url = video_details.get("videoUrl", "N/A")
            video_title = video_details.get("title", "N/A")
            uploaded = video_details.get("publishedAt", "N/A")
            duration = video_details.get("duration", "N/A")

            f.write(f"{video_url}\n\n")
            f.write(f"**Title:** {video_title}\n")
            f.write(f"**Video URL:** {video_url}\n")
            f.write(f"**Channel:** [[▶️ {channel_title}]]\n")
            f.write(f"**Uploaded:** {uploaded}\n")
            f.write(f"**Duration:** {duration}\n")
            f.write(f"**Playlist:** [[Playlist {display_playlist_name}]]\n\n")

            # Write the summary content
            f.write("## AI Summary\n\n")
            f.write(summary if summary.strip() else "*Summary could not be generated or was empty.*")
            f.write("\n\n")

            # Write transcript link
            f.write("## Transcript\n\n")
            f.write(f"[[{link_target_transcript_name}]]\n")

        logging.info(f"Successfully wrote summary file: {summary_filepath}")
        return True
    except Exception as e:
        logging.error(f"Error writing summary file {summary_filepath}: {e}", exc_info=True)
        print(f"Error writing summary file {summary_filepath.name}: {e}")
        return False
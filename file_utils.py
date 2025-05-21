import config
import logging
import re
import yaml
from pathlib import Path

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

def create_summary_file(video_details, summary, summary_filepath, transcript_filename_component, display_playlist_name="N/A"):
    """
    Creates or overwrites the summary Markdown file.
    The summary_filepath should include the playlist subfolder.
    transcript_filename_component is the actual filename of the transcript (e.g., "Playlist – Title – ID.md" or just "Playlist – Title – ID").
    """
    if not video_details or summary is None:
        logging.error("Cannot create summary file: Missing video_details or summary is None.")
        return False
    summary_filepath = Path(summary_filepath)
    # Ensure transcript_filename_component does not end with .md for the link
    link_target_transcript_name = transcript_filename_component.removesuffix('.md')

    try:
        logging.info(f"Writing summary file: {summary_filepath}")
        print(f"Saving summary file: {summary_filepath.relative_to(config.OUTPUT_DIR)}")
        # Ensure the subfolder exists
        summary_filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(summary_filepath, "w", encoding="utf-8") as f:
            f.write(f"{video_details.get('videoUrl', 'N/A')}\n\n") 
            f.write(f"**Title:** {video_details.get('title', 'Untitled Video')}\n\n")
            f.write(f"**Video URL:** {video_details.get('videoUrl', 'N/A')}\n")
            channel_title = video_details.get('channelTitle', 'N/A')
            f.write(f"**Channel:** [[▶️ {channel_title}]]\n")
            f.write(f"**Uploaded:** {video_details.get('publishedAt', 'N/A')}\n")
            f.write(f"**Duration:** {video_details.get('duration', 'N/A')}\n")
            # Use display_playlist_name (rawer version) for the link content
            f.write(f"**Playlist:** [[Playlist {display_playlist_name}]]\n\n")
            f.write("## AI Summary\n\n")
            f.write(summary if summary.strip() else "*Summary could not be generated or was empty.*")
            f.write("\n\n") 
            f.write("## Transcript\n\n")
            # The link target is just the name of the transcript file.
            # Obsidian should find it if it's in ../transcripts/PLAYLIST_FOLDER/
            # or if names are unique enough within the vault.
            f.write(f"[[{link_target_transcript_name}]]\n")
        logging.info(f"Successfully wrote summary file: {summary_filepath}")
        return True
    except Exception as e:
        logging.error(f"Error writing summary file {summary_filepath}: {e}", exc_info=True)
        print(f"Error writing summary file {summary_filepath.name}: {e}")
        return False
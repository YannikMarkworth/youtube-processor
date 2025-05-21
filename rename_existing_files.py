import os
import re
import logging
import sys
from pathlib import Path
import config       # To access TRANSCRIPTS_DIR, SUMMARIES_DIR, BASE_DIR
import file_utils   # To access clean_filename

# Configure basic logging for this script
log_file_path_rename = config.BASE_DIR / "rename_files_log.log"
# Ensure logging is set up fresh for this script, or clear existing handlers
root_logger = logging.getLogger()
if root_logger.handlers:
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)-8s - %(module)s - %(funcName)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file_path_rename, mode='a', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# MODIFIED Regex to parse old filenames based on log output
# Assumes 11-character VIDEO_ID followed by '_' and then the title part (which includes underscores)
# For transcripts: "VIDEOID_Title_With_Underscores.md"
OLD_TRANSCRIPT_REGEX = re.compile(r"([a-zA-Z0-9_-]{11})_(.*)\.md")
# For summaries: "VIDEOID_Title_With_Underscores_summary.md"
OLD_SUMMARY_REGEX = re.compile(r"([a-zA-Z0-9_-]{11})_(.*)_summary\.md")

# Regex to extract playlist name from summary content: **Playlist:** [[Playlist ActualName]]
PLAYLIST_LINE_REGEX = re.compile(r"\*\*Playlist:\*\* \[\[Playlist (.*?)\]\]")

def get_playlist_from_summary_content(summary_filepath_obj):
    """Reads a summary file and extracts the playlist name."""
    try:
        content = summary_filepath_obj.read_text(encoding="utf-8")
        match = PLAYLIST_LINE_REGEX.search(content)
        if match:
            playlist_name = match.group(1).strip()
            logging.debug(f"Extracted playlist '{playlist_name}' from {summary_filepath_obj.name}")
            return playlist_name
        else:
            logging.warning(f"Playlist line not found in {summary_filepath_obj.name}")
            return None
    except Exception as e:
        logging.error(f"Error reading or parsing playlist from {summary_filepath_obj.name}: {e}")
        return None

def process_summary_file(summary_filepath_obj, video_id_to_playlist_map, is_dry_run):
    """Processes a single summary file: extracts data, renames, updates link, and populates map."""
    logging.info(f"Processing SUMMARY file: {summary_filepath_obj.name}")
    old_filename = summary_filepath_obj.name
    match = OLD_SUMMARY_REGEX.match(old_filename) # Uses updated regex

    if not match:
        logging.warning(f"Could not parse old summary filename (using new regex): {old_filename}. Skipping.")
        return False

    video_id = match.group(1)
    old_title_part_with_underscores = match.group(2)
    title_part_with_spaces = old_title_part_with_underscores.replace('_', ' ') # Convert underscores to spaces for the new title

    extracted_playlist_name_raw = get_playlist_from_summary_content(summary_filepath_obj)
    if not extracted_playlist_name_raw:
        logging.warning(f"No playlist name found in content of {old_filename}. Using 'Unknown Playlist'.")
        extracted_playlist_name_raw = "Unknown Playlist"
    
    cleaned_playlist_name_for_file = file_utils.clean_filename(extracted_playlist_name_raw)
    video_id_to_playlist_map[video_id] = cleaned_playlist_name_for_file

    new_base_name_part = f"{cleaned_playlist_name_for_file} – {title_part_with_spaces} – {video_id}"
    new_summary_filename = f"{new_base_name_part} – Summary.md"
    new_summary_filepath_obj = summary_filepath_obj.parent / new_summary_filename

    if summary_filepath_obj == new_summary_filepath_obj:
        logging.info(f"Skipped: Summary file '{old_filename}' already matches new format.")
        return "skipped"

    logging.info(f"  Old Video ID: {video_id}, Old Title Part (underscored): {old_title_part_with_underscores}")
    logging.info(f"  New Title Part (spaced): {title_part_with_spaces}")
    logging.info(f"  Extracted Playlist: '{extracted_playlist_name_raw}' (Cleaned: '{cleaned_playlist_name_for_file}')")
    logging.info(f"  New proposed summary filename: '{new_summary_filename}'")

    if not is_dry_run:
        try:
            temp_path_for_read_write = summary_filepath_obj
            if summary_filepath_obj != new_summary_filepath_obj :
                summary_filepath_obj.rename(new_summary_filepath_obj)
                logging.info(f"  SUCCESS: Renamed '{old_filename}' to '{new_summary_filename}'")
                temp_path_for_read_write = new_summary_filepath_obj

            logging.info(f"    Attempting to update internal link in '{new_summary_filename}'...")
            # Old link target was [[VIDEOID_OldTitlePartWithUnderscores]]
            old_link_target_basename = f"{video_id}_{old_title_part_with_underscores}"
            # New link target is [[PlaylistName – TitleWithSpaces – VIDEOID]]
            new_link_target_basename = f"{cleaned_playlist_name_for_file} – {title_part_with_spaces} – {video_id}"
            
            content = temp_path_for_read_write.read_text(encoding="utf-8")
            old_link_pattern = re.compile(r"\[\[" + re.escape(old_link_target_basename) + r"\]\]")
            new_link_string = f"[[{new_link_target_basename}]]"

            if old_link_pattern.search(content):
                updated_content = old_link_pattern.sub(new_link_string, content)
                if updated_content != content:
                    temp_path_for_read_write.write_text(updated_content, encoding="utf-8")
                    logging.info(f"    SUCCESS: Internal link updated to point to '[[{new_link_target_basename}]]'.")
                else:
                    logging.warning(f"    INFO: Link '[[{old_link_target_basename}]]' found but no change after replacement logic.")
            else:
                logging.warning(f"    WARNING: Expected link '[[{old_link_target_basename}]]' not found. Manual check advised.")
            return True
        except Exception as e_rename:
            logging.error(f"  ERROR processing summary file '{old_filename}': {e_rename}")
            return False
    return "dry_run_success"

def process_transcript_file(transcript_filepath_obj, video_id_to_playlist_map, is_dry_run):
    """Processes a single transcript file: renames it based on the playlist map."""
    logging.info(f"Processing TRANSCRIPT file: {transcript_filepath_obj.name}")
    old_filename = transcript_filepath_obj.name
    match = OLD_TRANSCRIPT_REGEX.match(old_filename) # Uses updated regex

    if not match:
        logging.warning(f"Could not parse old transcript filename (using new regex): {old_filename}. Skipping.")
        return False

    video_id = match.group(1)
    old_title_part_with_underscores = match.group(2)
    title_part_with_spaces = old_title_part_with_underscores.replace('_', ' ') # Convert underscores to spaces

    playlist_name_for_file = video_id_to_playlist_map.get(video_id)
    if not playlist_name_for_file:
        logging.warning(f"No playlist mapping found for transcript's video ID '{video_id}' (source: {old_filename}). Using 'Unknown Playlist'.")
        playlist_name_for_file = "Unknown Playlist"
    
    new_base_name_part = f"{playlist_name_for_file} – {title_part_with_spaces} – {video_id}"
    new_transcript_filename = f"{new_base_name_part}.md"
    new_transcript_filepath_obj = transcript_filepath_obj.parent / new_transcript_filename

    if transcript_filepath_obj == new_transcript_filepath_obj:
        logging.info(f"Skipped: Transcript file '{old_filename}' already matches new format or uses 'Unknown Playlist' consistently.")
        return "skipped"

    logging.info(f"  Old Video ID: {video_id}, Old Title Part (underscored): {old_title_part_with_underscores}")
    logging.info(f"  New Title Part (spaced): {title_part_with_spaces}")
    logging.info(f"  Playlist from map: '{playlist_name_for_file}'")
    logging.info(f"  New proposed transcript filename: '{new_transcript_filename}'")

    if not is_dry_run:
        try:
            transcript_filepath_obj.rename(new_transcript_filepath_obj)
            logging.info(f"  SUCCESS: Renamed '{old_filename}' to '{new_transcript_filename}'")
            return True
        except Exception as e_rename:
            logging.error(f"  ERROR renaming transcript file '{old_filename}': {e_rename}")
            return False
    return "dry_run_success"

if __name__ == "__main__":
    print("--- Existing Files Renaming Script (Auto Playlist Detection & Underscore Fix) ---") # Updated title
    print(f"This script will rename existing files and attempt to detect playlist names from summary file contents.")
    print(f"It assumes old filenames are like 'VIDEOID_Title_With_Underscores.md'.") # Added assumption
    print(f"  New Transcript: 'Detected Playlist Name – Title With Spaces – VIDEO_ID.md'")
    print(f"  New Summary:    'Detected Playlist Name – Title With Spaces – VIDEO_ID – Summary.md'")
    print(f"It will also update internal Obsidian links in summary files.")
    print(f"Logs will be saved to: {log_file_path_rename}")
    print("-" * 30)

    dry_run_input = input("Perform a DRY RUN first? (yes/no) [yes]: ").strip().lower()
    is_dry_run = dry_run_input != "no"

    if is_dry_run:
        print("\n--- STARTING DRY RUN ---")
        print("No files will actually be changed.")
    else:
        confirmation = input(f"\nWARNING: This will RENAME files and MODIFY summary contents in:\n"
                             f"  - Transcripts: {config.TRANSCRIPTS_DIR}\n"
                             f"  - Summaries:   {config.SUMMARIES_DIR}\n"
                             f"Playlist names will be extracted from summary files automatically.\n"
                             f"Underscores in old title parts will be converted to spaces.\n" # Added note
                             f"Are you sure you want to proceed? (yes/no): ").strip().lower()
        if confirmation != "yes":
            print("Operation cancelled by user. Exiting.")
            sys.exit(0)
        print("\n--- STARTING ACTUAL RENAMING ---")

    video_id_to_playlist_name = {}
    
    summary_processed_count = 0
    summary_skipped_count = 0
    summary_error_count = 0
    transcript_processed_count = 0
    transcript_skipped_count = 0
    transcript_error_count = 0

    # --- Process Summaries First ---
    logging.info("--- Starting Pass 1: Processing Summary Files ---")
    print("\n--- Processing Summary Files ---")
    if config.SUMMARIES_DIR.exists() and config.SUMMARIES_DIR.is_dir():
        for filepath_obj in sorted(config.SUMMARIES_DIR.iterdir()): 
            if filepath_obj.is_file() and filepath_obj.name.endswith(".md"):
                result = process_summary_file(filepath_obj, video_id_to_playlist_name, is_dry_run)
                if result == True or result == "dry_run_success": summary_processed_count += 1
                elif result == "skipped": summary_skipped_count += 1
                else: summary_error_count += 1
    else:
        logging.warning(f"Summaries directory not found or is not a directory: {config.SUMMARIES_DIR}")
        print(f"Warning: Summaries directory not found: {config.SUMMARIES_DIR}")
    
    logging.info(f"--- Finished Pass 1: Summary Files ---")
    logging.info(f"  Summaries {'Would process' if is_dry_run else 'Processed'}: {summary_processed_count}, Skipped: {summary_skipped_count}, Errors: {summary_error_count}")
    print(f"Summary files scan complete. Processed: {summary_processed_count}, Skipped: {summary_skipped_count}, Errors: {summary_error_count}")

    # --- Process Transcripts Second ---
    logging.info("--- Starting Pass 2: Processing Transcript Files ---")
    print("\n--- Processing Transcript Files ---")
    if config.TRANSCRIPTS_DIR.exists() and config.TRANSCRIPTS_DIR.is_dir():
        for filepath_obj in sorted(config.TRANSCRIPTS_DIR.iterdir()):
            if filepath_obj.is_file() and filepath_obj.name.endswith(".md"):
                result = process_transcript_file(filepath_obj, video_id_to_playlist_name, is_dry_run)
                if result == True or result == "dry_run_success": transcript_processed_count +=1
                elif result == "skipped": transcript_skipped_count += 1
                else: transcript_error_count += 1
    else:
        logging.warning(f"Transcripts directory not found or is not a directory: {config.TRANSCRIPTS_DIR}")
        print(f"Warning: Transcripts directory not found: {config.TRANSCRIPTS_DIR}")

    logging.info(f"--- Finished Pass 2: Transcript Files ---")
    logging.info(f"  Transcripts {'Would process' if is_dry_run else 'Processed'}: {transcript_processed_count}, Skipped: {transcript_skipped_count}, Errors: {transcript_error_count}")
    print(f"Transcript files scan complete. Processed: {transcript_processed_count}, Skipped: {transcript_skipped_count}, Errors: {transcript_error_count}")

    print("-" * 30)
    if is_dry_run:
        print("DRY RUN finished. Review the logs. Run again with 'no' for dry run to apply changes.")
    else:
        print("RENAMING process finished. Please check your files and the log.")
    print(f"Detailed log saved to: {log_file_path_rename}")
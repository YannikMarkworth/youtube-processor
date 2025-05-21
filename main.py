import logging
import sys
import re
from datetime import datetime
from pathlib import Path
import platform 

import config 
import youtube_utils
import transcript_utils
import file_utils
import ai_utils

SUMMARIES_LOG_FOR_CURRENT_RUN = []

def setup_logging(log_level=logging.INFO):
    # ... (logging setup remains the same)
    log_file_path = config.ERROR_LOG_FILE
    print(f"[INFO] Attempting to configure logging. Level: {logging.getLevelName(log_level)}. File: {log_file_path}")
    force_reconfigure = False
    try:
        python_version_tuple = platform.python_version_tuple()
        if int(python_version_tuple[0]) >= 3 and int(python_version_tuple[1]) >= 8:
            force_reconfigure = True
    except Exception: pass 
    file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
    file_handler.setLevel(log_level)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)-8s - %(name)s - %(module)s:%(lineno)d - %(funcName)s - %(message)s')
    console_formatter = logging.Formatter('%(levelname)s: %(message)s') 
    file_handler.setFormatter(file_formatter)
    console_handler.setFormatter(console_formatter)
    handlers_list = [file_handler, console_handler]
    try:
        if force_reconfigure: logging.basicConfig(level=log_level, handlers=handlers_list, force=True)
        else: 
             root = logging.getLogger()
             if root.handlers:
                 for handler in root.handlers[:]: root.removeHandler(handler); handler.close()
             logging.basicConfig(level=log_level, handlers=handlers_list)
        logging.info(f"Logging configured. Root level: {logging.getLevelName(logging.getLogger().level)}. File: {log_file_path}")
        logging.info(f"Using OpenAI Config: Model='{config.OPENAI_MODEL_NAME}', ContextLimit={config.OPENAI_CONTEXT_LIMIT}, MaxOutputTokens={config.OPENAI_MAX_TOKENS}, Temperature={config.OPENAI_TEMPERATURE}")
    except Exception as e:
        logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s', stream=sys.stdout)
        logging.error(f"[ERROR] Failed to configure custom logging: {e}. Using basic console logging.", exc_info=True)


def extract_playlist_id(url):
    # ... (extract_playlist_id remains the same)
    patterns = [ r'list=([a-zA-Z0-9_-]+)' ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match: return match.group(1)
    logging.error(f"Could not extract Playlist ID from URL: {url}")
    print(f"Error: Could not find a valid YouTube Playlist ID in URL: {url}\nEnsure the URL contains 'list=PLAYLIST_ID'.")
    return None

def process_playlist(playlist_url):
    logging.info(f"Attempting to process playlist URL: {playlist_url}")
    playlist_id = extract_playlist_id(playlist_url)
    if not playlist_id: return

    logging.info("Loading summarization prompts...")
    chunk_prompt_template = ai_utils.load_prompt(config.CHUNK_PROMPT_FILE)
    final_prompt_template = ai_utils.load_prompt(config.FINAL_PROMPT_FILE)
    prompts_available = chunk_prompt_template and final_prompt_template
    if not prompts_available:
        logging.warning("Could not load prompt templates. AI Summarization will be skipped for this playlist.")

    youtube = youtube_utils.build_youtube_service()
    if not youtube: return

    playlist_details = youtube_utils.get_playlist_details(youtube, playlist_id)
    raw_playlist_title = "Unknown Playlist"
    if playlist_details and playlist_details.get("title"):
        raw_playlist_title = playlist_details["title"]
    
    cleaned_playlist_name_for_path_and_filename = file_utils.clean_filename(raw_playlist_title)
    
    logging.info(f"Processing videos from playlist: '{raw_playlist_title}' (Cleaned for path/file: '{cleaned_playlist_name_for_path_and_filename}', ID: {playlist_id})")
    print(f"Aktuelle Playlist: '{raw_playlist_title}' (Ordner/Dateiname-Präfix: '{cleaned_playlist_name_for_path_and_filename}')")

    video_items = youtube_utils.get_playlist_video_items(youtube, playlist_id)
    if not video_items: 
        logging.warning(f"No video items found in playlist '{raw_playlist_title}'.")
        print(f"Warnung: Keine Videos in Playlist '{raw_playlist_title}' gefunden.")
        return

    total_videos, processed_count, skipped_count, failed_to_create_files_count = len(video_items), 0, 0, 0 # Renamed failed_count
    logging.info(f"{total_videos} videos found in playlist '{raw_playlist_title}'.")
    print(f"{total_videos} Videos in Playlist '{raw_playlist_title}' gefunden.")
    
    playlist_transcript_subfolder = config.TRANSCRIPTS_DIR / cleaned_playlist_name_for_path_and_filename
    playlist_summary_subfolder = config.SUMMARIES_DIR / cleaned_playlist_name_for_path_and_filename

    for index, (video_id, _) in enumerate(video_items):
        current_video_num = index + 1
        logging.info(f"--- Processing video {current_video_num}/{total_videos} (ID: {video_id}) from playlist '{raw_playlist_title}' ---")

        video_details = youtube_utils.get_video_details(youtube, video_id)
        if not video_details:
            logging.error(f"FAILURE: Could not fetch details for video ID '{video_id}'. Skipped from further processing.")
            failed_to_create_files_count += 1 # Count as a failure to create any files
            continue

        video_title_raw = video_details.get('title', 'untitled_video')
        filename_core_component = file_utils.generate_filename_component(
            cleaned_playlist_name_for_path_and_filename, video_id, video_title_raw
        )
        
        transcript_filepath = playlist_transcript_subfolder / f"{filename_core_component}.md"
        summary_filepath = playlist_summary_subfolder / f"{filename_core_component} – Summary.md"
        
        logging.debug(f"Expected transcript file: {transcript_filepath}")
        logging.debug(f"Expected summary file: {summary_filepath}")

        # Skip if summary file already exists (as per previous logic)
        # This check now assumes that if a summary exists, the whole process for this video was completed.
        if file_utils.check_summary_exists(video_id, cleaned_playlist_name_for_path_and_filename):
            logging.info(f"Skipped: Summary for video ID '{video_id}' already exists in folder '{cleaned_playlist_name_for_path_and_filename}'.")
            print(f"Übersprungen: Summary für {video_id} in Ordner '{cleaned_playlist_name_for_path_and_filename}' existiert bereits.")
            skipped_count += 1
            continue
        
        # --- Transcript Fetching and File Creation ---
        transcript_content = None
        transcript_available_for_summarization = False # Flag to indicate if we have a real transcript

        if transcript_filepath.exists():
            logging.info(f"Transcript file found: {transcript_filepath.name}. Reading...")
            transcript_content = file_utils.read_transcript_from_file(transcript_filepath)
            if transcript_content is not None:
                transcript_available_for_summarization = True
            else:
                 logging.warning(f"Could not read content from existing transcript file: {transcript_filepath}. Using placeholder.")
                 transcript_content = "Transcript could not be loaded from existing file. Please paste manually."
        else: # Transcript file does not exist, try fetching from API
            logging.info(f"Transcript file not found for {video_id}. Fetching from API...")
            api_transcript = transcript_utils.get_transcript(video_id)
            if api_transcript is not None:
                transcript_content = api_transcript
                transcript_available_for_summarization = True
            else:
                logging.warning(f"Transcript not available via API for video ID '{video_id}'. Using placeholder.")
                transcript_content = "Transcript could not be fetched from API. Please paste manually if available elsewhere."

        # Always try to create the transcript file (with content or placeholder)
        if not file_utils.create_transcript_file(video_details, transcript_content, transcript_filepath):
            logging.error(f"FAILURE: Could not create transcript file (even with placeholder) at {transcript_filepath}. Skipping this video.")
            failed_to_create_files_count += 1
            continue # If we can't even save this, something is wrong with file system access for this video.
        
        # --- Summarization ---
        summary_content = None
        is_placeholder_summary = False

        if not prompts_available:
            logging.warning(f"Prompts not loaded. Skipping AI summarization for {video_id}.")
            summary_content = "Summary generation skipped: AI Prompts missing."
            is_placeholder_summary = True
        elif not transcript_available_for_summarization:
            logging.info(f"Transcript for video ID '{video_id}' is a placeholder. Skipping AI summarization.")
            summary_content = "Summary not generated: Transcript was unavailable or could not be loaded."
            is_placeholder_summary = True
        else:
            logging.info(f"Generating AI summary for video ID '{video_id}'...")
            summary_content = ai_utils.summarize_transcript(
                transcript_content, chunk_prompt_template, final_prompt_template, video_title_raw
            )
            if summary_content is None:
                logging.error(f"AI summary generation failed for video ID '{video_id}'.")
                summary_content = "AI summary generation failed. Please check AI service or logs."
                is_placeholder_summary = True
        
        # --- Summary File Creation ---
        if file_utils.create_summary_file(video_details, summary_content, summary_filepath, filename_core_component, raw_playlist_title):
            logging.info(f"Video {video_id} processed. Transcript and Summary files created/updated at {summary_filepath.parent}")
            processed_count += 1 # Count as processed if all files are made.
            
            summary_filename_stem = summary_filepath.name.removesuffix('.md')
            link_path_for_master_log = f"summaries/{cleaned_playlist_name_for_path_and_filename}/{summary_filename_stem}"
            SUMMARIES_LOG_FOR_CURRENT_RUN.append({
                "link_target": link_path_for_master_log,
                "video_title": video_title_raw,
                "playlist_context": raw_playlist_title,
                "is_placeholder": is_placeholder_summary 
            })
        else:
            logging.error(f"FAILURE: Could not create summary file at {summary_filepath}. Transcript file might have been created.")
            failed_to_create_files_count += 1
            # Transcript file might exist, but summary failed. Still counts as a failure to complete the pair.

    logging.info(f"--- Processing finished for playlist '{raw_playlist_title}' ---")
    logging.info(f"Stats: Total: {total_videos}, Processed (files created): {processed_count}, Skipped (already exists): {skipped_count}, Failed (file creation issue): {failed_to_create_files_count}")
    print(f"\n--- Verarbeitung für Playlist '{raw_playlist_title}' abgeschlossen ---")
    print(f"Gesamt: {total_videos}, Verarbeitet (Dateien erstellt): {processed_count}, Übersprungen (existierte): {skipped_count}, Kritische Fehler (Dateierstellung): {failed_to_create_files_count}")


def update_master_summary_log():
    # ... (update_master_summary_log remains mostly the same, but uses the 'is_placeholder' flag)
    if not SUMMARIES_LOG_FOR_CURRENT_RUN:
        logging.info("No new summaries generated in this run to add to the master log.")
        return

    master_log_filepath = config.OUTPUT_DIR / "master_summary_log.md"
    logging.info(f"Updating master summary log: {master_log_filepath}")

    today_date = datetime.now().strftime("%Y-%m-%d")
    new_entries_md = f"## Processed on {today_date}\n\n"
    for item in SUMMARIES_LOG_FOR_CURRENT_RUN:
        placeholder_indicator = ""
        if item.get("is_placeholder"):
            placeholder_indicator = " (Placeholder - check content)" # General placeholder note
        
        new_entries_md += f"- **{item['playlist_context']} / {item['video_title']}**{placeholder_indicator}: [[{item['link_target']}]]\n"
    new_entries_md += "\n---\n\n"

    existing_content = ""
    if master_log_filepath.exists():
        try: existing_content = master_log_filepath.read_text(encoding="utf-8")
        except Exception as e: logging.error(f"Error reading existing master summary log {master_log_filepath}: {e}")
    try:
        with open(master_log_filepath, "w", encoding="utf-8") as f:
            f.write(new_entries_md); f.write(existing_content)
        logging.info(f"Master summary log updated successfully. Added {len(SUMMARIES_LOG_FOR_CURRENT_RUN)} entries.")
        print(f"Master summary log '{master_log_filepath.name}' updated with {len(SUMMARIES_LOG_FOR_CURRENT_RUN)} new entries.")
    except Exception as e:
        logging.error(f"Error writing to master summary log {master_log_filepath}: {e}")
        print(f"FEHLER: Master summary log konnte nicht geschrieben werden: {e}")
    
    SUMMARIES_LOG_FOR_CURRENT_RUN.clear()


if __name__ == "__main__":
    # ... (if __name__ == "__main__" block remains the same)
    setup_logging() 
    logging.debug("--- MAIN SCRIPT EXECUTION STARTED ---")
    SUMMARIES_LOG_FOR_CURRENT_RUN.clear()
    playlist_urls_from_file = []
    try:
        with open(config.PLAYLIST_URL_FILE, "r", encoding="utf-8") as f:
            for line in f:
                url = line.strip()
                if url and not url.startswith("#"): playlist_urls_from_file.append(url)
        if not playlist_urls_from_file:
            logging.critical(f"Error: No valid playlist URLs found in '{config.PLAYLIST_URL_FILE}'."); sys.exit(1)
        logging.info(f"{len(playlist_urls_from_file)} playlist URL(s) read.")
    except FileNotFoundError:
        logging.critical(f"CRITICAL ERROR: Playlist URL file not found: '{config.PLAYLIST_URL_FILE}'.", exc_info=True); sys.exit(1)
    except Exception as e:
        logging.critical(f"CRITICAL ERROR: Failed to read playlist URL file: {e}", exc_info=True); sys.exit(1)

    for i, playlist_url in enumerate(playlist_urls_from_file):
        logging.info(f"=== Starting processing for playlist {i+1}/{len(playlist_urls_from_file)}: {playlist_url} ===")
        print(f"\n======================================================================")
        print(f"Starte Verarbeitung für Playlist {i+1}/{len(playlist_urls_from_file)}: {playlist_url}")
        print(f"======================================================================")
        process_playlist(playlist_url)

    update_master_summary_log()
    logging.info("=== All specified playlists have been processed. Script finished. ===")
    print(f"\n======================================================================")
    print("Alle angegebenen Playlists wurden abgearbeitet.")
    print(f"======================================================================")
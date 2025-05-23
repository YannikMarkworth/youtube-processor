# === transcript_utils.py - Cleaned and Annotated ===

"""
Handles fetching video transcripts using the youtube-transcript-api library.
Prioritizes German and English transcripts.
"""

import time
import traceback
import logging
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import xml.etree.ElementTree # Wichtig für ParseError

# --- Main Transcript Fetching Function ---

def get_transcript(video_id):
    """
    Fetches the transcript for a given YouTube video ID, attempting to retrieve
    either German ('de') or English ('en') versions.
    Includes a retry mechanism for transient errors like ParseError.
    """
    preferred_langs = ['de', 'en']
    max_retries = 3  # Anzahl der Gesamtversuche (1 initial + 2 Wiederholungen)
    base_initial_delay = 2 # Sekunden Wartezeit vor jedem Versuch (wie zuvor)
    retry_specific_delay = 3 # Zusätzliche Sekunden Wartezeit zwischen den Wiederholungsversuchen

    logging.info(f"Attempting to fetch transcript for {video_id} (Preferred Langs: {preferred_langs}). Max attempts: {max_retries}")

    for attempt in range(max_retries):
        logging.debug(f"Transcript fetch attempt {attempt + 1}/{max_retries} for video {video_id}")
        try:
            # Grundlegende Wartezeit vor jedem Versuch
            logging.debug(f"Waiting for {base_initial_delay} seconds before API call (Attempt {attempt + 1})...")
            time.sleep(base_initial_delay)

            transcript_list_segments = YouTubeTranscriptApi.get_transcript(video_id, languages=preferred_langs)
            full_transcript = " ".join([segment['text'] for segment in transcript_list_segments])

            logging.info(f"Successfully fetched transcript for {video_id} on attempt {attempt + 1}.")
            print(f"Successfully fetched transcript for video: {video_id} (Attempt {attempt + 1})")
            return full_transcript

        except (TranscriptsDisabled, NoTranscriptFound) as e_known_negative:
            # Bei diesen Fehlern ist das Transkript definitiv nicht verfügbar oder nicht in den bevorzugten Sprachen.
            # Eine Wiederholung ist sinnlos.
            logging.warning(f"{type(e_known_negative).__name__} for video {video_id} on attempt {attempt + 1}: {e_known_negative}")
            print(f"Warning: {type(e_known_negative).__name__} for video {video_id}. {e_known_negative}")
            return None # Sofort beenden und None zurückgeben

        except xml.etree.ElementTree.ParseError as e_parse:
            logging.warning(
                f"XML ParseError on attempt {attempt + 1}/{max_retries} for {video_id}. Error: {e_parse}\n"
                f"Traceback (condensed for ParseError): {traceback.format_exc().splitlines()[-3:]}" # Loggt nur die relevantesten Teile des ParseError Tracebacks
            )
            if attempt < max_retries - 1:
                logging.info(f"Waiting {retry_specific_delay} seconds before retrying {video_id} due to ParseError...")
                time.sleep(retry_specific_delay)
                # Schleife wird fortgesetzt für den nächsten Versuch
            else:
                logging.error(f"Failed to fetch transcript for {video_id} after {max_retries} attempts due to persistent ParseError.")
                print(f"Error: XML ParseError for {video_id} after {max_retries} attempts. Check error_log.log.")
                return None # Nach allen Versuchen fehlgeschlagen

        except Exception as e_general:
            # Alle anderen unerwarteten Fehler
            logging.error(
                f"Unexpected error on attempt {attempt + 1}/{max_retries} for {video_id}. Error: {e_general}\n"
                f"Traceback: {traceback.format_exc()}"
            )
            if attempt < max_retries - 1:
                logging.info(f"Waiting {retry_specific_delay} seconds before retrying {video_id} due to unexpected error...")
                time.sleep(retry_specific_delay)
                # Schleife wird fortgesetzt für den nächsten Versuch
            else:
                logging.error(f"Failed to fetch transcript for {video_id} after {max_retries} attempts due to persistent unexpected error.")
                print(f"Error: Could not fetch transcript for {video_id} after {max_retries} attempts. Reason: {e_general}. Check error_log.log.")
                return None # Nach allen Versuchen fehlgeschlagen

    # Dieser Punkt sollte idealerweise nicht erreicht werden, wenn die Logik oben korrekt ist,
    # aber als Fallback geben wir None zurück.
    logging.error(f"Exited retry loop for {video_id} without success or explicit failure handling within loop.")
    return None

# --- Optional Testing Area ---
# This block only runs when the script is executed directly (python transcript_utils.py)
if __name__ == "__main__":
    # Configure basic logging for testing this module directly
    # Note: This might conflict slightly if run *after* main.py's logging is set,
    # but it's useful for isolated testing.
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    print("-" * 20)
    print("--- Running transcript_utils.py directly for testing ---")
    print("-" * 20)

    # Example Video IDs for testing different scenarios
    TEST_VIDEO_ID_WITH_TRANSCRIPT_EN = "dQw4w9WgXcQ" # Rick Astley (usually has 'en')
    TEST_VIDEO_ID_WITH_TRANSCRIPT_DE = "QO2m698NaLs" # Your German example video
    TEST_VIDEO_ID_WITHOUT_TRANSCRIPT = "klGadYn5p70" # Short test video (likely none)
    # TEST_VIDEO_ID_DISABLED = "VIDEO_ID_HERE" # Find one if needed

    # Test Case 1: English video
    print(f"\n--- Testing English Video: {TEST_VIDEO_ID_WITH_TRANSCRIPT_EN} ---")
    transcript1 = get_transcript(TEST_VIDEO_ID_WITH_TRANSCRIPT_EN)
    if transcript1:
        print("Transcript found (first 300 chars):")
        print(transcript1[:300] + "...")
    else:
        print("Transcript retrieval failed.")

    # Test Case 2: German video
    print(f"\n--- Testing German Video: {TEST_VIDEO_ID_WITH_TRANSCRIPT_DE} ---")
    transcript_de = get_transcript(TEST_VIDEO_ID_WITH_TRANSCRIPT_DE)
    if transcript_de:
        print("Transcript found (first 300 chars):")
        print(transcript_de[:300] + "...")
    else:
        print("Transcript retrieval failed.")

    # Test Case 3: Video likely without transcript
    print(f"\n--- Testing No Transcript Video: {TEST_VIDEO_ID_WITHOUT_TRANSCRIPT} ---")
    transcript2 = get_transcript(TEST_VIDEO_ID_WITHOUT_TRANSCRIPT)
    if transcript2:
        print("Transcript found unexpectedly:")
        print(transcript2[:300] + "...")
    else:
        print("Transcript retrieval failed (expected for this video).")

    # Test Case 4: Disabled (if you find an ID)
    # if TEST_VIDEO_ID_DISABLED != "VIDEO_ID_HERE":
    #     print(f"\n--- Testing Disabled Transcript Video: {TEST_VIDEO_ID_DISABLED} ---")
    #     transcript3 = get_transcript(TEST_VIDEO_ID_DISABLED)
    #     if not transcript3:
    #         print("Transcript retrieval failed (expected for disabled).")
    #     else:
    #          print("Transcript found unexpectedly.")


    print("\n--- Testing finished ---")
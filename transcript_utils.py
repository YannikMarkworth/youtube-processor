# === transcript_utils.py - Cleaned and Annotated ===

"""
Handles fetching video transcripts using the youtube-transcript-api library.
Prioritizes German and English transcripts.
"""

import logging
# Removed duplicate: import logging
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

# --- Main Transcript Fetching Function ---

def get_transcript(video_id):
    """
    Fetches the transcript for a given YouTube video ID, attempting to retrieve
    either German ('de') or English ('en') versions.

    It uses the youtube-transcript-api's built-in language preference mechanism.

    Args:
        video_id (str): The ID of the YouTube video.

    Returns:
        str | None: A string containing the full transcript text if found in 'de' or 'en',
                    otherwise None if fetching fails, transcripts are disabled, or
                    neither preferred language is found.
    """
    # Define preferred languages in order of preference for the API call.
    # Could potentially be moved to config if more flexibility is needed.
    preferred_langs = ['de', 'en']
    logging.info(f"Attempting to fetch transcript for {video_id} (Preferred Langs: {preferred_langs})...")
    print(f"Attempting fetch for {video_id} (Preferred Langs: {preferred_langs})...") # User feedback

    try:
        # Make the primary API call to get the transcript.
        # The 'languages' parameter tells the library to try finding a transcript
        # matching any language in the list, respecting the order.
        transcript_list_segments = YouTubeTranscriptApi.get_transcript(video_id, languages=preferred_langs)

        # If successful, join the 'text' parts of the returned segments.
        full_transcript = " ".join([segment['text'] for segment in transcript_list_segments])

        # --- Optional: Check which language was actually fetched ---
        # This block makes *another* API call just to log the specific language.
        # This is potentially inefficient (doubles API calls on success).
        # Consider removing or making conditional for production use if speed/quota is a concern.
        try:
            # List transcripts again and find the one matching the preference list
            actual_transcript_obj = YouTubeTranscriptApi.list_transcripts(video_id).find_transcript(preferred_langs)
            fetched_lang_info = f"'{actual_transcript_obj.language}' ({'manual' if not actual_transcript_obj.is_generated else 'generated'})"
            logging.info(f"Successfully fetched {fetched_lang_info} transcript for {video_id}")
            print(f"Successfully fetched {fetched_lang_info} transcript for video: {video_id}")
        except Exception as lang_check_e:
             # If the check fails for any reason, log it but continue with the transcript we already have
             logging.warning(f"Successfully fetched transcript for {video_id}, but couldn't verify exact language ({lang_check_e})")
             print(f"Successfully fetched transcript for video: {video_id} (language check skipped/failed)")
        # --- End Optional Language Check ---

        # Return the transcript text
        return full_transcript

    # --- Specific Exception Handling ---
    except TranscriptsDisabled:
        # Handle cases where transcripts are explicitly disabled by the video owner
        logging.warning(f"Transcripts are disabled for video {video_id}")
        print(f"Warning: Transcripts are disabled for video {video_id}")
        return None
    except NoTranscriptFound:
        # Handle cases where *neither* German nor English transcripts could be found
        logging.warning(f"No transcript found in preferred languages {preferred_langs} for video {video_id}")
        print(f"Warning: No transcript found in {preferred_langs} for video {video_id}")
        return None
    # --- Generic Exception Handling ---
    except Exception as e:
        # Handle any other unexpected errors (network issues, API changes, library bugs etc.)
        logging.error(f"An unexpected error occurred fetching transcript for {video_id}: {e}")
        print(f"Error: Could not fetch transcript for {video_id}. Reason: {e}")
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
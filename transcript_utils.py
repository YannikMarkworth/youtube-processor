import logging
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

def get_transcript(video_id):
    """
    Fetches a transcript using a multi-layered, resilient approach based on recent
    community-found solutions. Tries multiple language codes and fallback methods.
    """
    logging.info(f"Attempting to fetch transcript for {video_id} using resilient multi-layered approach.")

    # --- Language Variants to Try ---
    # We will try these in order, as YouTube is becoming more specific about language codes.
    german_variants = ['de', 'de-DE']
    english_variants = ['en', 'en-US', 'en-GB']
    preferred_variants = german_variants + english_variants

    # --- Method 1: Direct fetch using a list of preferred language variants ---
    # This is a fast first attempt.
    logging.debug(f"Method 1: Attempting direct fetch with variants {preferred_variants}")
    try:
        transcript_segments = YouTubeTranscriptApi.get_transcript(video_id, languages=preferred_variants)
        logging.info(f"Method 1 SUCCESS: Directly fetched a transcript for {video_id}.")
        print(f"Successfully fetched transcript for video: {video_id} (Direct Method)")
        full_transcript = " ".join([segment['text'] for segment in transcript_segments])
        return full_transcript
    except TranscriptsDisabled:
        logging.warning(f"Transcripts are disabled for video {video_id}. No further attempts will be made.")
        print(f"Warning: Transcripts are disabled for video {video_id}.")
        return None
    except NoTranscriptFound:
        logging.warning(f"Method 1 FAILED: No transcript found via direct fetch. Proceeding to Method 2.")
    except Exception as e:
        logging.warning(f"Method 1 FAILED with an unexpected error: {e}. Proceeding to Method 2.")


    # --- Method 2: List all available transcripts and manually find a match ---
    # This method is slower but more thorough.
    logging.debug("Method 2: Listing all available transcripts and searching manually.")
    try:
        # Use the modern, instance-based approach to be safe.
        yt_api = YouTubeTranscriptApi()
        transcript_list = yt_api.list(video_id)
        
        # 2a: Look for an exact match in our preferred variants
        for lang_code in preferred_variants:
            try:
                transcript = transcript_list.find_transcript([lang_code])
                logging.info(f"Method 2a SUCCESS: Found transcript via list-and-find for lang_code '{lang_code}'.")
                print(f"Successfully fetched transcript for video: {video_id} (List-and-Find Method)")
                transcript_segments = transcript.fetch()
                return " ".join([segment['text'] for segment in transcript_segments])
            except NoTranscriptFound:
                continue # This language code wasn't in the list, try the next one.
        
        # 2b: If no preferred language found, try to find ANY auto-generated transcript as a fallback.
        logging.debug("Method 2b: No preferred language found. Looking for any auto-generated transcript.")
        for transcript in transcript_list:
            if transcript.is_generated:
                logging.info(f"Method 2b SUCCESS: Found an auto-generated transcript in '{transcript.language_code}'.")
                print(f"Successfully fetched transcript for video: {video_id} (Auto-generated Fallback)")
                transcript_segments = transcript.fetch()
                return " ".join([segment['text'] for segment in transcript_segments])

        # 2c: If still nothing, just grab the very first transcript in the list as a last resort.
        logging.debug("Method 2c: No auto-generated one found. Grabbing the first available transcript in the list.")
        first_transcript = next(iter(transcript_list), None) # Safely get the first item or None
        if first_transcript:
            logging.info(f"Method 2c SUCCESS: Found a transcript in '{first_transcript.language_code}' as a final resort.")
            print(f"Successfully fetched transcript for video: {video_id} (First-Available Fallback)")
            transcript_segments = first_transcript.fetch()
            return " ".join([segment['text'] for segment in transcript_segments])

    except TranscriptsDisabled:
        logging.warning(f"Transcripts are disabled for video {video_id} (checked in Method 2).")
        print(f"Warning: Transcripts are disabled for video {video_id}.")
        return None
    except Exception as e:
        logging.error(f"Method 2 FAILED with an unexpected error: {e}", exc_info=True)
        print(f"Error: Could not retrieve transcript for {video_id}. Check the error_log.log file.")
        return None

    # If all methods have failed to return a value, this is the final failure.
    logging.error(f"All methods failed to retrieve a transcript for {video_id}.")
    return None
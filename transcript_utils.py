import logging
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from youtube_transcript_api.proxies import WebshareProxyConfig
import config # To get proxy credentials

def get_transcript(video_id):
    """
    Fetches a transcript using a rotating residential proxy to bypass YouTube's
    strict rate limiting, as recommended by the library author.
    """
    logging.info(f"Attempting to fetch transcript for {video_id} using Webshare proxy.")

    # --- Check for Proxy Credentials ---
    if not config.PROXY_USERNAME or not config.PROXY_PASSWORD:
        logging.error("PROXY_USERNAME or PROXY_PASSWORD not found in .env file. Cannot use proxy.")
        print("Error: Proxy credentials are not set in your .env file. Transcript fetching will fail.")
        return None

    try:
        # --- Configure the Proxy ---
        proxy_config = WebshareProxyConfig(
            proxy_username=config.PROXY_USERNAME,
            proxy_password=config.PROXY_PASSWORD
        )

        # --- Initialize the API with the Proxy Configuration ---
        # The library now knows to send all requests through your proxy.
        ytt_api = YouTubeTranscriptApi(proxy_config=proxy_config)

        # --- Fetch the transcript using the modern .fetch() method ---
        # As confirmed in the GitHub issue, a direct fetch is more reliable with a proxy.
        preferred_langs = ['de', 'en']
        fetched_transcript_object = ytt_api.fetch(video_id, languages=preferred_langs)
        
        logging.info(f"SUCCESS: Fetched transcript for {video_id} using proxy.")
        print(f"Successfully fetched transcript for video: {video_id} (Proxy Method)")
        
        # Convert the fetched transcript object into the simple text format our script needs.
        transcript_segments = fetched_transcript_object.to_raw_data()
        full_transcript = " ".join([segment['text'] for segment in transcript_segments])
        return full_transcript

    except TranscriptsDisabled:
        logging.warning(f"Transcripts are disabled for video {video_id}.")
        print(f"Warning: Transcripts are disabled for video {video_id}.")
        return None
    except NoTranscriptFound:
        logging.warning(f"No transcript found in preferred languages ('de', 'en') for {video_id}, even with proxy.")
        print(f"Warning: No German or English transcript found for {video_id}.")
        return None
    except Exception as e:
        # This will catch other errors, such as an invalid proxy login.
        logging.error(f"An unexpected error occurred while fetching transcript with proxy for {video_id}: {e}", exc_info=True)
        print(f"Error: An error occurred with the proxy or API: {e}")
        return None
# === youtube_utils.py - Cleaned and Annotated ===

"""
Utility functions for interacting with the YouTube Data API v3.

Provides functions to build the API service, fetch video items from a playlist,
and retrieve detailed metadata for specific videos using an API key.

Note: Functions requiring modification of YouTube data (like deleting playlist items)
would require OAuth 2.0 authentication, not just an API key. A placeholder
for building an authenticated service is included but not implemented.
"""

import config  # For YOUTUBE_API_KEY
import logging # For logging errors

# Import necessary Google API client library components
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --- Initial Check for API Key ---
# Stop immediately if the essential API key is missing from configuration.
if not config.YOUTUBE_API_KEY:
    # Raising an error might be preferable to just logging, as the module is unusable without a key.
    error_msg = "YouTube API Key not found. Please set YOUTUBE_API_KEY in your .env file."
    logging.critical(error_msg)
    raise ValueError(error_msg)

# --- YouTube Service Builders ---

def build_youtube_service():
    """
    Builds and returns the YouTube Data API service object using the API key.

    This service object is used for read-only operations like fetching playlists and video details.

    Returns:
        googleapiclient.discovery.Resource | None: The YouTube service object,
                                                 or None if building the service fails.
    """
    try:
        # Build the service resource object.
        # Arguments: API name ('youtube'), API version ('v3'), developerKey (your API key).
        youtube_service = build('youtube', 'v3', developerKey=config.YOUTUBE_API_KEY)
        logging.info("YouTube API service (read-only) created successfully.")
        print("YouTube service created successfully.") # User feedback
        return youtube_service
    except Exception as e:
        # Catch any potential errors during service initialization
        logging.critical(f"CRITICAL: Error building YouTube service: {e}", exc_info=True)
        print(f"Error: Could not build YouTube service. Reason: {e}")
        return None

# --- Placeholder for Authenticated Service (Needed for Playlist Modification) ---
# def build_authenticated_youtube_service():
#     """
#     (Not Implemented) Builds an OAuth 2.0 authenticated YouTube service object.
#
#     This would be required for actions like deleting playlist items.
#     It involves a more complex flow using client secrets, scopes, and user consent.
#     Libraries needed: google-auth-oauthlib, google-auth-httplib2
#
#     Returns:
#         googleapiclient.discovery.Resource | None: The authenticated service object.
#     """
#     logging.warning("Function build_authenticated_youtube_service is not implemented.")
#     # Implementation would involve:
#     # 1. Setting up OAuth credentials in Google Cloud Console.
#     # 2. Defining SCOPES (e.g., config.YOUTUBE_API_SCOPES).
#     # 3. Using google_auth_oauthlib.flow.InstalledAppFlow for user authorization.
#     # 4. Storing/refreshing credentials (e.g., in config.OAUTH_TOKEN_FILE).
#     # 5. Building the service with credentials: build('youtube', 'v3', credentials=credentials)
#     print("Error: Authenticated YouTube service function is not implemented.")
#     return None

# --- Data Fetching Functions ---

def get_playlist_video_items(youtube_service, playlist_id):
    """
    Fetches all video IDs and their corresponding playlist item IDs from a YouTube playlist.

    Handles pagination automatically to retrieve all items.

    Args:
        youtube_service (googleapiclient.discovery.Resource): The initialized YouTube service object.
        playlist_id (str): The ID of the target YouTube playlist (e.g., 'PL...').

    Returns:
        list[tuple[str, str]]: A list of tuples, where each tuple is (video_id, playlist_item_id).
                                Returns an empty list if an error occurs, the playlist is empty,
                                or the service object is invalid.
    """
    # Validate the service object input
    if not youtube_service:
        logging.error("get_playlist_video_items called with an invalid YouTube service object.")
        return []

    video_items = []
    next_page_token = None # Initialize page token for pagination

    logging.info(f"Fetching video items from playlist: {playlist_id}...")
    print(f"Fetching videos from playlist: {playlist_id}...") # User feedback

    try:
        # Loop until all pages of results have been fetched
        while True:
            # Construct the API request for playlist items
            request = youtube_service.playlistItems().list(
                part="contentDetails,id", # Request 'contentDetails' for videoId, 'id' for playlistItemId
                playlistId=playlist_id,
                maxResults=50,          # Request the maximum allowed items per page
                pageToken=next_page_token # Provide the token for the next page (if any)
            )
            # Execute the request
            response = request.execute()

            # Process the items found on the current page
            for item in response.get("items", []):
                # Safely get videoId from nested dictionary
                video_id = item.get("contentDetails", {}).get("videoId")
                # Get the unique ID of the item *within this playlist* (needed for deletion)
                playlist_item_id = item.get("id")
                # Ensure both IDs were found before adding
                if video_id and playlist_item_id:
                    video_items.append((video_id, playlist_item_id))

            # Get the token for the *next* page of results
            next_page_token = response.get("nextPageToken")
            # If there's no next page token, we've fetched all items, exit the loop
            if not next_page_token:
                break

        logging.info(f"Found {len(video_items)} video items in playlist {playlist_id}.")
        print(f"Found {len(video_items)} videos in the playlist.") # User feedback
        return video_items

    # --- Error Handling for API Calls ---
    except HttpError as e:
        # Handle specific API errors (e.g., 403 Forbidden - quota/key issue, 404 Not Found - bad ID)
        # Note: Quota errors often return 403. Rate limit errors are often 429.
        logging.error(f"YouTube API HTTP error {e.resp.status} fetching playlist items ({playlist_id}): {e.content}", exc_info=True)
        print(f"Error fetching playlist items: YouTube API Error {e.resp.status}. Check API key, quota, and playlist ID.")
        return [] # Return empty list on API error
    except Exception as e:
        # Handle any other unexpected errors during the API interaction
        logging.error(f"Unexpected error fetching playlist items ({playlist_id}): {e}", exc_info=True)
        print(f"An unexpected error occurred while fetching playlist items: {e}")
        return []

def get_video_details(youtube_service, video_id):
    """
    Fetches detailed metadata for a specific video ID.

    Requests snippet (title, description, channel, dates) and contentDetails (duration).

    Args:
        youtube_service (googleapiclient.discovery.Resource): The initialized YouTube service object.
        video_id (str): The ID of the target YouTube video.

    Returns:
        dict | None: A dictionary containing key video metadata, or None if an error occurs
                     or the video is not found/accessible.
    """
     # Validate the service object input
    if not youtube_service:
        logging.error("get_video_details called with an invalid YouTube service object.")
        return None

    logging.info(f"Fetching details for video ID: {video_id}...")
    print(f"Fetching details for video: {video_id}...") # User feedback

    try:
        # Construct the API request for video details
        request = youtube_service.videos().list(
            part="snippet,contentDetails", # Request snippet and contentDetails parts
            id=video_id                 # Specify the video ID
        )
        # Execute the request
        response = request.execute()

        # Check if the response contains any items (video might be deleted, private, etc.)
        if not response.get("items"):
            logging.warning(f"Video details not found for ID {video_id} (maybe private or deleted?).")
            print(f"Warning: Video {video_id} not found or access denied.")
            return None

        # Extract data from the first (and only) item in the response
        video_item = response["items"][0]
        snippet = video_item.get("snippet", {})           # Safely get snippet dict
        content_details = video_item.get("contentDetails", {}) # Safely get contentDetails dict

        # Assemble the dictionary of details we care about
        details = {
            "title": snippet.get("title", "No Title Provided"),
            "description": snippet.get("description", ""),
            "publishedAt": snippet.get("publishedAt"), # ISO 8601 format timestamp (string)
            "channelTitle": snippet.get("channelTitle", "Unknown Channel"),
            "channelId": snippet.get("channelId"),       # Added based on previous request
            "duration": content_details.get("duration"), # ISO 8601 duration format (string, e.g., "PT11M58S")
            "videoId": video_id,                     # Include the ID itself for convenience
            "videoUrl": f"https://www.youtube.com/watch?v={video_id}" # Standard watch URL
        }
        logging.info(f"Successfully fetched details for video '{details['title']}' ({video_id}).")
        print(f"Successfully fetched details for '{details['title']}'.") # User feedback
        return details

    # --- Error Handling for API Calls ---
    except HttpError as e:
        logging.error(f"YouTube API HTTP error {e.resp.status} fetching video details ({video_id}): {e.content}", exc_info=True)
        print(f"Error fetching video details for {video_id}: YouTube API Error {e.resp.status}. Check video ID.")
        return None
    except Exception as e:
        logging.error(f"Unexpected error fetching video details ({video_id}): {e}", exc_info=True)
        print(f"An unexpected error occurred while fetching video details: {e}")
        return None

def get_playlist_details(youtube_service, playlist_id):
    """
    Fetches details for a specific playlist, primarily its title.

    Args:
        youtube_service (googleapiclient.discovery.Resource): The initialized YouTube service object.
        playlist_id (str): The ID of the target YouTube playlist.

    Returns:
        dict | None: A dictionary containing playlist details (e.g., {'title': 'Playlist Title', 'id': 'playlist_id'}),
                     or None if an error occurs or details can't be fetched.
                     Returns a default title if fetching fails but an ID is provided.
    """
    if not youtube_service:
        logging.error("get_playlist_details called with an invalid YouTube service object.")
        return None
    
    if not playlist_id:
        logging.error("get_playlist_details called with no playlist_id.")
        return None

    logging.info(f"Fetching details for playlist ID: {playlist_id}...")
    try:
        request = youtube_service.playlists().list(
            part="snippet",  # 'snippet' contains title, description, etc.
            id=playlist_id,
            maxResults=1 # We only expect one playlist for a given ID
        )
        response = request.execute()

        if response.get("items"):
            playlist_data = response["items"][0].get("snippet", {})
            playlist_title = playlist_data.get("title", "Unnamed Playlist") # Default if title somehow missing
            logging.info(f"Successfully fetched details for playlist ID {playlist_id}. Title: '{playlist_title}'")
            return {"title": playlist_title, "id": playlist_id}
        else:
            logging.warning(f"No details found for playlist ID {playlist_id} (playlist might be empty, private, or deleted).")
            # Return a dictionary with a placeholder title so the main script can still proceed
            return {"title": "Unknown Playlist (Not Found or Inaccessible)", "id": playlist_id}
            
    except HttpError as e:
        logging.error(f"YouTube API HTTP error {e.resp.status} fetching playlist details for ID '{playlist_id}': {e.content}", exc_info=True)
        print(f"API Error: Could not fetch details for playlist ID '{playlist_id}'. HTTP Status: {e.resp.status}.")
        return {"title": "Unknown Playlist (API Error)", "id": playlist_id} # Default on API error
    except Exception as e:
        logging.error(f"Unexpected error fetching playlist details for ID '{playlist_id}': {e}", exc_info=True)
        return {"title": "Unknown Playlist (Unexpected Error)", "id": playlist_id} # Default on other errors

# --- Testing Area ---
# This block only runs when youtube_utils.py is executed directly
if __name__ == "__main__":
    print("-" * 20)
    print("--- Running youtube_utils.py directly for testing ---")
    print("-" * 20)

    # Configure logging just for this test run
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    # --- !!! IMPORTANT: Replace with a valid Playlist ID for testing !!! ---
    # Use a shorter playlist for quicker testing if possible.
    TEST_PLAYLIST_ID = "PLXXXXXXXXXXXXXXXXX" # <-- REPLACE THIS!

    # Basic checks before proceeding
    if not config.YOUTUBE_API_KEY:
        print("Testing stopped: YouTube API Key is missing in .env file.")
    # Use the actual placeholder string in the check
    elif TEST_PLAYLIST_ID == "PLXXXXXXXXXXXXXXXXX":
         print("Testing stopped: Please replace 'PLXXXXXXXXXXXXXXXXX' with an actual Playlist ID in the test code below.")
    else:
        # Step 1: Build the YouTube service object
        print("\nStep 1: Building YouTube Service...")
        youtube_service = build_youtube_service()

        if youtube_service:
            # Step 2: Get items from the test playlist
            print(f"\nStep 2: Fetching items from Playlist ID: {TEST_PLAYLIST_ID}...")
            playlist_items = get_playlist_video_items(youtube_service, TEST_PLAYLIST_ID)

            if playlist_items:
                print(f"\nResult: Found {len(playlist_items)} items.")
                # Print details for the first few items
                print("First few items found:")
                for i, item_tuple in enumerate(playlist_items[:5]):
                    print(f"  {i+1}. Video ID: {item_tuple[0]}, Playlist Item ID: {item_tuple[1]}")
                if len(playlist_items) > 5: print("  ...")

                # Step 3: Get details for the first video found
                first_video_id = playlist_items[0][0] # Get video ID from the first tuple (index 0, element 0)
                print(f"\nStep 3: Fetching details for the first video (ID: {first_video_id})...")
                video_details = get_video_details(youtube_service, first_video_id)

                if video_details:
                    print("\nResult: Video Details Fetched Successfully:")
                    # Print the details dictionary nicely
                    for key, value in video_details.items():
                        # Truncate long descriptions for cleaner test output
                        if key == 'description' and isinstance(value, str) and len(value) > 150:
                            print(f"  - {key}: {value[:150].replace(chr(10), ' ')}...") # Replace newlines in snippet
                        else:
                            print(f"  - {key}: {value}")
                else:
                    print(f"Result: Failed to get details for video {first_video_id}.")
            else:
                print(f"Result: Could not retrieve any items from playlist {TEST_PLAYLIST_ID}.")
                print("Check if the playlist ID is correct, public, and the API key has permissions.")
        else:
            print("Result: Failed to build YouTube service. Cannot proceed with tests.")
            print("Check API key configuration and network connection.")

    print("\n--- Testing finished ---")
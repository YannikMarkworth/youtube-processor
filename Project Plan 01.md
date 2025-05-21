Okay, let's design and outline the Python code for this YouTube Processing Tool.

This task involves several distinct parts: interacting with YouTube APIs, handling transcripts, calling an AI model, managing files, and robust error handling/logging.

**Core Libraries We'll Need:**

1.  `google-api-python-client`: For interacting with the YouTube Data API v3 (fetching playlist items, video details, *and crucially, removing playlist items*). This requires API keys and potentially OAuth 2.0 for modification actions.
2.  `google-auth-oauthlib` & `google-auth-httplib2`: Needed for OAuth 2.0 authentication if modifying playlists.
3.  `youtube-transcript-api`: A convenient library for fetching video transcripts.
4.  `openai` (or another AI library like `google-generativeai`): For interacting with the language model for summarization.
5.  `PyYAML`: For writing YAML metadata.
6.  Standard libraries: `os`, `logging`, `json` (for logs/tracking), `datetime`, `re` (for cleaning filenames), `argparse` (for command-line arguments).

**Project Structure:**

```
youtube-processor/
|-- main.py                 # Main script execution
|-- youtube_utils.py        # Functions for YouTube API interactions
|-- transcript_utils.py     # Functions for fetching transcripts
|-- ai_utils.py             # Functions for AI summarization
|-- file_utils.py           # Functions for Markdown generation and file handling
|-- config.py               # Configuration settings (API keys, paths - potentially use .env)
|-- summarization_prompt.txt # Prompt for the AI model
|-- processed_log.json      # Log of processed videos
|-- error_log.log           # Detailed error logging file
|-- credentials.json        # OAuth 2.0 credentials file (if modifying playlists)
|-- token.json              # OAuth 2.0 token file (generated after authorization)
|-- requirements.txt        # Python dependencies
|-- output/                 # Directory for generated Markdown files
    |-- transcripts/        # Folder for full transcript files
    |-- summaries/          # Folder for summary files
```

**Step-by-Step Implementation Outline:**

**1. Setup & Configuration (`config.py`, `requirements.txt`)**

* `requirements.txt`: List all necessary libraries.
    ```
    google-api-python-client
    google-auth-oauthlib
    google-auth-httplib2
    youtube-transcript-api
    openai
    PyYAML
    python-dotenv  # Optional, for .env file handling
    ```
* `config.py` (or use `.env` with `python-dotenv`):
    * `YOUTUBE_API_KEY`: Your Google Cloud API key with YouTube Data API v3 enabled.
    * `OPENAI_API_KEY`: Your OpenAI API key.
    * `OUTPUT_DIR`: Path to the main output directory (e.g., `"./output"`).
    * `TRANSCRIPTS_DIR`: Path relative to `OUTPUT_DIR` (e.g., `"transcripts"`).
    * `SUMMARIES_DIR`: Path relative to `OUTPUT_DIR` (e.g., `"summaries"`).
    * `PROMPT_FILE`: Path to `summarization_prompt.txt`.
    * `PROCESSED_LOG_FILE`: Path to `processed_log.json`.
    * `ERROR_LOG_FILE`: Path to `error_log.log`.
    * `OAUTH_CREDENTIALS_FILE`: Path to `credentials.json` (needed for playlist modification).
    * `OAUTH_TOKEN_FILE`: Path to `token.json`.
    * `YOUTUBE_API_SCOPES`: `["https://www.googleapis.com/auth/youtube.force-ssl"]` (Scope needed for playlist item deletion).

**2. Logging Setup (`main.py` or separate module)**

* Use the `logging` module.
* Configure basic logging to console and a detailed log to `error_log.log`.
* Include timestamps, log levels, and relevant context (like video ID).

**3. YouTube Interaction (`youtube_utils.py`)**

* **Authentication:**
    * Function to build the YouTube API service object using the API key (for read-only actions).
    * *Crucially:* Function to build an *authenticated* YouTube API service object using OAuth 2.0 flow (`google_auth_oauthlib`) for playlist modification. This will require user interaction the first time to grant permissions. Store the token in `token.json`. **This is the most complex part.**
* **`get_playlist_video_ids(youtube, playlist_id)`:**
    * Takes the YouTube service object and playlist ID.
    * Uses `YoutubelistItems().list()` repeatedly (handling `nextPageToken`) to fetch all video IDs (`contentDetails.videoId`) and playlist item IDs (`id` - needed for deletion) in the playlist.
    * Returns a list of tuples: `[(video_id, playlist_item_id), ...]`.
* **`get_video_details(youtube, video_id)`:**
    * Takes the YouTube service object and video ID.
    * Uses `youtube.videos().list()` with `part='snippet,contentDetails'`.
    * Extracts title, description, upload date (`snippet.publishedAt`), duration (`contentDetails.duration` - needs parsing ISO 8601 duration), channel title, etc.
    * Returns a dictionary of metadata.
* **`remove_video_from_playlist(youtube_authenticated, playlist_item_id)`:**
    * Takes the *OAuth authenticated* YouTube service object and the `playlist_item_id` (obtained from `get_playlist_video_ids`).
    * Uses `YoutubelistItems().delete(id=playlist_item_id)`.
    * Includes error handling (e.g., item not found, permissions error).

**4. Transcript Handling (`transcript_utils.py`)**

* **`get_transcript(video_id)`:**
    * Takes the video ID.
    * Uses `YouTubeTranscriptApi.get_transcript(video_id)` wrapped in a `try...except` block.
    * Handles `TranscriptsDisabled`, `NoTranscriptFound`, and other potential errors from the library.
    * Returns the transcript text (concatenated from segments) or `None` if unavailable.

**5. AI Summarization (`ai_utils.py`)**

* **`load_prompt(prompt_file_path)`:** Reads the prompt from `summarization_prompt.txt`.
* **`summarize_transcript(api_key, transcript, prompt)`:**
    * Takes OpenAI API key, transcript text, and the loaded prompt.
    * Initializes the OpenAI client.
    * Constructs the message/payload for the AI model (e.g., using ChatCompletion for GPT models). Combine the system prompt/instructions from the file with the user message containing the transcript.
    * Makes the API call.
    * Handles potential API errors (rate limits, connection issues).
    * Extracts and returns the summary text.

**6. File Generation & Handling (`file_utils.py`)**

* **`load_processed_log(log_file_path)`:** Reads `processed_log.json` (if it exists) into a dictionary or set for quick lookups. Handles file not found.
* **`save_processed_log(log_file_path, processed_data)`:** Writes the updated processed video data back to `processed_log.json`.
* **`clean_filename(title)`:** Creates a safe filename from the video title (remove invalid characters, limit length). Use `re`.
* **`create_markdown_files(output_dir, transcripts_dir, summaries_dir, video_details, transcript, summary)`:**
    * Takes paths, video metadata, transcript, and summary.
    * Creates `output/transcripts` and `output/summaries` directories if they don't exist (`os.makedirs(exist_ok=True)`).
    * Generates a clean filename based on the video title.
    * **Transcript File (`output/transcripts/filename.md`):**
        * Uses `PyYAML` to dump metadata (title, video_id, url, upload_date, duration, channel, etc.) as YAML frontmatter.
        * Appends the full transcript below the frontmatter.
    * **Summary File (`output/summaries/filename_summary.md`):**
        * Writes video URL (`https://www.youtube.com/watch?v=VIDEO_ID`).
        * Writes key metadata (title, date, duration).
        * Includes the AI-generated summary.
        * Adds an Obsidian link to the corresponding transcript file: `[[filename]]` (ensure the link matches the transcript filename *without* the extension if your Obsidian vault is set up that way, or `[[filename.md]]`).
    * Handles file writing errors.

**7. Main Execution Logic (`main.py`)**

* **Setup:**
    * Import necessary modules and config.
    * Set up logging.
    * Use `argparse` to get the YouTube Playlist URL (and potentially override config paths).
    * Create output directories.
* **Load State:**
    * Load the processed video log using `file_utils.load_processed_log`. Store processed video IDs in a set for efficient checking: `processed_video_ids`.
    * Load the AI summarization prompt using `ai_utils.load_prompt`.
* **Initialize APIs:**
    * Build the read-only YouTube service object using `youtube_utils` and the API key.
    * *Conditional:* If playlist modification is intended, build the OAuth-authenticated YouTube service object. Handle the initial authorization flow if `token.json` is missing/invalid. This might require user interaction in the console.
* **Extract Playlist Info:**
    * Parse the playlist ID from the input URL.
    * Call `youtube_utils.get_playlist_video_ids` to get the list of `(video_id, playlist_item_id)`.
* **Processing Loop:**
    * Initialize lists/dictionaries for tracking: `successfully_processed = []`, `failed_to_process = {}`.
    * Iterate through `(video_id, playlist_item_id)` from the playlist:
        * **Check if already processed:** `if video_id in processed_video_ids: continue`
        * **Start Try Block:** Wrap the processing for this video in a `try...except` block.
        * Log processing start for `video_id`.
        * **Get Video Details:** Call `youtube_utils.get_video_details`. Handle potential `HttpError` (e.g., video not found, private). If error, log and add to `failed_to_process`, then `continue`.
        * **Get Transcript:** Call `transcript_utils.get_transcript`. If `None` (transcript unavailable), log warning, add to `failed_to_process` with reason "No transcript", and `continue`.
        * **Summarize:** Call `ai_utils.summarize_transcript`. Handle potential AI API errors. If error, log, add to `failed_to_process`, and `continue`.
        * **Generate Files:** Call `file_utils.create_markdown_files`. Handle potential file writing errors. If error, log, add to `failed_to_process`, and `continue`.
        * **Record Success:**
            * Log success for `video_id`.
            * Add `video_id` to `processed_video_ids` set.
            * Add `{'video_id': video_id, 'playlist_item_id': playlist_item_id, 'title': video_details['title'], 'processed_at': datetime.now().isoformat()}` to the `successfully_processed` list.
        * **Catch Block:**
            * Catch specific exceptions (`HttpError`, transcript errors, AI errors, `FileNotFoundError`, etc.).
            * Log the error with `video_id`.
            * Add `video_id` to `failed_to_process` dictionary with the error message/type.
            * Catch generic `Exception` as a fallback, log it.
* **Post-Processing:**
    * **Update Processed Log:** Add the details from `successfully_processed` to the data structure loaded initially and save it back using `file_utils.save_processed_log`.
    * **Playlist Cleanup (Optional but requested):**
        * Check if the authenticated YouTube service object exists (i.e., OAuth was successful).
        * If yes, iterate through the `successfully_processed` list.
        * For each `playlist_item_id`, call `youtube_utils.remove_video_from_playlist`. Wrap this in a `try...except` as removal might fail (permissions, quota, item already gone). Log success or failure of removal.
    * **Report Failures:** Log a summary of videos that failed processing (from `failed_to_process` dictionary). These might need manual review or retry logic in a future version.

**Example `summarization_prompt.txt`:**

```
You are an expert assistant tasked with summarizing video transcripts.
Analyze the following transcript and provide a concise summary (3-5 bullet points or a short paragraph) capturing the main topics, key arguments, or conclusions presented in the video. Focus on the core information content.

Transcript:
"""
{transcript}
"""

Summary:
```

**Error Handling Considerations:**

* **API Quotas:** YouTube Data API has quotas. Implement backoff/retry logic or simply expect `HttpError` related to quotas and log them. AI APIs also have rate limits.
* **Authentication Errors:** Handle invalid API keys and OAuth token issues gracefully.
* **Network Issues:** Wrap API calls in `try...except` for connection errors.
* **Video Availability:** Videos might be private, deleted, or region-locked. The API calls should handle these, resulting in errors to be logged.
* **Missing Transcripts:** Explicitly handle cases where transcripts are disabled or unavailable using `youtube-transcript-api`'s exceptions.
* **File System Errors:** Handle potential errors during directory creation or file writing (e.g., permissions issues, disk full).

**Record Keeping (`processed_log.json`):**

A simple structure could be a dictionary where keys are video IDs:

```json
{
  "VIDEO_ID_1": {
    "title": "Video Title 1",
    "playlist_item_id": "PLAYLIST_ITEM_ID_1",
    "processed_at": "2025-04-04T18:30:00Z",
    "status": "processed",
    "summary_file": "output/summaries/video-title-1_summary.md",
    "transcript_file": "output/transcripts/video-title-1.md"
  },
  "VIDEO_ID_2": {
    "title": "Video Title 2",
    "playlist_item_id": "PLAYLIST_ITEM_ID_2",
    "processed_at": "2025-04-04T18:35:15Z",
    "status": "failed",
    "error": "No transcript found"
  }
  // ... more entries
}
```
This log helps skip already processed videos and track failures.

This detailed outline provides a solid foundation for building the YouTube Processing Tool. Remember that implementing the OAuth 2.0 flow for playlist modification is a significant step requiring careful handling of credentials and user authorization.
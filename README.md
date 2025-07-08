# YouTube Playlist Processor

## Description

This Python-based application processes a YouTube playlist, retrieves video details and full transcripts, generates AI-powered summaries for each video, and saves the information into structured Markdown files suitable for review and referencing, especially within knowledge management tools like Obsidian.

Due to recent changes in YouTube's rate-limiting policies, this script now **requires the use of a rotating residential proxy** to reliably fetch video transcripts.

## Features

  * **Playlist Processing:** Reads a target YouTube playlist URL from a text file.
  * **Video Data Retrieval:** Fetches essential metadata (title, description, channel info, duration, upload date, IDs) for each video using the YouTube Data API v3.
  * **Transcript Fetching via Proxy:** Retrieves full video transcripts using `youtube-transcript-api`, sending requests through a required rotating residential proxy to avoid rate-limiting errors.
  * **AI Summarization:**
      * Generates concise summaries using an OpenAI model (configurable, e.g., GPT-4o-mini, GPT-4-turbo).
      * Uses configurable prompts for summarization (separate prompts for chunking vs. final summarization).
      * Handles long transcripts automatically via a token-based chunking (map-reduce) strategy.
      * Passes video title to the AI for better context.
      * Allows configuration of model name, context limit, max output tokens, and temperature via `.env`.
  * **Markdown Generation:** For each video, creates structured transcript and summary files with metadata and links suitable for Obsidian.
  * **File-Based Skipping:** Checks for the existence of summary files to avoid reprocessing completed videos.
  * **Configurable:** Uses a `.env` file for API keys, proxy credentials, and AI parameters.
  * **Logging:** Logs progress and errors to both the console and a file (`error_log.log`).

## How It Works

1.  **Initialization:** Loads configuration (API keys, AI settings, paths) from `.env` and `config.py`. Sets up logging. Reads the target playlist URL from `playlist_url.txt`. Loads AI prompt templates.
2.  **Playlist Fetching:** Retrieves the list of video IDs contained within the specified YouTube playlist.
3.  **Video Iteration:** Loops through each video ID in the playlist.
4.  **Skip Check:** Determines the expected summary filename and checks if it already exists in the `output/summaries/` directory. If it exists, the video is skipped.
5.  **Data Fetching (if not skipped):**
      * Fetches video metadata (title, description, channel ID etc.) from the YouTube API.
      * Determines expected transcript filename. Checks if it exists.
      * If transcript file exists, it reads the content.
      * If not, it fetches the transcript from the API (prioritizing DE/EN) and saves it to the transcript file.
6.  **Summarization (if transcript available):**
      * Calculates required tokens for the transcript, prompt, and title.
      * Compares against the configured model's context limit threshold.
      * If within the limit, it sends the full transcript, title, and final prompt template to the configured OpenAI model.
      * If over the limit, it splits the transcript into token-based chunks, sends each chunk with the title and chunk prompt template to OpenAI, combines the chunk summaries, and sends the combined summaries with the title and final prompt template to OpenAI for a final summary.
7.  **File Saving (if summary generated):** Saves the generated summary (along with metadata and links) to the summary Markdown file.

## Setup Instructions

1.  **Prerequisites:**

      * Python 3.9 or higher installed.
      * Access to a terminal or command line.

2.  **Get the Code:** Clone this repository or download the source files into a directory.

3.  **Create and Activate Virtual Environment:** Open a terminal in the project directory and run:

    ```bash
    # Create the environment
    python3 -m venv venv
    # Activate the environment (macOS/Linux)
    source venv/bin/activate
    ```

4.  **Install Dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

5.  **API Keys & Configuration (`.env` file):**

      * Create a file named `.env` in the project root.
      * Add your API keys:
        ```
        YOUTUBE_API_KEY="your_google_cloud_api_key"
        OPENAI_API_KEY="your_openai_api_key"
        ```

6.  **Proxy Configuration (Required for Transcript Fetching):**

      * **Get a Proxy Subscription:** This script requires a **Rotating Residential Proxy** to function. The library has built-in support for [Webshare.io](http://webshare.io/). You must purchase a "Rotating Residential" plan. *Do not* use "Proxy Server" or "Static Residential" plans.
      * **Find Your Credentials:** In your Webshare account dashboard, find your **Proxy Username** and **Proxy Password**.
      * **Add Credentials to `.env` File:** Add your credentials to the `.env` file:
        ```
        PROXY_USERNAME="your_webshare_username_here"
        PROXY_PASSWORD="your_webshare_password_here"
        ```

7.  **Input File:**

      * Create `playlist_url.txt` in the project root and paste the full URL of the YouTube playlist you want to process.

## Usage

1.  **Activate Environment:** Ensure your virtual environment is active in your terminal (`source venv/bin/activate`).
2.  **Run the Script:**
    ```bash
    python main.py
    ```
3.  **Output:** Generated Markdown files will appear in the `output/transcripts/` and `output/summaries/` directories.

## Troubleshooting

  * **`ModuleNotFoundError`:** Make sure your virtual environment (`venv`) is activated before running `pip install` or `python main.py`.
  * **`FileNotFoundError` for `playlist_url.txt` or prompt files:** Ensure the files exist in the correct location (project root) and that the filenames in `config.py` match the actual filenames.
  * **YouTube API Errors (`HttpError 403`, `404`):** Check your `YOUTUBE_API_KEY` in `.env`. Ensure the YouTube Data API v3 is enabled in your Google Cloud project and that the playlist URL is correct.
  * **`429 Client Error: Too Many Requests`:** This error means you are being rate-limited by YouTube. You **must** correctly configure a rotating residential proxy as described in Step 6 of the "Setup Instructions." Simple delays are no longer sufficient to fix this. Check that your `PROXY_USERNAME` and `PROXY_PASSWORD` are correct in the `.env` file.
  * **OpenAI API Errors (`AuthenticationError`, `RateLimitError`, `ContextLengthError`):** Check your `OPENAI_API_KEY` in `.env` and your account usage limits. Ensure `OPENAI_CONTEXT_LIMIT` in `.env` matches your selected model.
  * **Permission Errors:** Ensure the script has write permissions for the `output` directory and the `error_log.log` file.

## Future Enhancements / To-Do

  * **Record Keeping:** Implement a persistent log (`processed_log.json`) to track processed/failed videos more robustly and potentially allow selective retries based on failure type.
  * **Playlist Management:** Implement OAuth 2.0 authentication to allow the script to automatically remove successfully processed videos from the source YouTube playlist.
  * **More Sophisticated Chunking:** Explore hierarchical summarization for extremely long content where combined chunk summaries still exceed context limits.
  * **Configuration Validation:** Add more explicit validation for `.env` values in `config.py`.
  * **GUI:** Create a graphical user interface for easier use.
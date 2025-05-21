# YouTube Playlist Processor

## Description

This Python-based application processes a YouTube playlist, retrieves video details and full transcripts, generates AI-powered summaries for each video, and saves the information into structured Markdown files suitable for review and referencing, especially within knowledge management tools like Obsidian.

It handles potentially long transcripts by implementing automatic chunking for AI summarization and allows for flexible configuration of AI models and parameters. The processing logic checks for existing output files to avoid redundant work.

## Features

* **Playlist Processing:** Reads a target YouTube playlist URL from a text file.
* **Video Data Retrieval:** Fetches essential metadata (title, description, channel info, duration, upload date, IDs) for each video using the YouTube Data API v3.
* **Transcript Fetching:** Retrieves full video transcripts using `youtube-transcript-api`, prioritizing German and English languages.
* **AI Summarization:**
    * Generates concise summaries using an OpenAI model (configurable, e.g., GPT-4o-mini, GPT-4-turbo).
    * Uses configurable prompts for summarization (separate prompts for chunking vs. final summarization).
    * Handles long transcripts automatically via a token-based chunking (map-reduce) strategy.
    * Passes video title to the AI for better context.
    * Allows configuration of model name, context limit, max output tokens, and temperature via `.env`.
* **Markdown Generation:** For each video, creates:
    * A full transcript file (`.md`) in `output/transcripts/` with YAML frontmatter containing metadata (including description and channel ID).
    * A summary file (`.md`) in `output/summaries/` containing key metadata (with channel name as an Obsidian link), the AI-generated summary, and an Obsidian link (`[[...]]`) to the corresponding transcript file.
* **File-Based Skipping:** Checks for the existence of the summary file to avoid reprocessing videos that have already been completed. Summary regeneration can be triggered by deleting the specific summary file.
* **Configurable:** Uses a `.env` file for API keys and AI parameters, and `config.py` for defaults and paths.
* **Logging:** Logs progress and errors to both the console and a file (`error_log.log`).

## How It Works

1.  **Initialization:** Loads configuration (API keys, AI settings, paths) from `.env` and `config.py`. Sets up logging. Reads the target playlist URL from `playlist_url.txt`. Loads AI prompt templates.
2.  **Playlist Fetching:** Retrieves the list of video IDs contained within the specified YouTube playlist.
3.  **Video Iteration:** Loops through each video ID in the playlist.
4.  **Skip Check:** Determines the expected summary filename (based on video ID) and checks if it already exists in the `output/summaries/` directory. If it exists, the video is skipped.
5.  **Data Fetching (if not skipped):**
    * Fetches video metadata (title, description, channel ID etc.) from the YouTube API.
    * Determines expected transcript filename. Checks if it exists.
    * If transcript file exists, reads content.
    * If not, fetches transcript from API (prioritizing DE/EN) and saves it to the transcript file.
6.  **Summarization (if transcript available):**
    * Calculates required tokens for the transcript + prompt + title.
    * Compares against the configured model's context limit threshold.
    * If within limit: Sends full transcript + title + final prompt template to the configured OpenAI model.
    * If over limit: Splits transcript into token-based chunks. Sends each chunk + title + chunk prompt template to OpenAI. Combines chunk summaries. Sends combined summaries + title + final prompt template to OpenAI for a final summary.
7.  **File Saving (if summary generated):** Saves the generated summary (along with metadata and links) to the summary Markdown file.

## Setup Instructions

1.  **Prerequisites:**
    * Python 3.9 or higher installed.
    * Access to a terminal or command line.
    * Git (optional, for version control).

2.  **Get the Code:** Clone this repository or download the source files into a directory (e.g., `youtube-processor`).

3.  **Create Virtual Environment:** Open a terminal, navigate into the project directory (`cd youtube-processor`), and create a Python virtual environment:
    ```bash
    python3 -m venv venv
    ```

4.  **Activate Virtual Environment:**
    * macOS/Linux: `source venv/bin/activate`
    * Windows (cmd): `venv\Scripts\activate`
    * Windows (PowerShell/GitBash): `venv\Scripts\Activate.ps1` or `. venv/Scripts/activate`
    * *(You should see `(venv)` at the beginning of your terminal prompt).*

5.  **Install Dependencies:** Install the required Python libraries:
    ```bash
    pip install -r requirements.txt
    ```

6.  **API Keys & Configuration (`.env`):**
    * Make a copy of `.env.example` (if provided) or create a new file named `.env` in the project root.
    * **Add your API keys:**
        * `YOUTUBE_API_KEY`: Get from Google Cloud Console (Enable YouTube Data API v3).
        * `OPENAI_API_KEY`: Get from OpenAI Platform (platform.openai.com).
    * **Configure AI Parameters (Optional Overrides):**
        * `OPENAI_MODEL_NAME`: Set the desired OpenAI model (e.g., `"gpt-4o-mini-2024-07-18"`, `"gpt-4-turbo"`). Defaults to the value in `config.py` if not set.
        * `OPENAI_CONTEXT_LIMIT`: **Important!** Set this to the known token limit of your chosen model (e.g., `"128000"` for `gpt-4-turbo` or `gpt-4o-mini`). Defaults to 4096 if not set.
        * `OPENAI_MAX_TOKENS`: Uncomment and set to control the maximum *output* length of the summary (e.g., `"2000"`). Defaults to the value in `config.py`.
        * `OPENAI_TEMPERATURE`: Uncomment and set (0.0-2.0) to control creativity. Defaults to the value in `config.py`.
    * **Ensure `.env` is listed in your `.gitignore` file!**

7.  **Prompt Files:**
    * Edit `summarize_chunk_prompt.txt`: Define a simple prompt for summarizing intermediate chunks. Must include `{input_text}` and `{video_title}` placeholders.
    * Edit `summarize_final_prompt.txt`: Add your detailed prompt for generating the final structured summary. Must include `{input_text}` and `{video_title}` placeholders.

8.  **Input File:**
    * Create `playlist_url.txt` in the project root.
    * Paste the **full URL** of the YouTube playlist you want to process onto the first line.

## Usage

1.  **Activate Environment:** Open your terminal, navigate to the project directory, and activate the virtual environment:
    ```bash
    source venv/bin/activate
    ```
    *(Ensure `(venv)` appears in your prompt).*

2.  **Run the Script:** Execute the main script:
    ```bash
    python main.py
    ```

3.  **Output:**
    * The script will print progress messages and logs to the console.
    * Detailed logs (including errors) are saved to `error_log.log`.
    * Generated Markdown files will appear in the `output/transcripts/` and `output/summaries/` directories. Files are named `VIDEO_ID_CleanedTitle.md` and `VIDEO_ID_CleanedTitle_summary.md`.
    * The script will skip videos for which a summary file matching the pattern `VIDEO_ID_*_summary.md` already exists. To re-summarize a video, delete its corresponding summary file from the `output/summaries/` directory before running the script again.

## Troubleshooting

* **`ModuleNotFoundError`:** Make sure your virtual environment (`venv`) is activated before running `pip install` or `python main.py`. Ensure all packages in `requirements.txt` were installed correctly. Check that VS Code is using the interpreter from the `venv`.
* **`FileNotFoundError` for `playlist_url.txt` or prompt files:** Ensure the files exist in the correct location (project root) and that the filenames in `config.py` match the actual filenames.
* **YouTube API Errors (`HttpError 403`, `404`):** Check your `YOUTUBE_API_KEY` in `.env`. Ensure the YouTube Data API v3 is enabled in your Google Cloud project. Check the playlist ID/URL is correct and the playlist is public or unlisted. Check API quotas.
* **OpenAI API Errors (`AuthenticationError`, `RateLimitError`, `ContextLengthError`):** Check your `OPENAI_API_KEY` in `.env`. Check your OpenAI account usage and rate limits. Ensure `OPENAI_CONTEXT_LIMIT` in `.env` matches your selected model. If context errors persist on long videos, you might need a model with an even larger context window or explore hierarchical summarization.
* **Permission Errors:** Ensure the script has write permissions for the `output` directory and the `error_log.log` file.

## Future Enhancements / To-Do

* **Record Keeping:** Implement a persistent log (`processed_log.json`) to track processed/failed videos more robustly and potentially allow selective retries based on failure type.
* **Playlist Management:** Implement OAuth 2.0 authentication to allow the script to automatically remove successfully processed videos from the source YouTube playlist.
* **More Sophisticated Chunking:** Explore hierarchical summarization for extremely long content where combined chunk summaries still exceed context limits.
* **Configuration Validation:** Add more explicit validation for `.env` values in `config.py`.
* **GUI:** Create a graphical user interface for easier use.

## License

(Optional: Add a license if desired, e.g., MIT License)
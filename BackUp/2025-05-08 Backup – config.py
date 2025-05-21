# === config.py - Cleaned and Annotated ===

"""
Configuration loading for the YouTube Processor application.

Reads API keys and configurable parameters from the .env file,
provides default values, performs necessary type conversions,
and defines essential file/directory paths.
"""

import os
import logging
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from the .env file into os.environ
# Searches for .env in the current directory or parent directories.
load_dotenv()

# --- API Keys ---
# Load API keys from environment variables (set in .env)
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- AI Model Configuration ---
# Define default values for AI parameters
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
DEFAULT_MAX_TOKENS = 1000   # Default max *output* tokens for the summary
DEFAULT_TEMPERATURE = 0.5  # Default creativity (0=deterministic, 1+=more random)
DEFAULT_CONTEXT_LIMIT = 4096 # Default model *input* context limit (used as fallback)

# Load Model Name from .env, use default if not set
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", DEFAULT_OPENAI_MODEL)

# Load Max Tokens: Check .env first, fall back to default, handle errors
try:
    max_tokens_str = os.getenv("OPENAI_MAX_TOKENS") # Value from .env is always a string
    if max_tokens_str:
        # If set in .env, try converting to integer
        OPENAI_MAX_TOKENS = int(max_tokens_str)
    else:
        # Not set in .env, use the default defined above
        OPENAI_MAX_TOKENS = DEFAULT_MAX_TOKENS
except (ValueError, TypeError):
    # Handle cases where the value in .env is not a valid integer
    logging.warning(f"Invalid OPENAI_MAX_TOKENS value '{max_tokens_str}' in .env. Using default: {DEFAULT_MAX_TOKENS}")
    OPENAI_MAX_TOKENS = DEFAULT_MAX_TOKENS

# Load Temperature: Check .env first, fall back to default, handle errors
try:
    temp_str = os.getenv("OPENAI_TEMPERATURE") # Value from .env is always a string
    if temp_str:
        # If set in .env, try converting to float
        OPENAI_TEMPERATURE = float(temp_str)
    else:
        # Not set in .env, use the default defined above
        OPENAI_TEMPERATURE = DEFAULT_TEMPERATURE
except (ValueError, TypeError):
    # Handle cases where the value in .env is not a valid float
    logging.warning(f"Invalid OPENAI_TEMPERATURE value '{temp_str}' in .env. Using default: {DEFAULT_TEMPERATURE}")
    OPENAI_TEMPERATURE = DEFAULT_TEMPERATURE

# Load Context Limit: Check .env first, fall back to default, handle errors
try:
    limit_str = os.getenv("OPENAI_CONTEXT_LIMIT") # Value from .env is always a string
    if limit_str:
        # If set in .env, try converting to integer
        OPENAI_CONTEXT_LIMIT = int(limit_str)
    else:
        # Not set in .env, use the default. Add specific warning for GPT-4/4o.
        if "gpt-4" in OPENAI_MODEL_NAME.lower() or "4o" in OPENAI_MODEL_NAME.lower():
             logging.warning(f"OPENAI_CONTEXT_LIMIT not set in .env for a GPT-4/4o model. Using default: {DEFAULT_CONTEXT_LIMIT}. Consider setting it to the model's actual limit (e.g., 128000) in .env for optimal performance.")
        OPENAI_CONTEXT_LIMIT = DEFAULT_CONTEXT_LIMIT
except (ValueError, TypeError):
    # Handle cases where the value in .env is not a valid integer
    logging.warning(f"Invalid OPENAI_CONTEXT_LIMIT value '{limit_str}' in .env. Using default: {DEFAULT_CONTEXT_LIMIT}")
    OPENAI_CONTEXT_LIMIT = DEFAULT_CONTEXT_LIMIT

# Log the final AI configuration being used for this run
logging.info(f"OpenAI Config: Model='{OPENAI_MODEL_NAME}', ContextLimit={OPENAI_CONTEXT_LIMIT}, MaxOutputTokens={OPENAI_MAX_TOKENS}, Temperature={OPENAI_TEMPERATURE}")


# --- File Paths ---
# Define the absolute base directory of the project (where this config file is located)
BASE_DIR = Path(__file__).resolve().parent

# Define output directories relative to the base directory
OUTPUT_DIR = Path("/Users/yannikmarkworth/Obsidian/Yannik/• YouTube-Importer")
TRANSCRIPTS_DIR = OUTPUT_DIR / "Transcripts"
SUMMARIES_DIR = OUTPUT_DIR / "Summaries"

# Ensure these output directories exist, create them if they don't
# parents=True creates parent directories if needed. exist_ok=True prevents errors if they already exist.
TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)


# --- File Names ---
# Define paths to specific configuration and log files relative to the base directory
PLAYLIST_URL_FILE = BASE_DIR / "playlist_url.txt" # Input file for playlist URL
CHUNK_PROMPT_FILE = BASE_DIR / "summarize_chunk_prompt.txt"  # Prompt for chunking step
FINAL_PROMPT_FILE = BASE_DIR / "summarize_final_prompt.txt"  # Prompt for final summary step
ERROR_LOG_FILE = BASE_DIR / "error_log.log"          # Main log file for errors/info
# PROCESSED_LOG_FILE = BASE_DIR / "processed_log.json" # Definition kept but commented out as logic was removed


# --- OAuth Configuration (Placeholder for potential future playlist modification) ---
# GOOGLE_CLIENT_SECRETS_FILE_NAME = os.getenv("GOOGLE_CLIENT_SECRETS_FILE")
# GOOGLE_CLIENT_SECRETS_FILE = BASE_DIR / GOOGLE_CLIENT_SECRETS_FILE_NAME if GOOGLE_CLIENT_SECRETS_FILE_NAME else None
# OAUTH_TOKEN_FILE = BASE_DIR / "token.json"
# YOUTUBE_API_SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]


# --- Basic Startup Checks (Optional) ---
# Example checks - uncomment and adapt if needed
# if not YOUTUBE_API_KEY:
#     logging.warning("YOUTUBE_API_KEY not found in environment variables (.env file).")
# if not OPENAI_API_KEY:
#     logging.warning("OPENAI_API_KEY not found in environment variables (.env file).")


# Indicate that configuration loading is complete (using logging)
logging.info("Configuration loaded. Output directories ensured.")
# Removed the print statement, using logging instead.
# === config.py - ADDING DEBUG PRINTS ===

import os
import logging
from dotenv import load_dotenv
from pathlib import Path

# Add print statements BEFORE logging might be fully configured
print("[CONFIG_DEBUG] config.py loading...")

# Load environment variables
print("[CONFIG_DEBUG] Calling load_dotenv()...")
load_dotenv()
print("[CONFIG_DEBUG] load_dotenv() finished.")

# --- API Keys ---
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
print(f"[CONFIG_DEBUG] Raw YOUTUBE_API_KEY from .env: {'Exists' if YOUTUBE_API_KEY else 'Not Found'}")
print(f"[CONFIG_DEBUG] Raw OPENAI_API_KEY from .env: {'Exists' if OPENAI_API_KEY else 'Not Found'}")


# --- AI Model Configuration ---
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
DEFAULT_MAX_TOKENS = 1000
DEFAULT_TEMPERATURE = 0.5
DEFAULT_CONTEXT_LIMIT = 4096

# --- Model Name ---
model_name_str = os.getenv("OPENAI_MODEL_NAME")
print(f"[CONFIG_DEBUG] Raw OPENAI_MODEL_NAME from .env: '{model_name_str}'")
# Strip quotes if present (best to fix .env, but this helps debugging)
if model_name_str and model_name_str.startswith('"') and model_name_str.endswith('"'):
    print("[CONFIG_DEBUG] Note: OPENAI_MODEL_NAME has quotes in .env.")
    OPENAI_MODEL_NAME = model_name_str.strip('"') or DEFAULT_OPENAI_MODEL
else:
    OPENAI_MODEL_NAME = model_name_str or DEFAULT_OPENAI_MODEL


# --- Max Tokens ---
OPENAI_MAX_TOKENS = DEFAULT_MAX_TOKENS # Start with default
max_tokens_str = os.getenv("OPENAI_MAX_TOKENS")
print(f"[CONFIG_DEBUG] Raw OPENAI_MAX_TOKENS from .env: '{max_tokens_str}' (Type: {type(max_tokens_str)})")
if max_tokens_str:
    try:
        # Strip potential whitespace before converting
        cleaned_max_tokens_str = max_tokens_str.strip()
        print(f"[CONFIG_DEBUG] Attempting int conversion for MAX_TOKENS: int('{cleaned_max_tokens_str}')")
        OPENAI_MAX_TOKENS = int(cleaned_max_tokens_str)
        print(f"[CONFIG_DEBUG] Successfully parsed OPENAI_MAX_TOKENS: {OPENAI_MAX_TOKENS}")
    except (ValueError, TypeError) as e:
        print(f"[CONFIG_DEBUG] ERROR parsing OPENAI_MAX_TOKENS: {e}. Falling back to default.")
        # Use logging here too, in case it works
        logging.warning(
            f"Invalid OPENAI_MAX_TOKENS value '{max_tokens_str}' in .env. Error: {e}. Using default: {DEFAULT_MAX_TOKENS}"
        )
        OPENAI_MAX_TOKENS = DEFAULT_MAX_TOKENS # Ensure default is set on error
else:
    print(f"[CONFIG_DEBUG] OPENAI_MAX_TOKENS not found in .env, using default: {DEFAULT_MAX_TOKENS}")


# --- Temperature ---
OPENAI_TEMPERATURE = DEFAULT_TEMPERATURE # Start with default
temp_str = os.getenv("OPENAI_TEMPERATURE")
print(f"[CONFIG_DEBUG] Raw OPENAI_TEMPERATURE from .env: '{temp_str}' (Type: {type(temp_str)})")
if temp_str:
    try:
        cleaned_temp_str = temp_str.strip()
        print(f"[CONFIG_DEBUG] Attempting float conversion for TEMPERATURE: float('{cleaned_temp_str}')")
        OPENAI_TEMPERATURE = float(cleaned_temp_str)
        print(f"[CONFIG_DEBUG] Successfully parsed OPENAI_TEMPERATURE: {OPENAI_TEMPERATURE}")
    except (ValueError, TypeError) as e:
        print(f"[CONFIG_DEBUG] ERROR parsing OPENAI_TEMPERATURE: {e}. Falling back to default.")
        logging.warning(
            f"Invalid OPENAI_TEMPERATURE value '{temp_str}' in .env. Error: {e}. Using default: {DEFAULT_TEMPERATURE}"
        )
        OPENAI_TEMPERATURE = DEFAULT_TEMPERATURE
else:
    print(f"[CONFIG_DEBUG] OPENAI_TEMPERATURE not found in .env, using default: {DEFAULT_TEMPERATURE}")


# --- Context Limit ---
OPENAI_CONTEXT_LIMIT = DEFAULT_CONTEXT_LIMIT # Start with default
limit_str = os.getenv("OPENAI_CONTEXT_LIMIT")
print(f"[CONFIG_DEBUG] Raw OPENAI_CONTEXT_LIMIT from .env: '{limit_str}' (Type: {type(limit_str)})")
if limit_str:
    try:
        cleaned_limit_str = limit_str.strip()
        print(f"[CONFIG_DEBUG] Attempting int conversion for CONTEXT_LIMIT: int('{cleaned_limit_str}')")
        OPENAI_CONTEXT_LIMIT = int(cleaned_limit_str)
        print(f"[CONFIG_DEBUG] Successfully parsed OPENAI_CONTEXT_LIMIT: {OPENAI_CONTEXT_LIMIT}")
    except (ValueError, TypeError) as e:
        print(f"[CONFIG_DEBUG] ERROR parsing OPENAI_CONTEXT_LIMIT: {e}. Falling back to default.")
        logging.warning(
            f"Invalid OPENAI_CONTEXT_LIMIT value '{limit_str}' in .env. Error: {e}. Using default: {DEFAULT_CONTEXT_LIMIT}"
        )
        OPENAI_CONTEXT_LIMIT = DEFAULT_CONTEXT_LIMIT
else:
    print(f"[CONFIG_DEBUG] OPENAI_CONTEXT_LIMIT not found in .env, using default: {DEFAULT_CONTEXT_LIMIT}")


# --- Final Config Values Check ---
print(f"[CONFIG_DEBUG] FINAL PARSED VALUES -> Model: {OPENAI_MODEL_NAME}, MaxTokens: {OPENAI_MAX_TOKENS}, Temp: {OPENAI_TEMPERATURE}, ContextLimit: {OPENAI_CONTEXT_LIMIT}")
# Logging this again in main.py's setup_logging is still good practice, as it confirms values after all imports.


# --- File Paths ---
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = Path("/Users/yannikmarkworth/Obsidian/Yannik/• YouTube-Importer") # Keep your specific path
TRANSCRIPTS_DIR = OUTPUT_DIR / "Transcripts"
SUMMARIES_DIR = OUTPUT_DIR / "Summaries"
print(f"[CONFIG_DEBUG] Base Dir: {BASE_DIR}")
print(f"[CONFIG_DEBUG] Output Dir: {OUTPUT_DIR}")

# Ensure output directories exist
try:
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[CONFIG_DEBUG] Output directories ensured.")
except Exception as e:
    print(f"[CONFIG_DEBUG] ERROR creating output directories: {e}")
    logging.error(f"Failed to create output directories: {e}", exc_info=True)

# --- File Names ---
PLAYLIST_URL_FILE = BASE_DIR / "playlist_url.txt"
CHUNK_PROMPT_FILE = BASE_DIR / "summarize_chunk_prompt.txt"
FINAL_PROMPT_FILE = BASE_DIR / "summarize_final_prompt.txt"
ERROR_LOG_FILE = BASE_DIR / "error_log.log"
print(f"[CONFIG_DEBUG] Log file path set to: {ERROR_LOG_FILE}")

# --- (OAuth and Startup Checks remain commented out) ---

print("[CONFIG_DEBUG] config.py loading complete.")
# This logging call might happen early relative to main's setup_logging
logging.info("Configuration loading complete from config.py.")
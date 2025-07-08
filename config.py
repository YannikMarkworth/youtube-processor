# === config.py - Updated for Gemini Support & Preserving Debug Prints ===

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

# --- AI Provider Selection ---
# User can choose 'openai' or 'gemini' in the .env file. Defaults to 'openai'.
AI_PROVIDER = os.getenv("AI_PROVIDER", "openai").lower()
print(f"[CONFIG_DEBUG] AI_PROVIDER set to: '{AI_PROVIDER}'")

# --- API Keys ---
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") # Added for Gemini
PROXY_USERNAME = os.getenv("PROXY_USERNAME")
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD")

print(f"[CONFIG_DEBUG] Raw YOUTUBE_API_KEY from .env: {'Exists' if YOUTUBE_API_KEY else 'Not Found'}")
print(f"[CONFIG_DEBUG] Raw OPENAI_API_KEY from .env: {'Exists' if OPENAI_API_KEY else 'Not Found'}")
print(f"[CONFIG_DEBUG] Raw GEMINI_API_KEY from .env: {'Exists' if GEMINI_API_KEY else 'Not Found'}") # Added

# --- OpenAI Model Configuration ---
print("\n[CONFIG_DEBUG] --- Loading OpenAI Config ---")
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
        cleaned_max_tokens_str = max_tokens_str.strip()
        OPENAI_MAX_TOKENS = int(cleaned_max_tokens_str)
        print(f"[CONFIG_DEBUG] Successfully parsed OPENAI_MAX_TOKENS: {OPENAI_MAX_TOKENS}")
    except (ValueError, TypeError) as e:
        print(f"[CONFIG_DEBUG] ERROR parsing OPENAI_MAX_TOKENS: {e}. Falling back to default.")
        logging.warning(f"Invalid OPENAI_MAX_TOKENS value '{max_tokens_str}' in .env. Using default: {DEFAULT_MAX_TOKENS}")
        OPENAI_MAX_TOKENS = DEFAULT_MAX_TOKENS
else:
    print(f"[CONFIG_DEBUG] OPENAI_MAX_TOKENS not found in .env, using default: {DEFAULT_MAX_TOKENS}")

# --- Temperature ---
OPENAI_TEMPERATURE = DEFAULT_TEMPERATURE # Start with default
temp_str = os.getenv("OPENAI_TEMPERATURE")
print(f"[CONFIG_DEBUG] Raw OPENAI_TEMPERATURE from .env: '{temp_str}' (Type: {type(temp_str)})")
if temp_str:
    try:
        cleaned_temp_str = temp_str.strip()
        OPENAI_TEMPERATURE = float(cleaned_temp_str)
        print(f"[CONFIG_DEBUG] Successfully parsed OPENAI_TEMPERATURE: {OPENAI_TEMPERATURE}")
    except (ValueError, TypeError) as e:
        print(f"[CONFIG_DEBUG] ERROR parsing OPENAI_TEMPERATURE: {e}. Falling back to default.")
        logging.warning(f"Invalid OPENAI_TEMPERATURE value '{temp_str}' in .env. Using default: {DEFAULT_TEMPERATURE}")
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
        OPENAI_CONTEXT_LIMIT = int(cleaned_limit_str)
        print(f"[CONFIG_DEBUG] Successfully parsed OPENAI_CONTEXT_LIMIT: {OPENAI_CONTEXT_LIMIT}")
    except (ValueError, TypeError) as e:
        print(f"[CONFIG_DEBUG] ERROR parsing OPENAI_CONTEXT_LIMIT: {e}. Falling back to default.")
        logging.warning(f"Invalid OPENAI_CONTEXT_LIMIT value '{limit_str}' in .env. Using default: {DEFAULT_CONTEXT_LIMIT}")
        OPENAI_CONTEXT_LIMIT = DEFAULT_CONTEXT_LIMIT
else:
    print(f"[CONFIG_DEBUG] OPENAI_CONTEXT_LIMIT not found in .env, using default: {DEFAULT_CONTEXT_LIMIT}")


# --- Gemini Model Configuration ---
print("\n[CONFIG_DEBUG] --- Loading Gemini Config ---")
DEFAULT_GEMINI_MODEL = "gemini-1.5-flash-latest"
DEFAULT_GEMINI_MAX_TOKENS = 2048
DEFAULT_GEMINI_TEMPERATURE = 0.5

GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", DEFAULT_GEMINI_MODEL)
print(f"[CONFIG_DEBUG] Raw GEMINI_MODEL_NAME from .env: '{GEMINI_MODEL_NAME}'")

# --- Gemini Max Tokens ---
GEMINI_MAX_TOKENS = DEFAULT_GEMINI_MAX_TOKENS
gemini_max_tokens_str = os.getenv("GEMINI_MAX_TOKENS")
print(f"[CONFIG_DEBUG] Raw GEMINI_MAX_TOKENS from .env: '{gemini_max_tokens_str}'")
if gemini_max_tokens_str:
    try:
        GEMINI_MAX_TOKENS = int(gemini_max_tokens_str.strip())
        print(f"[CONFIG_DEBUG] Successfully parsed GEMINI_MAX_TOKENS: {GEMINI_MAX_TOKENS}")
    except (ValueError, TypeError) as e:
        print(f"[CONFIG_DEBUG] ERROR parsing GEMINI_MAX_TOKENS: {e}. Falling back to default.")
        GEMINI_MAX_TOKENS = DEFAULT_GEMINI_MAX_TOKENS
else:
    print(f"[CONFIG_DEBUG] GEMINI_MAX_TOKENS not found in .env, using default: {DEFAULT_GEMINI_MAX_TOKENS}")

# --- Gemini Temperature ---
GEMINI_TEMPERATURE = DEFAULT_GEMINI_TEMPERATURE
gemini_temp_str = os.getenv("GEMINI_TEMPERATURE")
print(f"[CONFIG_DEBUG] Raw GEMINI_TEMPERATURE from .env: '{gemini_temp_str}'")
if gemini_temp_str:
    try:
        GEMINI_TEMPERATURE = float(gemini_temp_str.strip())
        print(f"[CONFIG_DEBUG] Successfully parsed GEMINI_TEMPERATURE: {GEMINI_TEMPERATURE}")
    except (ValueError, TypeError) as e:
        print(f"[CONFIG_DEBUG] ERROR parsing GEMINI_TEMPERATURE: {e}. Falling back to default.")
        GEMINI_TEMPERATURE = DEFAULT_GEMINI_TEMPERATURE
else:
    print(f"[CONFIG_DEBUG] GEMINI_TEMPERATURE not found in .env, using default: {DEFAULT_GEMINI_TEMPERATURE}")


# --- File Paths ---
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = Path("/Users/yannikmarkworth/Obsidian/Yannik/• YouTube-Importer") # Keep your specific path
TRANSCRIPTS_DIR = OUTPUT_DIR / "Transcripts"
SUMMARIES_DIR = OUTPUT_DIR / "Summaries"
print(f"\n[CONFIG_DEBUG] Base Dir: {BASE_DIR}")
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

print("[CONFIG_DEBUG] config.py loading complete.")
logging.info(f"Configuration loading complete from config.py. AI_PROVIDER is '{AI_PROVIDER}'.")
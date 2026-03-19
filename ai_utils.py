import logging
import math
import re
import config

# --- Conditional Imports ---
if config.AI_PROVIDER == 'openai':
    import openai
    import tiktoken
elif config.AI_PROVIDER == 'gemini':
    # This is the correct import for the 'google-genai' package
    from google import genai
else:
    raise ValueError(f"Invalid AI_PROVIDER '{config.AI_PROVIDER}' in config. Please choose 'openai' or 'gemini'.")

# --- Constants ---
CONTEXT_SAFETY_MARGIN = 500


# ==============================================================================
# --- METADATA PARSING ---
# ==============================================================================

def normalize_tag(tag):
    """Normalizes a tag: lowercase, hyphenated, no duplicates or trailing punctuation."""
    tag = tag.strip().lower()
    tag = re.sub(r'[\s_]+', '-', tag)   # spaces/underscores → hyphens
    tag = re.sub(r'-{2,}', '-', tag)    # collapse multiple hyphens
    tag = tag.strip('-')                 # strip leading/trailing hyphens
    tag = re.sub(r'[.,;:!?]+$', '', tag)  # remove trailing punctuation
    return tag


def parse_ai_response(raw_response):
    """
    Parses the AI output into metadata and summary text.
    Expects a :::META ... ::: block at the start, followed by the summary.
    Returns dict: {"metadata": {...}, "summary": "..."}
    Falls back gracefully if no META block is found.
    """
    if not raw_response:
        return {"metadata": {}, "summary": ""}

    # Try to find the :::META ... ::: block
    meta_match = re.search(r':::META\s*\n(.*?)\n:::', raw_response, re.DOTALL)

    if not meta_match:
        logging.warning("No :::META block found in AI response. Using full text as summary.")
        return {"metadata": {}, "summary": raw_response.strip()}

    meta_block = meta_match.group(1)
    # Everything after the closing ::: is the summary
    summary_text = raw_response[meta_match.end():].strip()

    metadata = {}
    for line in meta_block.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        # Split on first colon
        parts = line.split(":", 1)
        if len(parts) == 2:
            key = parts[0].strip().lower()
            value = parts[1].strip()
            if key == "tags":
                # Split comma-separated tags into a list
                metadata["tags"] = [normalize_tag(t) for t in value.split(",") if t.strip()]
            else:
                metadata[key] = value

    return {"metadata": metadata, "summary": summary_text}

# ==============================================================================
# --- OPENAI SPECIFIC FUNCTIONS (Unchanged) ---
# ==============================================================================
def _count_openai_tokens(text, model_name=config.OPENAI_MODEL_NAME):
    if not text: return 0
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        logging.debug(f"Could not find tiktoken encoding for model '{model_name}'. Using 'cl100k_base'.")
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

def _split_text_into_chunks_openai(text, max_tokens_per_chunk, model_name=config.OPENAI_MODEL_NAME):
    chunks = []
    try:
        encoding = tiktoken.encoding_for_model(model_name)
        tokens = encoding.encode(text)
        current_chunk_start_index = 0
        while current_chunk_start_index < len(tokens):
            chunk_end_index = min(current_chunk_start_index + max_tokens_per_chunk, len(tokens))
            chunk_tokens = tokens[current_chunk_start_index:chunk_end_index]
            chunks.append(encoding.decode(chunk_tokens))
            current_chunk_start_index = chunk_end_index
        logging.info(f"Split text into {len(chunks)} chunks for OpenAI.")
        return chunks
    except Exception as e:
         logging.error(f"Failed to split text into chunks for OpenAI: {e}. Returning text as a single chunk.")
         return [text]

def _call_openai_api(prompt_filled, purpose="summarization"):
    if not config.OPENAI_API_KEY:
        logging.error("OpenAI API Key missing.")
        return None
    try:
        client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL_NAME,
            messages=[{"role": "user", "content": prompt_filled}],
            temperature=config.OPENAI_TEMPERATURE,
            max_tokens=config.OPENAI_MAX_TOKENS
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"OpenAI API call failed for {purpose}: {e}", exc_info=True)
        return None

# ==============================================================================
# --- GEMINI SPECIFIC FUNCTIONS (Corrected to use 'google-genai') ---
# ==============================================================================

def _get_gemini_client():
    """Initializes and returns the Gemini client."""
    if not config.GEMINI_API_KEY:
        logging.error("Gemini API Key missing. Cannot configure client.")
        return None
    try:
        # Using genai.Client() from the correct 'google-genai' library
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        return client
    except Exception as e:
        logging.error(f"Failed to configure Gemini client: {e}", exc_info=True)
        return None

def _call_gemini_api(prompt_filled, client, purpose="summarization"):
    """Makes a single API call to Gemini using the correct client method."""
    try:
        logging.debug(f"Sending prompt to {config.GEMINI_MODEL_NAME} for {purpose}.")
        
        # The configuration is now part of the 'generate_content' call directly
        generation_config = {
            "max_output_tokens": config.GEMINI_MAX_TOKENS,
            "temperature": config.GEMINI_TEMPERATURE,
        }
        
        # Use the client.models.generate_content method as per the docs
        response = client.models.generate_content(
            model=f"models/{config.GEMINI_MODEL_NAME}",
            contents=prompt_filled,
            config=generation_config
        )
        return response.text.strip()
    except Exception as e:
        logging.error(f"Gemini API call failed for {purpose}: {e}", exc_info=True)
        print(f"Error during Gemini API call: {e}")
        return None

# ==============================================================================
# --- MAIN SUMMARIZATION ORCHESTRATOR ---
# ==============================================================================

def summarize_transcript(transcript, chunk_prompt_template, final_prompt_template, video_title):
    """The main entry point for summarization."""
    if not transcript or not transcript.strip():
        logging.warning("Summarize called with empty or missing transcript.")
        return None

    logging.info(f"Starting summarization process using AI Provider: {config.AI_PROVIDER.upper()}")

    if config.AI_PROVIDER == 'openai':
        return _summarize_with_openai(transcript, chunk_prompt_template, final_prompt_template, video_title)
    elif config.AI_PROVIDER == 'gemini':
        return _summarize_with_gemini(transcript, chunk_prompt_template, final_prompt_template, video_title)
    else:
        logging.error(f"Unsupported AI provider '{config.AI_PROVIDER}' configured.")
        return None

def _summarize_with_openai(transcript, chunk_prompt_template, final_prompt_template, video_title):
    """Handles the full summarization workflow for OpenAI, including chunking."""
    prompt_tokens = _count_openai_tokens(final_prompt_template.format(input_text="", video_title=""))
    safe_context_threshold = config.OPENAI_CONTEXT_LIMIT - prompt_tokens - config.OPENAI_MAX_TOKENS - CONTEXT_SAFETY_MARGIN
    transcript_tokens = _count_openai_tokens(transcript)

    if transcript_tokens < safe_context_threshold:
        print("Transcript fits in context. Using single-pass summarization (OpenAI)...")
        prompt = final_prompt_template.format(input_text=transcript, video_title=video_title)
        raw = _call_openai_api(prompt, "single pass final summary")
        return parse_ai_response(raw) if raw else None
    else:
        print(f"Transcript too long for single pass ({transcript_tokens} tokens). Chunking required (OpenAI)...")
        chunk_prompt_tokens = _count_openai_tokens(chunk_prompt_template.format(input_text="", video_title=""))
        max_tokens_per_chunk = config.OPENAI_CONTEXT_LIMIT - chunk_prompt_tokens - config.OPENAI_MAX_TOKENS - CONTEXT_SAFETY_MARGIN
        
        if max_tokens_per_chunk <= 0:
            logging.error("Cannot process with OpenAI: Chunk prompt is too large.")
            return None

        chunks = _split_text_into_chunks_openai(transcript, max_tokens_per_chunk)
        chunk_summaries = []
        print(f"Processing {len(chunks)} chunks...")

        for i, chunk in enumerate(chunks):
            print(f"Summarizing chunk {i+1}/{len(chunks)}...")
            prompt = chunk_prompt_template.format(input_text=chunk, video_title=video_title)
            chunk_summary = _call_openai_api(prompt, f"chunk {i+1} summary")
            if chunk_summary:
                chunk_summaries.append(chunk_summary)
            else:
                logging.error(f"Failed to summarize OpenAI chunk {i+1}. Aborting.")
                return None
        
        if not chunk_summaries:
            return None

        print("Combining chunk summaries (OpenAI)...")
        combined_summaries_text = "\n\n---\n\n".join(chunk_summaries)
        final_prompt = final_prompt_template.format(input_text=combined_summaries_text, video_title=video_title)
        raw = _call_openai_api(final_prompt, "final summary combination")
        return parse_ai_response(raw) if raw else None

def _summarize_with_gemini(transcript, chunk_prompt_template, final_prompt_template, video_title):
    """Handles the summarization workflow for Gemini using the new client."""
    client = _get_gemini_client()
    if not client:
        print("Error: Could not initialize Gemini client.")
        return None
    
    print("Summarizing with Gemini (single pass)...")
    prompt = final_prompt_template.format(input_text=transcript, video_title=video_title)
    raw = _call_gemini_api(prompt, client, "final summary")
    return parse_ai_response(raw) if raw else None

# ==============================================================================
# --- ATOMIC NOTES GENERATION ---
# ==============================================================================

def generate_atomic_notes(transcript, atomic_prompt_template, video_title):
    """Generates atomic notes from a transcript. Returns raw AI response text."""
    if not transcript or not transcript.strip():
        logging.warning("generate_atomic_notes called with empty transcript.")
        return None

    logging.info(f"Generating atomic notes using AI Provider: {config.AI_PROVIDER.upper()}")

    if config.AI_PROVIDER == 'openai':
        return _generate_atomic_notes_openai(transcript, atomic_prompt_template, video_title)
    elif config.AI_PROVIDER == 'gemini':
        return _generate_atomic_notes_gemini(transcript, atomic_prompt_template, video_title)
    else:
        logging.error(f"Unsupported AI provider '{config.AI_PROVIDER}' for atomic notes.")
        return None


def _generate_atomic_notes_openai(transcript, atomic_prompt_template, video_title):
    """Generates atomic notes using OpenAI, with chunking support for long transcripts."""
    prompt_tokens = _count_openai_tokens(atomic_prompt_template.format(input_text="", video_title=""))
    safe_context_threshold = config.OPENAI_CONTEXT_LIMIT - prompt_tokens - config.OPENAI_MAX_TOKENS - CONTEXT_SAFETY_MARGIN
    transcript_tokens = _count_openai_tokens(transcript)

    if transcript_tokens < safe_context_threshold:
        print("Transcript fits in context. Generating atomic notes in single pass (OpenAI)...")
        prompt = atomic_prompt_template.format(input_text=transcript, video_title=video_title)
        return _call_openai_api(prompt, "atomic notes single pass")
    else:
        print(f"Transcript too long for single pass ({transcript_tokens} tokens). Chunking for atomic notes (OpenAI)...")
        chunk_prompt_tokens = _count_openai_tokens(atomic_prompt_template.format(input_text="", video_title=""))
        max_tokens_per_chunk = config.OPENAI_CONTEXT_LIMIT - chunk_prompt_tokens - config.OPENAI_MAX_TOKENS - CONTEXT_SAFETY_MARGIN

        if max_tokens_per_chunk <= 0:
            logging.error("Cannot generate atomic notes: prompt is too large for context window.")
            return None

        chunks = _split_text_into_chunks_openai(transcript, max_tokens_per_chunk)
        all_notes_raw = []
        print(f"Processing {len(chunks)} chunks for atomic notes...")

        for i, chunk in enumerate(chunks):
            print(f"Extracting atomic notes from chunk {i+1}/{len(chunks)}...")
            prompt = atomic_prompt_template.format(input_text=chunk, video_title=video_title)
            result = _call_openai_api(prompt, f"atomic notes chunk {i+1}")
            if result:
                all_notes_raw.append(result)
            else:
                logging.warning(f"Failed to extract atomic notes from chunk {i+1}. Continuing with remaining chunks.")

        if not all_notes_raw:
            return None

        return "\n\n---\n\n".join(all_notes_raw)


def _generate_atomic_notes_gemini(transcript, atomic_prompt_template, video_title):
    """Generates atomic notes using Gemini (single pass)."""
    client = _get_gemini_client()
    if not client:
        print("Error: Could not initialize Gemini client for atomic notes.")
        return None

    print("Generating atomic notes with Gemini (single pass)...")
    prompt = atomic_prompt_template.format(input_text=transcript, video_title=video_title)
    return _call_gemini_api(prompt, client, "atomic notes")


def parse_atomic_notes(raw_response):
    """
    Parses the raw AI response into individual atomic notes.
    Returns: {"notes": [{"title": ..., "body": ..., "tags": [...]}, ...], "source_index": "..."}
    """
    if not raw_response:
        return {"notes": [], "source_index": ""}

    # Split off the source index section
    source_index = ""
    notes_text = raw_response
    source_marker = ":::SOURCE_INDEX"
    if source_marker in raw_response:
        parts = raw_response.split(source_marker, 1)
        notes_text = parts[0].strip()
        source_index = parts[1].strip()

    # Split into individual note blocks by ---
    blocks = re.split(r'\n---\n', notes_text)

    notes = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue

        lines = block.split('\n')

        # First non-empty line is the title
        title = ""
        body_lines = []
        tags = []
        found_title = False

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if found_title:
                    body_lines.append("")
                continue

            if not found_title:
                # Strip leading "# " markdown heading prefix if present
                title = re.sub(r'^#+\s*', '', stripped)
                found_title = True
            elif stripped.startswith("Tags:"):
                # Parse tags: "Tags: #tag1 #tag2 #tag3"
                tag_str = stripped[len("Tags:"):].strip()
                tags = [t.strip() for t in re.findall(r'#[\w-]+', tag_str)]
            else:
                body_lines.append(line)

        if title:
            body = '\n'.join(body_lines).strip()
            notes.append({
                "title": title,
                "body": body,
                "tags": tags,
            })

    logging.info(f"Parsed {len(notes)} atomic notes from AI response.")
    return {"notes": notes, "source_index": source_index}


# --- Prompt Loading Function (remains the same) ---
def load_prompt(prompt_file_path):
    """Loads a prompt template string from the specified file path."""
    try:
        with open(prompt_file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logging.error(f"Error reading prompt file {prompt_file_path}: {e}")
        return None
# === ai_utils.py - Cleaned and Annotated ===

import logging
import math
import config  # For API keys, model names, parameters, prompt paths
import openai  # OpenAI library for API access
import tiktoken # OpenAI library for token counting

# --- Constants ---
# Safety margin subtracted from context limit to leave room for response & minor inaccuracies
# Adjust these based on how critical fitting exactly is vs. potential truncation
CONTEXT_SAFETY_MARGIN = 150
# Fallback token estimation: average characters per token (adjust if needed)
FALLBACK_CHARS_PER_TOKEN = 4

# --- Helper Functions ---

def count_tokens(text, model_name=config.OPENAI_MODEL_NAME):
    """
    Counts the number of tokens in a given text string using tiktoken.
    Handles models that might not be directly mapped by tiktoken.encoding_for_model
    by attempting to use a known encoding like 'cl100k_base' for GPT-4 family.
    """
    if not text: # Handle empty string input gracefully
        return 0

    try:
        # First, try to get encoding directly using the model name.
        # For many standard model names, tiktoken.encoding_for_model() works.
        encoding = tiktoken.encoding_for_model(model_name)
        logging.debug(f"Successfully got tiktoken encoding for model '{model_name}' directly.")
    except (KeyError, ValueError) as e_direct_map:
        # This block is hit if tiktoken.encoding_for_model() fails for the given model_name.
        # The warning "Could not automatically map..." from your log originates from within tiktoken
        # when this type of exception occurs.
        logging.info(
            f"tiktoken.encoding_for_model failed for '{model_name}' ({e_direct_map}). "
            f"Will attempt explicit encoding based on model family."
        )

        # Check for known OpenAI model families that use 'cl100k_base'
        # (e.g., gpt-4o, gpt-4-turbo, gpt-4, and variants like gpt-4.1-mini, also gpt-3.5-turbo)
        model_name_lower = model_name.lower()
        if "gpt-4" in model_name_lower or \
           model_name_lower.startswith("gpt-3.5-turbo"):
            
            explicit_encoding_name = "cl100k_base"
            logging.info(
                f"Model '{model_name}' matches GPT-4/3.5 family. "
                f"Attempting to use explicit encoding: '{explicit_encoding_name}'."
            )
            try:
                encoding = tiktoken.get_encoding(explicit_encoding_name)
            except Exception as e_get_explicit_enc:
                # This would be unusual if 'cl100k_base' itself is not found by tiktoken.
                logging.warning(
                    f"Failed to get explicit encoding '{explicit_encoding_name}' for model {model_name} "
                    f"({e_get_explicit_enc}). Using char-based estimate as a last resort."
                )
                return math.ceil(len(text) / FALLBACK_CHARS_PER_TOKEN)
        else:
            # If it's not a recognized family for explicit handling, fall back to char-based estimate.
            logging.warning(
                f"Model '{model_name}' does not match known families for explicit tiktoken encoding. "
                f"Original mapping error: ({e_direct_map}). Using char-based estimate."
            )
            return math.ceil(len(text) / FALLBACK_CHARS_PER_TOKEN)

    # If we successfully obtained an encoding object (either directly or explicitly)
    try:
        num_tokens = len(encoding.encode(text))
        # Optional: More detailed logging for token counts if desired.
        # text_snippet = text[:30].replace(chr(10), ' ') # Get first 30 chars, replace newlines for logging
        # logging.debug(f"Token count for text (approx. '{text_snippet}...') with model '{model_name}': {num_tokens}")
        return num_tokens
    except Exception as e_encode_text:
        # This would be an unexpected error if an encoding object was supposedly obtained.
        logging.error(
            f"Failed to encode text using the determined tiktoken encoding for model {model_name} "
            f"({e_encode_text}). Using char-based estimate."
        )
        return math.ceil(len(text) / FALLBACK_CHARS_PER_TOKEN)

def split_text_into_chunks(text, max_tokens_per_chunk, model_name=config.OPENAI_MODEL_NAME):
    """
    Splits a long text into smaller chunks, each not exceeding the max token limit.

    Args:
        text (str): The text to split.
        max_tokens_per_chunk (int): The maximum number of tokens allowed in each chunk.
        model_name (str): The OpenAI model name (for accurate tokenization).

    Returns:
        list[str]: A list of text chunks. Returns the original text as a single chunk if splitting fails.
    """
    chunks = []
    try:
        encoding = tiktoken.encoding_for_model(model_name)
        tokens = encoding.encode(text)
        current_chunk_start_index = 0
        # Loop while there are still tokens left to process
        while current_chunk_start_index < len(tokens):
            # Calculate the end index for the current chunk
            chunk_end_index = min(current_chunk_start_index + max_tokens_per_chunk, len(tokens))
            # Extract the tokens for this chunk
            chunk_tokens = tokens[current_chunk_start_index:chunk_end_index]
            # Decode tokens back to text and add to the list
            chunks.append(encoding.decode(chunk_tokens))
            # Move the start index for the next chunk
            current_chunk_start_index = chunk_end_index
        logging.info(f"Split text into {len(chunks)} chunks based on max tokens ({max_tokens_per_chunk}).")
        return chunks
    except Exception as e:
         # If any error occurs during chunking, return the original text as one chunk
         logging.error(f"Failed to split text into chunks: {e}. Returning text as a single chunk.")
         return [text]

def _call_openai_api(prompt_filled, purpose="summarization"):
    """
    Internal helper function to make a single API call to OpenAI ChatCompletion.

    Handles client initialization and common API errors.

    Args:
        prompt_filled (str): The complete prompt string including the input text.
        purpose (str): A description of the API call's purpose for logging.

    Returns:
        str | None: The generated text content from the AI, or None if an error occurred.
    """
    # Ensure API key is available from config
    if not config.OPENAI_API_KEY:
        logging.error("OpenAI API Key missing in configuration. Cannot make API call.")
        print("Error: OpenAI API Key missing.")
        return None

    try:
        # Initialize OpenAI client (best practice to do this per call or manage lifetime appropriately)
        client = openai.OpenAI(api_key=config.OPENAI_API_KEY)

        # Log token count being sent (helpful for debugging context limits)
        tokens_sent = count_tokens(prompt_filled, config.OPENAI_MODEL_NAME)
        logging.debug(f"Sending {tokens_sent} tokens to {config.OPENAI_MODEL_NAME} API for {purpose}.")

        # Make the API call using configured parameters
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL_NAME,
            messages=[{"role": "user", "content": prompt_filled}],
            temperature=config.OPENAI_TEMPERATURE,
            max_tokens=config.OPENAI_MAX_TOKENS # This limits the length of the *response*
        )

        # Extract the response text
        result_text = response.choices[0].message.content.strip()
        # Log token usage from response (optional, good for cost tracking)
        # usage_info = response.usage # Contains completion_tokens, prompt_tokens, total_tokens
        # logging.debug(f"OpenAI Response Usage for {purpose}: {usage_info}")
        return result_text

    # --- Specific OpenAI Error Handling ---
    except openai.AuthenticationError:
         logging.error("OpenAI Authentication Error: Invalid API key.")
         print("Error: OpenAI API Key is invalid. Check your .env file.")
         return None
    except openai.RateLimitError:
         logging.error(f"OpenAI Rate Limit Error encountered for {purpose}.")
         print("Error: OpenAI rate limit exceeded. Please check your usage/limits or wait.")
         return None
    except openai.BadRequestError as e:
         # Check specifically for context length errors
         if "context_length_exceeded" in str(e):
              logging.error(f"OpenAI Context Length Error ({purpose}): Input ({tokens_sent} tokens) exceeds model's ({config.OPENAI_MODEL_NAME}) limit.")
              print(f"Error ({purpose}): Input too long for model {config.OPENAI_MODEL_NAME}. Try a model with a larger context window or shorter input.")
         else:
              # Handle other "bad request" errors (e.g., invalid parameters)
              logging.error(f"OpenAI Bad Request Error ({purpose}): {e}")
              print(f"Error ({purpose}): An OpenAI API Bad Request occurred: {e}")
         return None
    except openai.APIError as e:
         # Handle other generic OpenAI API errors (e.g., server issues)
         logging.error(f"OpenAI API Error ({purpose}): {e}")
         print(f"Error ({purpose}): An error occurred with the OpenAI API: {e}")
         return None
    # --- General Error Handling ---
    except Exception as e:
         # Catch any other unexpected errors during the API call
         logging.error(f"Unexpected error during OpenAI call ({purpose}): {e}")
         print(f"Error ({purpose}): An unexpected error occurred during API call: {e}")
         return None

# --- Main Summarization Orchestration Function ---
def summarize_transcript(transcript, chunk_prompt_template, final_prompt_template, video_title):
    """
    Generates a summary for a transcript, automatically handling chunking for long inputs.

    Uses a specific prompt for summarizing chunks and a potentially different, more detailed
    prompt for combining chunk summaries or for summarizing short transcripts directly.
    The video title is passed as context to the prompts.

    Args:
        transcript (str): The full transcript text to summarize.
        chunk_prompt_template (str): Prompt template for summarizing individual chunks.
                                     Must accept {input_text} and {video_title} placeholders.
        final_prompt_template (str): Prompt template for the final summary (either from combined
                                     chunks or directly from a short transcript).
                                     Must accept {input_text} and {video_title} placeholders.
        video_title (str): The title of the video, passed to the prompts for context.

    Returns:
        str | None: The generated final summary string, or None if summarization fails.
    """
    # --- Input Validation ---
    if not transcript or not transcript.strip():
        logging.warning("Summarize called with empty or missing transcript.")
        return None
    if not chunk_prompt_template or not final_prompt_template:
        logging.error("Summarize called with missing prompt templates.")
        print("Error: Missing prompt templates for summarization.")
        return None
    if video_title is None: video_title = "Untitled Video" # Provide a default title if None

    # --- Token Calculation and Chunking Decision ---
    # Estimate token cost of the prompt templates themselves (excluding input text/title)
    # Use dummy values for placeholders during estimation
    try:
        chunk_prompt_tokens = count_tokens(chunk_prompt_template.format(input_text="abc", video_title="xyz")) - count_tokens("abc") - count_tokens("xyz")
        final_prompt_tokens = count_tokens(final_prompt_template.format(input_text="abc", video_title="xyz")) - count_tokens("abc") - count_tokens("xyz")
        # Use the token count of the *larger* prompt for threshold calculations
        prompt_tokens_estimate = max(chunk_prompt_tokens, final_prompt_tokens)
        if prompt_tokens_estimate < 0 : prompt_tokens_estimate = 0 # Ensure non-negative
    except KeyError as e:
        # If placeholder is missing in *either* prompt, abort.
        logging.error(f"Placeholder error in prompt template token analysis (missing {e}): Check prompt files.")
        print(f"Error: Placeholder {e} missing in a prompt file. Cannot calculate token usage.")
        return None

    # Calculate a safe threshold *below* the model's actual context limit
    # Threshold = ModelLimit - PromptEstimate - MaxOutputTokens - SafetyMargin
    safe_context_threshold = config.OPENAI_CONTEXT_LIMIT - prompt_tokens_estimate - config.OPENAI_MAX_TOKENS - CONTEXT_SAFETY_MARGIN
    if safe_context_threshold <= 0:
        logging.error(f"Calculated safe context threshold ({safe_context_threshold}) is too low. Check model context limit ({config.OPENAI_CONTEXT_LIMIT}), max output tokens ({config.OPENAI_MAX_TOKENS}), and prompt lengths.")
        print("Error: Cannot process text; configured limits and prompt size leave no room for input.")
        return None

    # Count tokens in the actual transcript
    transcript_tokens = count_tokens(transcript)
    # Estimate total tokens if processed in a single pass (using the potentially larger final prompt estimate)
    total_input_tokens_estimate_single_pass = transcript_tokens + final_prompt_tokens

    logging.info(f"Transcript tokens: {transcript_tokens}, Est. single pass total tokens: {total_input_tokens_estimate_single_pass}, Safe threshold: {safe_context_threshold}")

    # --- Branch: Single Pass vs. Chunking ---
    if total_input_tokens_estimate_single_pass < safe_context_threshold:
        # Transcript (+ final prompt estimate) fits within the safe limit
        print(f"Transcript fits in context window ({total_input_tokens_estimate_single_pass} < {safe_context_threshold}). Using final prompt directly...")
        logging.info("Transcript within token limit, calling API once with final prompt.")
        try:
            # Format the *final* prompt with the *original* transcript and title
            prompt_filled = final_prompt_template.format(input_text=transcript, video_title=video_title)
        except KeyError as e:
             logging.error(f"Placeholder {e} missing in final_prompt_template. Cannot format.")
             print(f"Error: Placeholder {e} missing in final prompt file.")
             return None
        # Call the API
        summary = _call_openai_api(prompt_filled, purpose="single pass final summary")
        if summary: print("Summary received from OpenAI (single pass).")
        return summary # Return the summary (or None if API call failed)

    else:
        # Transcript is too long for a single pass, chunking is required
        print(f"Transcript exceeds context window ({total_input_tokens_estimate_single_pass} >= {safe_context_threshold}). Chunking required...")
        logging.info("Transcript exceeds token limit. Starting chunking process.")

        # --- Chunking Logic ---
        # Calculate max tokens for the *text content* of each chunk
        # Use the chunk prompt's token estimate here
        try:
            chunk_prompt_tokens_estimate = count_tokens(chunk_prompt_template.format(input_text="abc", video_title="xyz")) - count_tokens("abc") - count_tokens("xyz")
            if chunk_prompt_tokens_estimate < 0 : chunk_prompt_tokens_estimate = 0
        except KeyError as e:
            logging.error(f"Placeholder {e} missing in chunk_prompt_template. Cannot calculate chunk size.")
            print(f"Error: Placeholder {e} missing in chunk prompt file.")
            return None

        # Max text tokens per chunk = ModelLimit - ChunkPromptTokens - MaxOutputTokens - SafetyMargin
        max_tokens_per_chunk = config.OPENAI_CONTEXT_LIMIT - chunk_prompt_tokens_estimate - config.OPENAI_MAX_TOKENS - CONTEXT_SAFETY_MARGIN

        if max_tokens_per_chunk <= 0:
             logging.error("Chunk prompt is too large for the model's context window + output.")
             print("Error: The chunk summarization prompt is too long for the AI model given limits.")
             return None

        logging.info(f"Calculated max tokens per text chunk: {max_tokens_per_chunk}")
        # Split the transcript into chunks based on calculated max tokens
        chunks = split_text_into_chunks(transcript, max_tokens_per_chunk)
        chunk_summaries = []
        print(f"Processing {len(chunks)} chunks...")

        # --- Summarize each chunk ---
        for i, chunk in enumerate(chunks):
            print(f"Summarizing chunk {i+1}/{len(chunks)}...")
            logging.info(f"Summarizing chunk {i+1}/{len(chunks)}")
            try:
                # Format the *chunk* prompt with the current chunk text and video title
                prompt_filled = chunk_prompt_template.format(input_text=chunk, video_title=video_title)
            except KeyError as e:
                 logging.error(f"Placeholder {e} missing in chunk_prompt_template. Cannot format chunk {i+1}.")
                 print(f"Error: Placeholder {e} missing in chunk prompt file. Skipping chunk.")
                 continue # Skip this chunk if formatting fails

            # Call the API for this chunk
            chunk_summary = _call_openai_api(prompt_filled, purpose=f"chunk {i+1} summary")
            if chunk_summary:
                chunk_summaries.append(chunk_summary)
            else:
                # API call failed for this chunk - abort the whole process for this video
                logging.error(f"Failed to summarize chunk {i+1}. Aborting final summary for this video.")
                print(f"Error: Failed to get summary for chunk {i+1}. Cannot generate final summary.")
                return None

        # --- Combine chunk summaries ---
        if not chunk_summaries: # Check if any summaries were actually generated
            logging.error("No chunk summaries were generated (all chunks might have failed formatting/API calls).")
            print("Error: No summaries generated from chunks.")
            return None

        combined_summaries_text = "\n\n---\n\n".join(chunk_summaries) # Combine with separators
        print("All chunks summarized. Combining summaries using final prompt...")
        logging.info("Combining chunk summaries using final prompt.")

        try:
            # Format the *final* prompt with the combined chunk summaries and video title
            final_prompt_filled = final_prompt_template.format(input_text=combined_summaries_text, video_title=video_title)
        except KeyError as e:
             logging.error(f"Placeholder {e} missing in final_prompt_template. Cannot format final call.")
             print(f"Error: Placeholder {e} missing in final prompt file.")
             return None

        # Optional: Check token count for the final call
        final_call_tokens = count_tokens(final_prompt_filled)
        logging.info(f"Tokens for final combination call: {final_call_tokens}")
        # Recalculate safe limit based on final prompt tokens
        try:
             final_combine_prompt_tokens = count_tokens(final_prompt_template.format(input_text="abc", video_title="xyz")) - count_tokens("abc") - count_tokens("xyz")
             if final_combine_prompt_tokens < 0 : final_combine_prompt_tokens = 0
             final_safe_limit = config.OPENAI_CONTEXT_LIMIT - final_combine_prompt_tokens - config.OPENAI_MAX_TOKENS - 50 # Smaller safety margin ok here?
             if final_call_tokens >= final_safe_limit:
                 logging.warning("Combined summaries + final prompt might exceed context limit for the final call.")
                 print("Warning: Input for final summary step is very long, result might be truncated.")
        except KeyError as e:
             logging.warning(f"Could not check final token limit due to missing placeholder {e} in final prompt.")

        # Make the final API call to combine summaries
        final_summary = _call_openai_api(final_prompt_filled, purpose="final summary combination")
        if final_summary: print("Final summary received from OpenAI (combined chunks).")
        logging.info("Finished final summary combination step.")
        return final_summary


# --- Prompt Loading Function ---
def load_prompt(prompt_file_path):
    """
    Loads a prompt template string from the specified file path.

    Args:
        prompt_file_path (str or Path): The full path to the prompt file.

    Returns:
        str | None: The content of the file, or None if an error occurs.
    """
    try:
        with open(prompt_file_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()
        logging.info(f"Successfully loaded prompt template from {prompt_file_path}")
        return prompt_template
    except FileNotFoundError:
        logging.error(f"Prompt template file not found at: {prompt_file_path}")
        print(f"Error: Prompt file not found at {prompt_file_path}")
        return None
    except Exception as e:
        logging.error(f"Error reading prompt file {prompt_file_path}: {e}")
        print(f"Error: Could not read prompt file {prompt_file_path}. Reason: {e}")
        return None

# Removed the if __name__ == "__main__": block as this is intended as a module
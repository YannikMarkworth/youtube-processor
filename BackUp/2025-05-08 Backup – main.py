import logging
import sys
import re
# import time # Entfernt, da time.sleep auskommentiert war
from datetime import datetime # Nach oben verschoben
from pathlib import Path      # Nach oben verschoben

# Import our own modules
import config
import youtube_utils
import transcript_utils
import file_utils
import ai_utils

# --- Logging Configuration ---
def setup_logging():
    """Konfiguriert das Logging-System für Datei- und Konsolenausgabe."""
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        handlers=[
                            logging.FileHandler(config.ERROR_LOG_FILE, encoding='utf-8'), # Sicherstellen, dass die Datei UTF-8 verwendet
                            logging.StreamHandler()
                        ])
    logging.info("Logging konfiguriert.")

# --- Helper to Extract Playlist ID ---
def extract_playlist_id(url):
    """Extrahiert die YouTube Playlist ID aus verschiedenen URL-Formaten."""
    patterns = [
        r'list=([a-zA-Z0-9_-]+)', # Vereinfachtes Muster, das nach 'list=' sucht
        # Frühere Muster waren spezifischer, dieses ist breiter gefasst
        # r'(?:https?://)?(?:www\.)?youtube\.com/playlist\?list=([a-zA-Z0-9_-]+)',
        # r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[a-zA-Z0-9_-]+&list=([a-zA-Z0-9_-]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            playlist_id = match.group(1)
            logging.info(f"Extracted Playlist ID: {playlist_id}")
            return playlist_id

    logging.error(f"Konnte keine Playlist ID aus URL extrahieren: {url}")
    print(f"Error: Konnte keine gültige YouTube Playlist ID in der URL finden: {url}")
    print("Stellen Sie sicher, dass die URL 'list=PLAYLIST_ID' enthält.")
    return None

# --- Main Processing Function ---
def process_playlist(playlist_url): # Signature remains the same
    """
    Orchestriert die Verarbeitung einer YouTube-Playlist.
    Fetches playlist name and includes it in summaries.
    """
    logging.info(f"Starte Verarbeitung für Playlist URL: {playlist_url}")
    playlist_id = extract_playlist_id(playlist_url)
    if not playlist_id:
        logging.error(f"Konnte Playlist ID aus URL '{playlist_url}' nicht extrahieren. Überspringe diese Playlist.")
        print(f"Fehler: Ungültige Playlist URL oder ID nicht gefunden in: {playlist_url}. Diese Playlist wird übersprungen.")
        return # Skip this playlist if ID extraction fails

    # --- Initialisierung & Vorbereitung ---
    logging.info("Lade Zusammenfassungs-Prompts...")
    chunk_prompt_template = ai_utils.load_prompt(config.CHUNK_PROMPT_FILE)
    final_prompt_template = ai_utils.load_prompt(config.FINAL_PROMPT_FILE)
    prompts_loaded = chunk_prompt_template and final_prompt_template
    if not prompts_loaded:
        logging.warning("Konnte Prompt-Vorlagen nicht laden. Zusammenfassung wird für diese Playlist übersprungen.")
        print("Warnung: Prompt-Vorlagen nicht geladen. Keine Zusammenfassungen für diese Playlist möglich.")
        # Potentially return here if prompts are critical for the whole playlist processing

    youtube = youtube_utils.build_youtube_service()
    if not youtube:
        logging.critical("Konnte YouTube Service nicht erstellen. Überspringe diese Playlist.")
        print("Fehler: Initialisierung der YouTube-Verbindung fehlgeschlagen. Diese Playlist wird übersprungen.")
        return

    # Fetch playlist details (including its name)
    playlist_details = youtube_utils.get_playlist_details(youtube, playlist_id)
    current_playlist_name = "N/A" # Default if fetching fails
    if playlist_details and playlist_details.get("title"):
        current_playlist_name = playlist_details["title"]
    logging.info(f"Verarbeite Videos aus Playlist: '{current_playlist_name}' (ID: {playlist_id})")
    print(f"Aktuelle Playlist: '{current_playlist_name}'")

    logging.info(f"Hole Videoliste für Playlist ID: {playlist_id}")
    video_items = youtube_utils.get_playlist_video_items(youtube, playlist_id)
    if not video_items:
        logging.warning(f"Keine Videos in Playlist '{current_playlist_name}' (ID: {playlist_id}) gefunden oder API-Fehler.")
        print(f"Warnung: Keine Videos in Playlist '{current_playlist_name}' (ID: {playlist_id}) gefunden.")
        return

    total_videos = len(video_items)
    processed_count = 0
    skipped_count = 0
    failed_count = 0
    logging.info(f"{total_videos} Videos in Playlist '{current_playlist_name}' zur Verarbeitung gefunden.")
    print(f"{total_videos} Videos in Playlist '{current_playlist_name}' gefunden.")
    
    # === Haupt-Loop: Geht jedes Video durch ===
    for index, (video_id, playlist_item_id) in enumerate(video_items):
        current_video_num = index + 1
        print(f"\n--- Verarbeite Video {current_video_num}/{total_videos} (ID: {video_id}) aus Playlist '{current_playlist_name}' ---")
        logging.info(f"--- Verarbeite Video {current_video_num}/{total_videos} (ID: {video_id}) aus Playlist '{current_playlist_name}' ---")

        if file_utils.check_summary_exists(video_id):
            logging.info(f"Übersprungen: Summary-Datei für {video_id} existiert bereits.")
            print(f"Übersprungen: Summary für {video_id} existiert bereits.")
            skipped_count += 1
            continue

        print(f"Summary-Datei für {video_id} nicht gefunden. Verarbeite...")
        video_details = youtube_utils.get_video_details(youtube, video_id)
        if not video_details:
            logging.error(f"FEHLER: Konnte Details für {video_id} nicht holen. Übersprungen.")
            print(f"FEHLER: Details für {video_id} nicht abrufbar. Übersprungen.")
            failed_count += 1
            continue

        title = video_details.get('title', 'untitled')
        base_filename = file_utils.generate_base_filename(video_id, title)
        transcript_filepath = config.TRANSCRIPTS_DIR / f"{base_filename}.md"
        summary_filepath = config.SUMMARIES_DIR / f"{base_filename}_summary.md"
        logging.debug(f"Erwarte Transkript: {transcript_filepath}")
        logging.debug(f"Erwarte Summary: {summary_filepath}")

        transcript = None
        if transcript_filepath.exists():
            print(f"Transkript-Datei gefunden: {transcript_filepath.name}. Lese...")
            logging.info(f"Lese Transkript aus Datei: {transcript_filepath}")
            transcript = file_utils.read_transcript_from_file(transcript_filepath)
            if transcript is None:
                 logging.warning(f"Konnte Inhalt aus existierender Transkript-Datei nicht lesen: {transcript_filepath}. Überspringe Video.")
                 print(f"Warnung: Inhalt aus {transcript_filepath.name} nicht lesbar. Übersprungen.")
                 failed_count += 1
                 continue
        else:
            print("Transkript-Datei nicht gefunden. Hole von API...")
            logging.info(f"Transkript-Datei nicht gefunden. Hole Transkript für {video_id}")
            transcript_from_api = transcript_utils.get_transcript(video_id)
            if transcript_from_api is not None:
                print("Transkript von API geholt. Speichere Datei...")
                if file_utils.create_transcript_file(video_details, transcript_from_api, transcript_filepath):
                     transcript = transcript_from_api
                else:
                     logging.error(f"FEHLER: Konnte geholtes Transkript nicht speichern: {transcript_filepath}. Überspringe Zusammenfassung.")
                     print(f"FEHLER: Transkript-Datei für {video_id} nicht speicherbar. Zusammenfassung übersprungen.")
                     failed_count += 1
                     continue
            else:
                logging.warning(f"Transkript für {video_id} nicht verfügbar (API). Überspringe Zusammenfassung.")
                print(f"Warnung: Transkript für {video_id} nicht via API verfügbar. Zusammenfassung übersprungen.")
                failed_count += 1
                continue
        
        if transcript is None:
             logging.error(f"FEHLER: Transkript ist unerwartet 'None' vor Zusammenfassung für {video_id}. Übersprungen.")
             failed_count += 1
             continue
        if not prompts_loaded:
             logging.warning(f"Überspringe Zusammenfassung für {video_id}, da Prompts fehlen.")
             print("Warnung: Überspringe Zusammenfassung, da Prompts fehlen.")
             failed_count += 1
             continue

        print("Generiere AI Zusammenfassung...")
        logging.info(f"Generiere Zusammenfassung für {video_id}...")
        summary = ai_utils.summarize_transcript(
            transcript,
            chunk_prompt_template,
            final_prompt_template,
            video_details['title']
        )

        if summary is not None:
            print("Zusammenfassung generiert. Speichere Datei...")
            logging.info(f"Zusammenfassung für {video_id} erfolgreich generiert.")
            # MODIFIED: Pass current_playlist_name to create_summary_file
            if file_utils.create_summary_file(video_details, summary, summary_filepath, base_filename, current_playlist_name):
                 print(f"Video {video_id} erfolgreich verarbeitet und gespeichert.")
                 processed_count += 1
            else:
                 logging.error(f"FEHLER: Konnte Summary-Datei nicht speichern: {summary_filepath}.")
                 print(f"FEHLER: Summary-Datei für {video_id} nicht speicherbar.")
                 failed_count += 1
        else:
            logging.error(f"FEHLER: Konnte Zusammenfassung für {video_id} nicht generieren.")
            print(f"FEHLER: Zusammenfassung für {video_id} nicht generiert.")
            failed_count += 1
            
    # --- Ende des Haupt-Loops ---
    print(f"\n--- Verarbeitung für Playlist '{current_playlist_name}' abgeschlossen ---")
    print(f"Gesamte Videos in dieser Playlist: {total_videos}")
    print(f"Erfolgreich verarbeitet/aktualisiert: {processed_count}")
    print(f"Übersprungen (Summary existierte bereits): {skipped_count}")
    print(f"Fehlgeschlagen/Unvollständig: {failed_count}")
    logging.info(f"--- Verarbeitung für Playlist '{current_playlist_name}' (ID: {playlist_id}) abgeschlossen ---")
    logging.info(f"Statistik für Playlist '{current_playlist_name}': Gesamt: {total_videos}, Verarbeitet: {processed_count}, Übersprungen: {skipped_count}, Fehlgeschlagen: {failed_count}")

# === Ende der process_playlist Funktion ===


# --- Script Execution Entry Point ---
if __name__ == "__main__":
    # Logging konfigurieren
    setup_logging()

    # Playlist URLs aus Datei lesen
    logging.info(f"Versuche Playlist URLs aus Datei zu lesen: {config.PLAYLIST_URL_FILE}")
    playlist_urls_from_file = []
    try:
        with open(config.PLAYLIST_URL_FILE, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                url = line.strip()
                if url and not url.startswith("#"):  # Leerzeilen und Kommentare (#) ignorieren
                    playlist_urls_from_file.append(url)
                elif url.startswith("#"):
                    logging.info(f"Zeile {line_num} in '{config.PLAYLIST_URL_FILE}' als Kommentar ignoriert.")

        if not playlist_urls_from_file:
            error_msg = f"Fehler: Keine gültigen Playlist URLs in '{config.PLAYLIST_URL_FILE}' gefunden. Die Datei ist möglicherweise leer oder enthält nur Kommentare."
            logging.critical(error_msg)
            print(error_msg)
            sys.exit(1)
        
        logging.info(f"{len(playlist_urls_from_file)} Playlist URL(s) erfolgreich aus '{config.PLAYLIST_URL_FILE}' gelesen.")
        print(f"Gefunden: {len(playlist_urls_from_file)} Playlist URL(s) zum Verarbeiten.")

    except FileNotFoundError:
        error_msg = f"Fehler: Playlist URL Datei nicht gefunden: '{config.PLAYLIST_URL_FILE}'. Bitte erstellen und URL(s) eintragen (eine pro Zeile)."
        logging.critical(error_msg)
        print(error_msg)
        sys.exit(1)
    except Exception as e:
        error_msg = f"Fehler beim Lesen der Playlist URL Datei '{config.PLAYLIST_URL_FILE}': {e}"
        logging.critical(error_msg)
        print(error_msg)
        sys.exit(1)

    # Hauptverarbeitungsfunktion für jede gelesene URL aufrufen
    total_playlists_to_process = len(playlist_urls_from_file)
    overall_success_count = 0
    overall_skipped_count = 0
    overall_failed_count = 0

    for i, playlist_url in enumerate(playlist_urls_from_file):
        print(f"\n======================================================================")
        print(f"Starte Verarbeitung für Playlist {i+1}/{total_playlists_to_process}: {playlist_url}")
        print(f"======================================================================")
        logging.info(f"=== Starte Verarbeitung für Playlist {i+1}/{total_playlists_to_process}: {playlist_url} ===")
        
        # process_playlist will be modified in Part 2 to fetch and use the playlist name
        # For now, this structure iterates through the URLs
        # We will collect stats from process_playlist if we modify it to return them
        process_playlist(playlist_url) # This function will be modified next

    print(f"\n======================================================================")
    print("Alle angegebenen Playlists wurden abgearbeitet.")
    logging.info("=== Alle angegebenen Playlists wurden abgearbeitet. ===")
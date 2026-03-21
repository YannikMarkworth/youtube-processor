# YouTube Playlist Processor – Benutzerhandbuch

> **Zweck dieses Dokuments**
> Das Benutzerhandbuch ist deine Nachschlagehilfe für alle Einstellungen. Du findest hier jeden konfigurierbaren Parameter mit seinem genauen Namen, dem Standardwert und einer Empfehlung. Für eine allgemeine Erklärung, wie das Tool funktioniert, lies zuerst die [DOKUMENTATION.md](DOKUMENTATION.md).

---

## Inhaltsverzeichnis

1. [Wo Einstellungen gemacht werden](#1-wo-einstellungen-gemacht-werden)
2. [Pflichteinstellungen – Ohne diese läuft nichts](#2-pflichteinstellungen--ohne-diese-läuft-nichts)
3. [OpenAI-Konfiguration](#3-openai-konfiguration)
4. [Gemini-Konfiguration](#4-gemini-konfiguration)
5. [Eingabe und Ausgabe](#5-eingabe-und-ausgabe)
6. [Die Taxonomie (categories.txt)](#6-die-taxonomie-categoriestxt)
7. [KI-Prompt-Dateien anpassen](#7-ki-prompt-dateien-anpassen)
8. [Hilfsskripte – alle Optionen](#8-hilfsskripte--alle-optionen)
9. [Rate Limiting und API-Quotas](#9-rate-limiting-und-api-quotas)
10. [Vollständige .env-Vorlage](#10-vollständige-env-vorlage)
11. [Schnellreferenz aller Variablen](#11-schnellreferenz-aller-variablen)

---

## 1. Wo Einstellungen gemacht werden

Alle Einstellungen verteilen sich auf **zwei Orte**:

| Ort | Was wird dort konfiguriert? |
|---|---|
| `.env` (im Projektordner) | API-Schlüssel, KI-Modell, Tokens, Temperatur |
| `config.py` (Zeile 138) | Ausgabepfad (`OUTPUT_DIR`) |

**Wichtig:** Die `.env`-Datei ist nicht im Lieferumfang enthalten – du musst sie selbst anlegen. Eine vollständige Vorlage findest du in [Abschnitt 10](#10-vollständige-env-vorlage).

### Format der .env-Datei

```
VARIABLE_NAME="wert"
ZAHL_OHNE_ANFÜHRUNGSZEICHEN=4096
```

- Textwerte in Anführungszeichen schreiben
- Zahlen ohne Anführungszeichen
- Zeilen, die mit `#` beginnen, werden ignoriert (Kommentare)
- Nach Änderungen muss das Skript neu gestartet werden

---

## 2. Pflichteinstellungen – Ohne diese läuft nichts

### 2.1 Ausgabepfad

| | |
|---|---|
| **Variable** | `OUTPUT_DIR` |
| **Ort** | `config.py`, Zeile 138 |
| **Standard** | `/Users/yannikmarkworth/Obsidian/Yannik/• YouTube-Importer` (hardcodierter macOS-Pfad) |

> **Achtung – das ist die wichtigste Anpassung vor dem ersten Start!**
> Der Pfad ist direkt in `config.py` eingetragen und funktioniert nur auf dem ursprünglichen Rechner. Öffne `config.py` und ersetze Zeile 138 mit deinem eigenen Pfad.

**Beispiel:**
```python
# Vorher (Zeile 138):
OUTPUT_DIR = Path("/Users/yannikmarkworth/Obsidian/Yannik/• YouTube-Importer")

# Nachher – deinen eigenen Pfad eintragen:
OUTPUT_DIR = Path("/Users/deinname/Obsidian/YouTube")        # macOS
OUTPUT_DIR = Path("/home/deinname/Obsidian/YouTube")         # Linux
OUTPUT_DIR = Path("C:/Users/deinname/Obsidian/YouTube")      # Windows
```

Alle Unterordner (`Transcripts`, `Summaries`, `Atomic Notes`) werden automatisch angelegt.

---

### 2.2 KI-Anbieter wählen

| | |
|---|---|
| **Variable** | `AI_PROVIDER` |
| **Ort** | `.env` |
| **Standard** | `openai` |
| **Optionen** | `openai` oder `gemini` |

**Wirkung:** Legt fest, welcher KI-Dienst alle Zusammenfassungen, Kategorisierungen und Tags erstellt. Betrifft `main.py`, `classify_videos.py`, `retag_videos.py` und `review_inbox.py`.

> **Empfehlung:** Gemini für Einsteiger (günstiger, im Free Tier verfügbar). OpenAI für konsistentere Ergebnisse bei dichten Inhalten.

---

### 2.3 YouTube API-Schlüssel

| | |
|---|---|
| **Variable** | `YOUTUBE_API_KEY` |
| **Ort** | `.env` |
| **Pflicht** | Immer, unabhängig vom KI-Anbieter |

**Wirkung:** Ermöglicht den Zugriff auf YouTube-Playlists und Videoinfos. Ohne diesen Key wirft `youtube_utils.py` sofort einen Fehler und das Skript startet nicht.

> **Empfehlung:** In der Google Cloud Console ein Ausgabelimit setzen, um unerwartete Kosten zu vermeiden.

---

### 2.4 OpenAI API-Schlüssel

| | |
|---|---|
| **Variable** | `OPENAI_API_KEY` |
| **Ort** | `.env` |
| **Pflicht** | Nur wenn `AI_PROVIDER=openai` |

> **Empfehlung:** In der OpenAI-Konsole ein monatliches Ausgabelimit konfigurieren.

---

### 2.5 Google Gemini API-Schlüssel

| | |
|---|---|
| **Variable** | `GEMINI_API_KEY` |
| **Ort** | `.env` |
| **Pflicht** | Nur wenn `AI_PROVIDER=gemini` |

> **Empfehlung:** Über Google AI Studio generieren – dort gibt es einen kostenlosen Zugang.

---

### 2.6 Webshare Proxy-Zugangsdaten

| | |
|---|---|
| **Variablen** | `PROXY_USERNAME` und `PROXY_PASSWORD` |
| **Ort** | `.env` |
| **Pflicht** | Immer – ohne Proxy gibt es keine Transkripte |

**Wirkung:** Alle Transkriptanfragen an YouTube laufen über einen rotierenden Wohnproxy. Das ist notwendig, weil YouTube direkte Anfragen von Servern blockiert. Ohne funktionierenden Proxy wird für jedes Video ein leerer Transkript-Platzhalter erstellt.

> **Wichtig:** Du brauchst einen **Rotating Residential**-Plan bei Webshare. Die Optionen „Proxy Server" oder „Static Residential" funktionieren nicht.

---

## 3. OpenAI-Konfiguration

### 3.1 Modell

| | |
|---|---|
| **Variable** | `OPENAI_MODEL_NAME` |
| **Ort** | `.env` |
| **Standard** | `gpt-4.1-mini` |
| **Typ** | Text (Modellname als String) |

**Gängige Optionen:**

| Modell | Kontextfenster | Qualität | Kosten |
|---|---|---|---|
| `gpt-4.1-mini` | ~1.000.000 Tokens | gut | niedrig |
| `gpt-4o-mini` | 128.000 Tokens | gut | niedrig |
| `gpt-4o` | 128.000 Tokens | sehr gut | mittel |
| `gpt-4-turbo` | 128.000 Tokens | sehr gut | mittel–hoch |

> **Empfehlung:** `gpt-4.1-mini` für die meisten Inhalte – schnell, günstig und ausreichend gut. `gpt-4o` für dichte Podcasts oder wissenschaftliche Vorlesungen.

> **Achtung:** Das `OPENAI_CONTEXT_LIMIT` muss zum gewählten Modell passen – siehe nächster Punkt.

---

### 3.2 Kontextfenster-Limit

| | |
|---|---|
| **Variable** | `OPENAI_CONTEXT_LIMIT` |
| **Ort** | `.env` |
| **Standard** | `4096` |
| **Typ** | Ganzzahl |

**Wirkung:** Bestimmt, ob ein Transkript in einem Durchgang (Single Pass) oder in Teilen (Chunking) verarbeitet wird. Bei einem zu niedrigen Wert wird jedes Video in viele kleine Stücke zerlegt, was unnötig mehr API-Aufrufe und Kosten erzeugt.

> **Kritischer Hinweis:** Der Standardwert `4096` ist für alle modernen OpenAI-Modelle viel zu klein. Er war bei der ursprünglichen Einrichtung als Platzhalter gedacht und muss auf den korrekten Wert des gewählten Modells gesetzt werden.

**Empfohlene Werte:**

| Modell | OPENAI_CONTEXT_LIMIT |
|---|---|
| `gpt-4.1-mini` | `1000000` |
| `gpt-4o-mini` | `128000` |
| `gpt-4o` | `128000` |
| `gpt-4-turbo` | `128000` |

---

### 3.3 Maximale Ausgabelänge

| | |
|---|---|
| **Variable** | `OPENAI_MAX_TOKENS` |
| **Ort** | `.env` |
| **Standard** | `1000` |
| **Typ** | Ganzzahl |

**Wirkung:** Begrenzt die maximale Länge jeder KI-Antwort. Beeinflusst Detailtiefe der Zusammenfassung und wie der Chunking-Algorithmus die Abschnitte berechnet.

> **Empfehlung:**
> - `1500–2500` für normale Videos (15–60 Minuten)
> - `3000–4000` für sehr lange Podcasts oder Vorlesungen (90+ Minuten)
> - Zu kleiner Wert → Zusammenfassungen werden mitten im Satz abgebrochen

---

### 3.4 Temperatur

| | |
|---|---|
| **Variable** | `OPENAI_TEMPERATURE` |
| **Ort** | `.env` |
| **Standard** | `0.5` |
| **Typ** | Dezimalzahl (0.0–2.0) |

**Wirkung:** Steuert, wie „kreativ" oder „vorhersehbar" die KI antwortet.
- `0.0` = sehr sachlich, immer ähnliche Formulierungen
- `2.0` = sehr kreativ, manchmal unzuverlässig

> **Empfehlung:** `0.3–0.5` für sachliche, konsistente Zusammenfassungen. Über `1.0` ist für Zusammenfassungen nicht empfehlenswert.

---

## 4. Gemini-Konfiguration

> **Hinweis zum Chunking:** Gemini-Modelle verarbeiten Transkripte immer in einem einzigen Durchgang (Single Pass). Das Token-Chunking aus dem OpenAI-Pfad entfällt daher vollständig – `OPENAI_CONTEXT_LIMIT` hat bei Gemini keine Wirkung.

---

### 4.1 Modell

| | |
|---|---|
| **Variable** | `GEMINI_MODEL_NAME` |
| **Ort** | `.env` |
| **Standard** | `gemini-1.5-flash-latest` |
| **Typ** | Text (Modellname als String) |

**Gängige Optionen:**

| Modell | Qualität | Kosten |
|---|---|---|
| `gemini-1.5-flash-latest` | gut | sehr niedrig / Free Tier |
| `gemini-1.5-pro-latest` | sehr gut | niedrig–mittel |
| `gemini-2.0-flash` | gut | sehr niedrig |

> **Empfehlung:** `gemini-1.5-flash-latest` für den Einstieg – schnell und im kostenlosen Kontingent nutzbar.

---

### 4.2 Maximale Ausgabelänge

| | |
|---|---|
| **Variable** | `GEMINI_MAX_TOKENS` |
| **Ort** | `.env` |
| **Standard** | `2048` |
| **Typ** | Ganzzahl |

> **Empfehlung:** `2048–4096` für normale Nutzung.

---

### 4.3 Temperatur

| | |
|---|---|
| **Variable** | `GEMINI_TEMPERATURE` |
| **Ort** | `.env` |
| **Standard** | `0.5` |
| **Typ** | Dezimalzahl (0.0–2.0) |

> **Empfehlung:** Gleiche Logik wie bei OpenAI. `0.3–0.5` für sachliche Zusammenfassungen.

---

## 5. Eingabe und Ausgabe

### 5.1 Playlist-URL-Datei

| | |
|---|---|
| **Datei** | `playlist_url.txt` (im Projektordner) |
| **Format** | Eine YouTube-Playlist-URL pro Zeile |

Zeilen, die mit `#` beginnen, werden als Kommentare ignoriert.

**Beispiel:**
```
# Meine Lern-Playlists
https://www.youtube.com/playlist?list=PLxxxxxxxxxx

# Temporär pausiert:
# https://www.youtube.com/playlist?list=PLyyyyyyyyyy
```

> **Empfehlung:** Nicht mehr als 5–10 Playlists gleichzeitig. Größere Batches erhöhen Laufzeit und Fehlerrisiko.

---

### 5.2 Ausgabe-Unterordner

Diese Pfade leiten sich automatisch von `OUTPUT_DIR` ab und können nur durch Änderung in `config.py` angepasst werden:

| Ordner | Inhalt |
|---|---|
| `OUTPUT_DIR/Transcripts/` | Vollständige Video-Transkripte |
| `OUTPUT_DIR/Summaries/` | KI-Zusammenfassungen mit YAML-Metadaten |
| `OUTPUT_DIR/Atomic Notes/` | Einzelne, wiederverwendbare Wissensfragmente |

---

### 5.3 Dateinamensformat

```
PlaylistName – Videotitel – VIDEO_ID.md            (Transkript)
PlaylistName – Videotitel – VIDEO_ID – Summary.md  (Zusammenfassung)
```

Die Video-ID am Ende stellt sicher, dass jede Datei eindeutig ist – auch wenn zwei Videos denselben Titel haben.

---

## 6. Die Taxonomie (categories.txt)

### 6.1 Aufbau

Die Taxonomie ist eine einfache Textdatei mit eingerückten Kategorien:

```
Technology
  Software Development
    Python
    JavaScript
  Hardware
Science
  Physics
  Biology
Inbox
```

- Einrückung mit **2 Leerzeichen** = eine Hierarchieebene tiefer
- Bis zu 3 Ebenen möglich: Kategorie > Unterkategorie > Thema
- Die Datei wird von `main.py`, `classify_videos.py` und `review_inbox.py` gelesen

---

### 6.2 Die Inbox-Kategorie

`Inbox` ist die letzte Zeile in `categories.txt` und dient als Auffangbecken. Wenn die KI kein passendes Thema findet, landet das Video dort automatisch. `review_inbox.py` hilft dabei, diese Videos zu sortieren.

> **Wichtig:** `Inbox` darf nicht gelöscht werden und muss die letzte Zeile der Datei bleiben.

---

### 6.3 Kategorien hinzufügen und bearbeiten

1. `categories.txt` mit einem Texteditor öffnen
2. Neue Zeile an der richtigen Stelle einfügen (auf korrekte Einrückung achten)
3. Speichern
4. `classify_videos.py --fix-only` ausführen, damit bestehende Videos mit der neuen Kategorie abgeglichen werden

> **Empfehlungen:**
> - Lieber 10 breite Hauptkategorien als 100 kleine Spezialthemen – zu Beginn
> - Neue Kategorien erst anlegen, wenn mindestens 3 Videos hineinpassen würden
> - Nach größeren Umstrukturierungen: `classify_videos.py --reclassify` ausführen

---

## 7. KI-Prompt-Dateien anpassen

### 7.1 Übersicht

| Datei | Zweck |
|---|---|
| `summarize_chunk_prompt.txt` | Verarbeitung einzelner Transkript-Abschnitte (Chunking) |
| `summarize_final_prompt.txt` | Finale Zusammenfassung und Metadaten-Extraktion |
| `atomic_notes_prompt.txt` | Erstellung atomarer Evergreen-Notizen |

---

### 7.2 Was du anpassen kannst

**Sicher anzupassen:**
- Ton und Stil der Ausgabe (z. B. „sachlicher", „mit konkreten Beispielen")
- Länge der Ausgabeabschnitte
- Sprache der Anweisungen (die KI folgt dann trotzdem der Sprache des Transkripts)

**Nicht verändern – bricht das System:**
- Das `:::META ... :::` Block-Format in `summarize_final_prompt.txt`
- Die Platzhalter `{video_title}`, `{input_text}` und `{taxonomy}`
- Den SPRACHREGELUNG-Abschnitt (steuert automatische Spracherkennung)

> **Empfehlung:** Vor jeder Änderung eine Sicherheitskopie anlegen. Nach Änderungen zuerst ein einzelnes Video testen, bevor du eine ganze Playlist startest.

---

### 7.3 Sprache der Ausgabe

Das System erkennt automatisch die Sprache des Transkripts und erstellt die Zusammenfassung in derselben Sprache. Dieses Verhalten wird durch den SPRACHREGELUNG-Abschnitt in `summarize_final_prompt.txt` gesteuert.

Die `atomic_notes_prompt.txt` ist bewusst auf Englisch gehalten, da atomare Notizen sprachunabhängige Wissensfragmente sein sollen.

---

## 8. Hilfsskripte – alle Optionen

### 8.1 classify_videos.py

**Zweck:** Videos in die Taxonomie einordnen – entweder erstmalig oder erneut.

```bash
python classify_videos.py [Optionen]
```

| Option | Bedeutung |
|---|---|
| `--dry-run` | Vorschau ohne Änderungen. Immer zuerst verwenden. |
| `--limit N` | Nur die ersten N unkategorisierten Dateien verarbeiten |
| `--batch-size N` | Videos pro API-Batch (Standard: 40). Bei Fehlern verkleinern. |
| `--reclassify` | Alle Videos neu klassifizieren, auch bereits kategorisierte |
| `--fix-only` | Nur Videos neu klassifizieren, die keine Kategorie haben oder deren Kategorie nicht mehr in der Taxonomie steht |

**Empfohlener Workflow:**
```bash
python classify_videos.py --dry-run          # Erst schauen, was passieren würde
python classify_videos.py --limit 10         # Dann 10 Videos als Test
python classify_videos.py                    # Dann vollständiger Lauf
```

---

### 8.2 retag_videos.py

**Zweck:** Tags (Schlagwörter) für Videos vergeben oder aktualisieren.

```bash
python retag_videos.py [Optionen]
```

| Option | Bedeutung |
|---|---|
| `--dry-run` | Vorschau ohne Änderungen |
| `--limit N` | Nur N Dateien verarbeiten |
| `--batch-size N` | Videos pro Batch (Standard: 40) |
| `--retag` | Alle Videos neu taggen, auch bereits getaggte |

> **Empfehlung:** Nach größeren Verarbeitungsläufen ausführen, um alle neuen Videos zu taggen.

---

### 8.3 review_inbox.py

**Zweck:** Videos aus der „Inbox"-Kategorie interaktiv sortieren und die Taxonomie bei Bedarf erweitern.

```bash
python review_inbox.py [Optionen]
```

| Option | Bedeutung |
|---|---|
| *(ohne)* | Interaktiver Modus – jede Entscheidung einzeln bestätigen |
| `--dry-run` | KI-Vorschläge anzeigen ohne Änderungen vorzunehmen |
| `--auto` | Alle KI-Vorschläge ohne Rückfrage anwenden |

**Im interaktiven Modus:**

| Eingabe | Aktion |
|---|---|
| `y` | Alle Vorschläge für dieses Video anwenden |
| `N` | Abbrechen |
| `s` | Selektiv – jeden Vorschlag einzeln bestätigen |

> **Empfehlung:** `--auto` erst verwenden, nachdem du einmal im interaktiven Modus die Qualität der KI-Vorschläge geprüft hast. Die KI kann unpassende Kategorien vorschlagen.

---

### 8.4 browse.py

**Zweck:** Lokale Weboberfläche zum Durchsuchen und Filtern der verarbeiteten Videos.

```bash
python browse.py
```

Dann im Browser öffnen: **http://localhost:8080**

**Funktionen:**
- Volltext-Suche über alle Zusammenfassungen
- Filter nach Playlist, Kanal, Kategorie, Schwierigkeitsgrad
- Längenfilter (YouTube Shorts vs. normale Videos)
- Statistiken-Dashboard
- Zufalls-Discovery ("Zeig mir ein zufälliges Video")

> **Hinweis:** Beim ersten Start dauert der Index-Aufbau etwas länger. Danach wird der Index automatisch alle 60 Sekunden aktualisiert.

---

### 8.5 rename_existing_files.py

**Zweck:** Dateien vom alten Namensformat ins neue Format migrieren.

```bash
python rename_existing_files.py
```

Das Skript fragt interaktiv nach und bietet einen Dry-Run-Modus an.

> **Hinweis:** Nur relevant, wenn du von einer älteren Version des Tools migrierst. Immer erst den Dry Run durchführen.

---

### 8.6 create_master_log_from_existing.py

**Zweck:** Die Datei `master_summary_log.md` aus bestehenden Dateien neu aufbauen.

```bash
python create_master_log_from_existing.py
```

> **Wann nötig:** Wenn das Master-Log fehlt, beschädigt ist oder nach einem manuellen Eingriff in die Ordnerstruktur nicht mehr stimmt.

---

### 8.7 discover_taxonomy.py / analyze_taxonomy.py

**Zweck:** Die bestehende Taxonomie analysieren, ungenutzte Kategorien finden und Verbesserungen vorschlagen.

```bash
python discover_taxonomy.py
python analyze_taxonomy.py
```

> **Empfehlung:** Gelegentlich nach größeren Verarbeitungsläufen ausführen, um die Taxonomie zu optimieren.

---

## 9. Rate Limiting und API-Quotas

### 9.1 YouTube API Quota

- Standard-Tageslimit: **10.000 Einheiten**
- Kosten pro Abruf: `playlist.list` ~1 Einheit, `videos.list` ~1 Einheit
- Das Skript liest alle Videos einer Playlist in einem Durchgang aus

> **Empfehlung:** Bei sehr großen Playlists (100+ Videos) den Lauf auf mehrere Tage verteilen oder das `--limit`-Flag in den Hilfsskripten nutzen.

---

### 9.2 OpenAI Rate Limits

- Abhängig vom Kontingent-Tier (Free, Tier 1, Tier 2, ...)
- Das Skript macht bei API-Fehlern keine automatischen Wiederholungsversuche

> **Empfehlung:** Bei einem `RateLimitError` das Skript nach einer kurzen Pause einfach neu starten. Bereits verarbeitete Videos werden dank der Duplikaterkennung übersprungen – es gibt keine doppelten Dateien.

---

### 9.3 Die 5-Sekunden-Pause zwischen Videos

`main.py` wartet automatisch 5 Sekunden zwischen der Verarbeitung einzelner Videos, um YouTube-Ratenlimitierungen zu vermeiden. Diese Pause ist in `main.py` Zeile 321 definiert:

```python
time.sleep(5)  # Pause for 5 seconds
```

> **Empfehlung:** Den Wert nicht unter 3 Sekunden senken.

---

### 9.4 Die [CONFIG_DEBUG]-Ausgaben beim Start

Beim Start gibt `config.py` eine Reihe von `[CONFIG_DEBUG]`-Meldungen im Terminal aus. Das ist normales Verhalten und kein Fehler. Diese Ausgaben helfen bei der Fehlersuche, wenn API-Keys oder Einstellungen nicht korrekt geladen werden.

---

## 10. Vollständige .env-Vorlage

Lege diese Datei als `.env` im Projektordner an und fülle alle relevanten Felder aus:

```
# ===================================
# YouTube Playlist Processor – .env
# ===================================

# KI-Anbieter: "openai" oder "gemini"
AI_PROVIDER=openai

# -----------------------------------------------
# API-Schlüssel
# -----------------------------------------------

# YouTube Data API v3 (immer erforderlich)
YOUTUBE_API_KEY=dein_youtube_api_key

# OpenAI (nur wenn AI_PROVIDER=openai)
OPENAI_API_KEY=dein_openai_api_key

# Google Gemini (nur wenn AI_PROVIDER=gemini)
GEMINI_API_KEY=dein_gemini_api_key

# -----------------------------------------------
# Webshare Proxy (immer erforderlich)
# Rotating Residential Plan erforderlich
# -----------------------------------------------
PROXY_USERNAME=dein_proxy_username
PROXY_PASSWORD=dein_proxy_passwort

# -----------------------------------------------
# OpenAI-Konfiguration
# -----------------------------------------------
OPENAI_MODEL_NAME=gpt-4.1-mini
# WICHTIG: Auf das korrekte Kontextfenster des Modells setzen!
# gpt-4.1-mini → 1000000 | gpt-4o / gpt-4o-mini → 128000
OPENAI_CONTEXT_LIMIT=1000000
OPENAI_MAX_TOKENS=2000
OPENAI_TEMPERATURE=0.5

# -----------------------------------------------
# Gemini-Konfiguration
# -----------------------------------------------
GEMINI_MODEL_NAME=gemini-1.5-flash-latest
GEMINI_MAX_TOKENS=2048
GEMINI_TEMPERATURE=0.5
```

---

## 11. Schnellreferenz aller Variablen

| Variable | Datei | Standard | Typ | Pflicht |
|---|---|---|---|---|
| `OUTPUT_DIR` | `config.py` Z.138 | macOS-Pfad (ändern!) | Pfad | Ja |
| `AI_PROVIDER` | `.env` | `openai` | Text | Ja |
| `YOUTUBE_API_KEY` | `.env` | – | Text | Ja |
| `OPENAI_API_KEY` | `.env` | – | Text | Wenn OpenAI |
| `GEMINI_API_KEY` | `.env` | – | Text | Wenn Gemini |
| `PROXY_USERNAME` | `.env` | – | Text | Ja |
| `PROXY_PASSWORD` | `.env` | – | Text | Ja |
| `OPENAI_MODEL_NAME` | `.env` | `gpt-4.1-mini` | Text | Nein |
| `OPENAI_CONTEXT_LIMIT` | `.env` | `4096` ⚠️ | Zahl | Nein |
| `OPENAI_MAX_TOKENS` | `.env` | `1000` | Zahl | Nein |
| `OPENAI_TEMPERATURE` | `.env` | `0.5` | Dezimal | Nein |
| `GEMINI_MODEL_NAME` | `.env` | `gemini-1.5-flash-latest` | Text | Nein |
| `GEMINI_MAX_TOKENS` | `.env` | `2048` | Zahl | Nein |
| `GEMINI_TEMPERATURE` | `.env` | `0.5` | Dezimal | Nein |

> ⚠️ `OPENAI_CONTEXT_LIMIT=4096` ist der Codewert, aber für alle modernen Modelle zu klein. Immer auf den korrekten Wert des gewählten Modells setzen (siehe [Abschnitt 3.2](#32-kontextfenster-limit)).

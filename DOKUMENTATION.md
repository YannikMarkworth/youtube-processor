# YouTube Playlist Processor – Projektdokumentation

> **Für wen ist diese Dokumentation?**
> Diese Dokumentation richtet sich an alle, die das Tool nutzen oder verstehen wollen – egal ob technisch versiert oder nicht. Fachbegriffe werden im [Glossar](#glossar) am Ende erklärt.

---

## Inhaltsverzeichnis

1. [Was ist dieses Tool?](#1-was-ist-dieses-tool)
2. [Wie funktioniert es? – Der Prozess, Schritt für Schritt](#2-wie-funktioniert-es--der-prozess-schritt-für-schritt)
3. [Voraussetzungen](#3-voraussetzungen)
4. [Einrichtung (Schritt für Schritt)](#4-einrichtung-schritt-für-schritt)
5. [API-Zugänge beschaffen](#5-api-zugänge-beschaffen)
6. [Das Tool starten](#6-das-tool-starten)
7. [Projektstruktur erklärt](#7-projektstruktur-erklärt)
8. [Was wird ausgegeben?](#8-was-wird-ausgegeben)
9. [Das Taxonomie-System](#9-das-taxonomie-system)
10. [Häufige Probleme & Lösungen](#10-häufige-probleme--lösungen)
11. [Glossar](#11-glossar)

---

## 1. Was ist dieses Tool?

Der **YouTube Playlist Processor** ist ein automatisierter persönlicher Assistent für Wissensarbeiter, Content Creator und alle, die YouTube systematisch als Lernquelle nutzen.

**Die einfache Erklärung:** Stell dir vor, du hast einen extrem fleißigen Assistenten, der sich für dich stundenlang YouTube-Videos ansieht, alles Wichtige herausschreibt, es verständlich zusammenfasst, thematisch einordnet – und das alles in ordentliche Notizen verwandelt, die du jederzeit durchsuchen kannst. Genau das macht dieses Tool.

### Was es konkret tut:

- Es liest automatisch **ganze YouTube-Playlisten** aus
- Es holt sich das **vollständige Transkript** (Wort-für-Wort-Mitschrift) jedes Videos
- Es lässt eine **KI** (wahlweise OpenAI oder Google Gemini) eine hochwertige Zusammenfassung erstellen
- Es speichert alles als strukturierte **Markdown-Notizen**, perfekt für Obsidian
- Es ordnet jedes Video in eine **Themenkategorie** ein
- Es extrahiert **atomare Notizen** – kleine, wiederverwendbare Wissensbausteine

### Wer profitiert davon?

- **Knowledge Worker**, die YouTube-Inhalte in ihr Wissensmanagement integrieren wollen
- **Content Creator**, die Quellen und Recherche-Material strukturiert ablegen
- **Lernende**, die viele YouTube-Kanäle verfolgen und das Gelernte festhalten wollen
- **Alle**, die ihre YouTube-Watchtime in nachhaltiges Wissen umwandeln möchten

---

## 2. Wie funktioniert es? – Der Prozess, Schritt für Schritt

Wenn das Tool gestartet wird (`python main.py`), arbeitet es folgende Schritte automatisch ab:

### Schritt 1: Playlisten einlesen
Das Tool öffnet die Datei `playlist_url.txt` und liest alle darin enthaltenen YouTube-Playlist-Links. Du kannst beliebig viele Playlisten angeben.

### Schritt 2: Videos ermitteln
Für jede Playlist fragt das Tool die YouTube-API an und bekommt eine Liste aller enthaltenen Videos zurück – inklusive Titel, Beschreibung, Kanalnamen, Dauer und Veröffentlichungsdatum.

### Schritt 3: Bereits verarbeitete Videos überspringen
Das Tool prüft, ob für ein Video bereits eine Zusammenfassung existiert. Wenn ja, wird das Video übersprungen. Das bedeutet: Du kannst das Tool jederzeit erneut starten – es verarbeitet nur neue Videos.

### Schritt 4: Transkript abrufen
Das Tool holt das komplette Transkript (die automatische Untertitel-Mitschrift von YouTube) für jedes neue Video. Um nicht von YouTube gesperrt zu werden, nutzt es dabei einen **Proxy** – einen Umweg über andere Server.

### Schritt 5: KI-Zusammenfassung erstellen
Das Transkript wird an eine KI (OpenAI GPT oder Google Gemini) gesendet. Die KI:
- Erstellt eine strukturierte, hochwertige Zusammenfassung
- Schreibt einen Ein-Satz-TLDR ("Too Long; Didn't Read")
- Ordnet das Video einer Themenkategorie zu
- Vergibt passende Schlagwörter (Tags)
- Bewertet den Schwierigkeitsgrad des Inhalts

> **Hinweis bei sehr langen Videos:** Ist das Transkript länger als das, was die KI auf einmal lesen kann, wird es automatisch in mehrere Abschnitte aufgeteilt ("Chunking"). Jeder Abschnitt wird einzeln zusammengefasst, dann werden die Teil-Zusammenfassungen zu einer Gesamt-Zusammenfassung kombiniert.

### Schritt 6: Atomare Notizen erstellen
Zusätzlich zur Zusammenfassung erstellt die KI "atomare Notizen" – kleine, in sich abgeschlossene Wissensbausteine (z.B. "Was ist ein Hook im Storytelling?"). Diese eignen sich hervorragend als wiederverwendbare Notizen in Obsidian.

### Schritt 7: Dateien speichern & Log aktualisieren
Alle erstellten Dateien werden im angegebenen Ausgabe-Ordner (z.B. dein Obsidian-Vault) gespeichert. Das Tool führt auch ein "Master-Log" – eine Übersicht aller jemals verarbeiteten Videos.

---

## 3. Voraussetzungen

### Software

| Was | Warum | Wo herunterladen |
|-----|-------|-----------------|
| **Python 3.9 oder neuer** | Programmiersprache, in der das Tool geschrieben ist | python.org |
| **Obsidian** (empfohlen) | Um die erstellten Notizen zu nutzen | obsidian.md |

### Externe Dienste (Accounts erforderlich)

Du benötigst Zugänge zu folgenden Diensten. Alle haben kostenlose Einstiegsmöglichkeiten:

| Dienst | Wofür | Kosten |
|--------|-------|--------|
| **Google Cloud Console** | YouTube Data API (Videos & Playlisten abrufen) | Kostenlos bis 10.000 Anfragen/Tag |
| **OpenAI** ODER **Google AI Studio** | KI-Zusammenfassungen generieren | OpenAI: ~$0,01–0,05/Video; Gemini: kostenlos mit Limits |
| **Webshare.io** | Proxy-Dienst für Transkript-Abruf | Ca. $5–15/Monat |

> **Warum ein Proxy?** YouTube begrenzt, wie oft Transkripte von derselben IP-Adresse abgerufen werden können. Ein Proxy-Dienst umgeht diese Einschränkung zuverlässig. Ohne Proxy schlägt der Transkript-Abruf nach kurzer Zeit fehl.

---

## 4. Einrichtung (Schritt für Schritt)

### Schritt 1: Projekt herunterladen

Lade das Projekt herunter (oder klone es via Git) und öffne den Projektordner in deinem Terminal.

### Schritt 2: Virtuelle Umgebung erstellen

Eine virtuelle Umgebung ist ein abgeschlossener Bereich, in dem die Programm-Abhängigkeiten installiert werden – ohne dein System zu beeinflussen.

```bash
# Virtuelle Umgebung erstellen
python3 -m venv venv

# Virtuelle Umgebung aktivieren (Mac/Linux)
source venv/bin/activate

# Virtuelle Umgebung aktivieren (Windows)
venv\Scripts\activate
```

> Du erkennst, dass die Umgebung aktiv ist, wenn am Anfang deiner Eingabezeile `(venv)` steht.

### Schritt 3: Abhängigkeiten installieren

```bash
pip install -r requirements.txt
```

Dieser Befehl installiert alle benötigten Programm-Bibliotheken automatisch.

### Schritt 4: Konfigurationsdatei erstellen

Kopiere die Beispiel-Konfiguration und benenne die Kopie zu `.env` um:

```bash
# Mac/Linux
cp .env.example .env

# Windows
copy .env.example .env
```

Öffne die `.env`-Datei in einem Texteditor und trage deine API-Schlüssel ein (siehe [Abschnitt 5](#5-api-zugänge-beschaffen)).

### Schritt 5: Playlist-URLs eintragen

Öffne die Datei `playlist_url.txt` und trage die URLs der YouTube-Playlisten ein, die du verarbeiten möchtest – eine URL pro Zeile.

```
https://www.youtube.com/playlist?list=XXXXXXXXXXXXXXXX
https://www.youtube.com/playlist?list=YYYYYYYYYYYYYYYY
# Diese Zeile ist ein Kommentar und wird ignoriert
```

### Schritt 6: Ausgabepfad anpassen

Öffne `config.py` in einem Texteditor und ändere den Pfad `OUTPUT_DIR` so, dass er auf deinen Obsidian-Vault zeigt:

```python
OUTPUT_DIR = Path("/Pfad/zu/deinem/Obsidian/Vault/YouTube-Importer")
```

---

## 5. API-Zugänge beschaffen

### YouTube Data API v3 (Google Cloud)

1. Gehe zu [Google Cloud Console](https://console.cloud.google.com)
2. Erstelle ein neues Projekt (oder wähle ein bestehendes)
3. Navigiere zu **APIs & Dienste** → **Bibliothek**
4. Suche nach "YouTube Data API v3" und aktiviere sie
5. Gehe zu **APIs & Dienste** → **Anmeldedaten**
6. Klicke auf **Anmeldedaten erstellen** → **API-Schlüssel**
7. Kopiere den Schlüssel und trage ihn in `.env` ein: `YOUTUBE_API_KEY="dein-schlüssel"`

### OpenAI API (für GPT-Modelle)

1. Gehe zu [platform.openai.com](https://platform.openai.com)
2. Erstelle einen Account und lade Guthaben auf
3. Gehe zu **API Keys** und erstelle einen neuen Schlüssel
4. Trage ihn in `.env` ein: `OPENAI_API_KEY="dein-schlüssel"`

### Google Gemini API (Alternative zu OpenAI)

1. Gehe zu [Google AI Studio](https://aistudio.google.com)
2. Klicke auf **Get API Key**
3. Trage ihn in `.env` ein: `GEMINI_API_KEY="dein-schlüssel"`
4. Setze in `.env`: `AI_PROVIDER="gemini"`

### Webshare Proxy

1. Erstelle einen Account auf [webshare.io](https://www.webshare.io)
2. Wähle einen **Rotating Residential Proxy**-Plan
3. Finde deine Proxy-Zugangsdaten im Dashboard
4. Trage sie in `.env` ein:
   ```
   PROXY_USERNAME="dein-benutzername"
   PROXY_PASSWORD="dein-passwort"
   ```

---

## 6. Das Tool starten

### Hauptprogramm starten

```bash
# Sicherstellen, dass die virtuelle Umgebung aktiv ist
source venv/bin/activate  # (falls nicht schon aktiv)

# Hauptskript starten
python main.py
```

Das Tool läuft nun durch und verarbeitet alle Playlisten. Im Terminal siehst du den Fortschritt. Je nach Anzahl der Videos und Internetverbindung kann dies einige Zeit dauern.

### Weboberfläche starten (zum Durchsuchen der Ergebnisse)

```bash
python browse.py
```

Öffne dann deinen Browser und gehe zu: **http://localhost:8080**

Dort kannst du alle verarbeiteten Videos durchsuchen, filtern und nach Kategorien browsen.

---

## 7. Projektstruktur erklärt

### Eingabe-Dateien (diese bearbeitest du)

| Datei | Was ist das? |
|-------|-------------|
| `playlist_url.txt` | Liste der YouTube-Playlisten, die verarbeitet werden sollen |
| `.env` | Deine privaten API-Schlüssel und Einstellungen (niemals teilen!) |
| `categories.txt` | Das Kategorie-System, in das Videos eingeordnet werden |
| `summarize_final_prompt.txt` | Die Vorlage/Anweisung für die KI-Zusammenfassung |
| `summarize_chunk_prompt.txt` | Vorlage für sehr lange Videos (wird aufgeteilt) |
| `atomic_notes_prompt.txt` | Vorlage für die Erstellung atomarer Notizen |

### Kern-Skripte (diese laufen automatisch)

| Datei | Was macht sie? |
|-------|---------------|
| `main.py` | Das Herzstück – startet und koordiniert alles |
| `youtube_utils.py` | Kommuniziert mit YouTube, um Video-Infos zu holen |
| `transcript_utils.py` | Holt Transkripte (über den Proxy) |
| `ai_utils.py` | Schickt Transkripte an die KI und verarbeitet die Antwort |
| `file_utils.py` | Erstellt die Markdown-Dateien und speichert sie |
| `config.py` | Liest die Einstellungen aus der `.env`-Datei |

### Hilfs-Skripte (diese startest du bei Bedarf manuell)

| Datei | Wann nutzen? |
|-------|-------------|
| `browse.py` | Zum Durchsuchen der Ergebnisse im Browser |
| `classify_videos.py` | Um Videos nachträglich neu zu kategorisieren |
| `review_inbox.py` | Um nicht kategorisierte Videos zu überprüfen |
| `discover_taxonomy.py` | Um einen Überblick über das Kategorie-System zu bekommen |
| `analyze_taxonomy.py` | Für detaillierte Taxonomie-Analyse |
| `rename_existing_files.py` | Um bestehende Dateien umzubenennen |
| `create_master_log_from_existing.py` | Um das Master-Log neu aufzubauen |
| `retag_videos.py` | Um Schlagwörter systematisch zu aktualisieren |

### Ausgabe-Ordner (werden automatisch erstellt)

```
Dein Obsidian Vault/
└── YouTube-Importer/
    ├── Transcripts/         ← Vollständige Transkripte
    │   └── Playlist-Name/
    ├── Summaries/           ← KI-Zusammenfassungen (Hauptergebnis)
    │   └── Playlist-Name/
    └── Atomic Notes/        ← Atomare Wissensbausteine
        └── Playlist-Name/
```

---

## 8. Was wird ausgegeben?

### Zusammenfassungs-Datei (Summary)

Die wichtigste Ausgabe. Jede Summary-Datei enthält:

**Kopfbereich (YAML-Frontmatter)** – Metadaten über das Video:
```yaml
---
title: "Titel des Videos"
channel: "Kanalname"
url: "https://youtube.com/watch?v=..."
published: "2024-01-15"
duration: "23:45"
tldr: "Das Wichtigste in einem Satz"
category: "Tabletop RPGs > Game Mastering > Worldbuilding & Lore"
tags: [worldbuilding, storytelling, game-master]
difficulty: Fortgeschritten
language: en
---
```

**Hauptinhalt** – Strukturierte Zusammenfassung mit:
- "Die lebendige Essenz" – der absolute Kern des Videos in 2-3 Sätzen
- Thematisch gegliederte Abschnitte mit Kerngedanken und Beispielen
- "Praxis-Transfer & Takeaways" – konkrete Handlungsempfehlungen

### Transkript-Datei

Die vollständige, wortgetreue Abschrift des gesprochenen Inhalts – nützlich als Nachschlagewerk oder für eigene Suchen.

### Atomare Notizen

Kleine, in sich abgeschlossene Wissensbausteine aus dem Video, z.B.:

```markdown
## Was ist das "Show, don't tell"-Prinzip?

Anstatt dem Leser zu sagen, dass eine Figur traurig ist, zeigt man
es durch Handlungen und Details (z.B. "Sie starrte auf ihr Essen,
ohne zu essen"). Dies erzeugt stärkere emotionale Resonanz.

*Quelle: [[Playlist – Videotitel – ID – Summary]]*
```

### In Obsidian

In Obsidian kannst du:
- Nach Themen, Tags oder Kategorien **filtern**
- Zwischen verlinkten Notizen **navigieren**
- Die Zusammenfassungen im **Graphen** als Netzwerk visualisieren
- Atomare Notizen in eigene Projekte **einbetten**

---

## 9. Das Taxonomie-System

### Was ist eine Taxonomie?

Eine Taxonomie ist ein strukturiertes Ordnungssystem – wie ein Inhaltsverzeichnis, das alle denkbaren Themen hierarchisch einordnet.

### Wie ist sie aufgebaut?

Die Taxonomie hat bis zu drei Ebenen:

```
Hauptkategorie
  └── Unterkategorie
        └── Thema (spezifischste Ebene)
```

**Beispiel:**
```
Tabletop RPGs                    ← Hauptkategorie
  └── Game Mastering             ← Unterkategorie
        └── Worldbuilding & Lore ← Thema
```

### Aktuelle Hauptkategorien

Das Tool kommt mit folgenden vordefinierten Kategorien (in `categories.txt`):

- Tabletop RPGs
- Magic: The Gathering
- Content Creation & Video Production
- Storytelling & Creative Writing
- Artificial Intelligence
- Technology & Digital Tools
- Psychology & Mental Health
- Social Skills & Communication
- Mindset & Personal Development
- Business & Finance
- Politics & Society
- Science & History
- Parenting
- Media Analysis
- Comedy & Humor
- **Inbox** *(Auffangkategorie für nicht eindeutig zuordenbare Videos)*

### Was ist die "Inbox"?

Wenn die KI kein passendes Thema findet, ordnet sie das Video in "Inbox" ein. Diese Videos kannst du anschließend mit `review_inbox.py` manuell durchgehen.

### Kategorien anpassen

Du kannst `categories.txt` jederzeit bearbeiten und eigene Kategorien ergänzen. Danach kannst du mit `classify_videos.py` bestehende Videos neu kategorisieren. Details dazu findest du im [Benutzerhandbuch](BENUTZERHANDBUCH.md).

---

## 10. Häufige Probleme & Lösungen

### "ModuleNotFoundError" – Programm-Bibliothek nicht gefunden

**Ursache:** Die virtuelle Umgebung ist nicht aktiviert.

**Lösung:**
```bash
source venv/bin/activate   # Mac/Linux
venv\Scripts\activate      # Windows
```

### Keine Transkripte – Proxy-Fehler

**Ursache:** YouTube blockiert die direkten Anfragen. Dies ist das häufigste Problem.

**Lösung:**
1. Überprüfe deine Proxy-Zugangsdaten in der `.env`-Datei
2. Stelle sicher, dass dein Webshare-Plan aktiv und bezahlt ist
3. Prüfe im Webshare-Dashboard, ob dein Proxy-Kontingent erschöpft ist

### YouTube API Quota erschöpft (Fehler 429 oder 403)

**Ursache:** Das tägliche Limit der YouTube API (10.000 Anfragen/Tag) wurde erreicht.

**Lösung:** Warte bis zum nächsten Tag. Das Kontingent erneuert sich täglich um Mitternacht (Pacific Time). Das Tool erkennt bereits verarbeitete Videos und überspringt sie beim nächsten Start.

### Kein Transkript verfügbar

**Ursache:** Für manche Videos hat YouTube keine automatischen Untertitel generiert (z.B. bei sehr kurzen oder nicht-sprachlichen Videos).

**Verhalten:** Das Tool überspringt solche Videos automatisch und notiert sie im Log.

### OpenAI Fehler – API-Key ungültig oder Guthaben leer

**Ursache:** Entweder ist der API-Key falsch eingetragen, oder das OpenAI-Konto hat kein Guthaben.

**Lösung:**
1. Überprüfe `OPENAI_API_KEY` in der `.env`-Datei
2. Prüfe dein Guthaben auf [platform.openai.com](https://platform.openai.com)

### Ausgabe-Dateien werden nicht erstellt

**Ursache:** Der in `config.py` angegebene Ausgabepfad existiert nicht.

**Lösung:** Überprüfe den `OUTPUT_DIR`-Pfad in `config.py` und stelle sicher, dass der Ordner existiert (oder erstelle ihn manuell).

---

## 11. Glossar

| Begriff | Erklärung |
|---------|-----------|
| **API** | Eine Schnittstelle, über die Programme miteinander kommunizieren. Die YouTube API erlaubt es z.B., Video-Informationen programmatisch abzufragen. |
| **API-Key / API-Schlüssel** | Ein geheimer Code, der dich gegenüber einem Dienst authentifiziert – ähnlich wie ein Passwort. |
| **Atomare Notiz** | Eine kleine, in sich abgeschlossene Notiz zu einem einzigen Konzept oder einer einzigen Idee. |
| **Chunking** | Das Aufteilen langer Texte in kleinere Abschnitte, damit sie in das "Gedächtnis" der KI passen. |
| **Context Window / Kontextfenster** | Die maximale Menge an Text, die eine KI auf einmal "lesen" und verarbeiten kann. |
| **KI / AI** | Künstliche Intelligenz – hier: Sprachmodelle wie GPT-4 (OpenAI) oder Gemini (Google), die Text verstehen und generieren. |
| **Markdown** | Ein einfaches Text-Format, das mit Sonderzeichen formatiert wird (z.B. `**fett**`, `# Überschrift`). Obsidian nutzt Markdown. |
| **Master-Log** | Eine zentrale Übersichtsdatei, die alle jemals verarbeiteten Videos auflistet. |
| **Obsidian** | Eine beliebte App für persönliches Wissensmanagement, die Markdown-Dateien lokal speichert. |
| **Proxy** | Ein Zwischenserver, der Anfragen im Namen deines Computers stellt – für anonymität und um Rate Limiting zu umgehen. |
| **Rate Limiting** | Eine Beschränkung, wie oft ein Dienst innerhalb einer Zeit angefragt werden darf. |
| **Rotating Residential Proxy** | Ein Proxy-Dienst, der bei jeder Anfrage eine andere, echte IP-Adresse verwendet – besonders zuverlässig gegen Rate Limiting. |
| **Taxonomy / Taxonomie** | Ein hierarchisch strukturiertes Ordnungssystem für Themen und Kategorien. |
| **TLDR** | "Too Long; Didn't Read" – eine Ein-Satz-Zusammenfassung des Kerngedankens. |
| **Token** | Die kleinste Einheit, in der KI-Modelle Text verarbeiten. Grob: 1 Token ≈ 0,75 Wörter. |
| **Transkript** | Die wortgetreue schriftliche Abschrift des gesprochenen Inhalts eines Videos (automatisch von YouTube generiert). |
| **Virtuelle Umgebung (venv)** | Ein abgeschlossener Python-Bereich, in dem Bibliotheken installiert werden, ohne das System zu beeinflussen. |
| **YAML-Frontmatter** | Der strukturierte Kopfbereich einer Markdown-Datei, der Metadaten enthält (Datum, Tags, Kategorie, etc.). |

---

*Letzte Aktualisierung: März 2026 | Weitere Details und Optionen findest du im [Benutzerhandbuch](BENUTZERHANDBUCH.md)*

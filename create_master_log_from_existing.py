import sys
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# This script needs to know where your output directory is, so it imports from your config
try:
    import config
except ImportError:
    print("ERROR: Could not import config.py. Make sure this script is in the same directory as your other files.")
    sys.exit(1)

# Regular expressions to find the specific lines in the summary files
PLAYLIST_RE = re.compile(r"\*\*Playlist:\*\* \[\[Playlist (.*?)\]\]")
TITLE_RE = re.compile(r"\*\*Title:\*\* (.*)")

def create_log_from_existing_summaries():
    """
    Scans the summaries directory, extracts metadata from each summary file,
    and generates a new master_summary_log.md file sorted by modification date.
    """
    summaries_dir = config.SUMMARIES_DIR
    output_dir = config.OUTPUT_DIR
    master_log_filepath = output_dir / "master_summary_log.md"

    if not summaries_dir.exists():
        print(f"ERROR: The summaries directory does not exist at: {summaries_dir}")
        return

    print(f"Scanning for summary files in: {summaries_dir}")
    
    # Using rglob to find all matching summary files in all subdirectories
    summary_files = list(summaries_dir.rglob("*– Summary.md"))

    if not summary_files:
        print("No summary files found to process.")
        return

    print(f"Found {len(summary_files)} summary files. Extracting information...")

    summary_data_list = []
    for filepath in summary_files:
        try:
            content = filepath.read_text(encoding="utf-8")
            
            # The video URL is expected to be the first line
            video_url = content.splitlines()[0].strip()

            title_match = TITLE_RE.search(content)
            playlist_match = PLAYLIST_RE.search(content)

            # Extract info, providing defaults if not found
            video_title = title_match.group(1).strip() if title_match else "Untitled Video"
            playlist_name = playlist_match.group(1).strip() if playlist_match else "Unknown Playlist"
            
            # Get the file's last modification time
            mod_time = filepath.stat().st_mtime
            
            # Get the file's path relative to the main output directory for the link
            relative_path = filepath.relative_to(output_dir)

            summary_data_list.append({
                "video_url": video_url,
                "video_title": video_title,
                "playlist_name": playlist_name,
                "link_target": relative_path,
                "mod_time": mod_time,
            })

        except Exception as e:
            print(f"  - Warning: Could not process file {filepath.name}. Reason: {e}")
            continue
    
    # Sort all extracted data by modification time, newest first
    summary_data_list.sort(key=lambda x: x['mod_time'], reverse=True)

    # Group the sorted data by date
    summaries_by_date = defaultdict(list)
    for data in summary_data_list:
        mod_date_str = datetime.fromtimestamp(data['mod_time']).strftime('%Y-%m-%d')
        summaries_by_date[mod_date_str].append(data)
    
    # Get the sorted list of dates (newest first)
    sorted_dates = sorted(summaries_by_date.keys(), reverse=True)

    print("Generating new master summary log content...")
    master_log_md = ""
    for date_str in sorted_dates:
        master_log_md += f"## Processed on {date_str}\n\n"
        # The items for this date are already sorted by time because of the initial sort
        for item in summaries_by_date[date_str]:
            display_text = f"{item['playlist_name']} – {item['video_title']}"
            
            # Convert path to string and ensure forward slashes for Obsidian compatibility
            link_target_str = str(item['link_target']).replace('\\', '/')
            # Remove the ".md" extension for the link
            link_target_stem = link_target_str.removesuffix('.md')
            
            master_log_md += f"{item['video_url']}\n"
            master_log_md += f"[[{link_target_stem}|{display_text}]]\n\n"
            
    # Write the newly generated content to the master log file
    try:
        master_log_filepath.write_text(master_log_md, encoding="utf-8")
        print("-" * 30)
        print(f"SUCCESS: New 'master_summary_log.md' has been created with {len(summary_data_list)} entries.")
        print(f"You can find the file at: {master_log_filepath}")
        print("-" * 30)
    except Exception as e:
        print(f"ERROR: Could not write the new master log file. Reason: {e}")


if __name__ == "__main__":
    create_log_from_existing_summaries()
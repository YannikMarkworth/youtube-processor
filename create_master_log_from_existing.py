import sys
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

try:
    import config
    import file_utils
except ImportError:
    print("ERROR: Could not import config.py or file_utils.py. Make sure this script is in the same directory as your other files.")
    sys.exit(1)

PLAYLIST_RE = re.compile(r"\*\*Playlist:\*\* \[\[Playlist (.*?)\]\]")
TITLE_RE = re.compile(r"\*\*Title:\*\* (.*)")

def create_log_from_existing_summaries():
    summaries_dir = config.SUMMARIES_DIR
    output_dir = config.OUTPUT_DIR
    master_log_filepath = output_dir / "master_summary_log.md"

    if not summaries_dir.exists():
        print(f"ERROR: The summaries directory does not exist at: {summaries_dir}")
        return

    print(f"Scanning for summary files in: {summaries_dir}")
    
    summary_files = list(summaries_dir.rglob("*– Summary.md"))

    if not summary_files:
        print("No summary files found to process.")
        return

    print(f"Found {len(summary_files)} summary files. Extracting information...")

    summary_data_list = []
    for filepath in summary_files:
        try:
            content = filepath.read_text(encoding="utf-8")
            
            video_url = content.splitlines()[0].strip()
            title_match = TITLE_RE.search(content)
            playlist_match = PLAYLIST_RE.search(content)

            video_title = title_match.group(1).strip() if title_match else "Untitled Video"
            playlist_name = playlist_match.group(1).strip() if playlist_match else "Unknown Playlist"
            
            mod_time = filepath.stat().st_mtime
            relative_path = filepath.relative_to(output_dir)

            summary_data_list.append({
                "video_url": video_url,
                "video_title": video_title,
                "playlist_name": playlist_name,
                "link_target": relative_path,
                "mod_time": mod_time,
                "filepath": filepath,
            })

        except Exception as e:
            print(f"  - Warning: Could not process file {filepath.name}. Reason: {e}")
            continue
    
    summary_data_list.sort(key=lambda x: x['mod_time'], reverse=True)

    # --- Generate Playlist-Specific Logs ---
    print("\nGrouping summaries by playlist to create individual logs...")
    summaries_by_playlist = defaultdict(list)
    for data in summary_data_list:
        summaries_by_playlist[data['playlist_name']].append(data)

    for playlist_name, items in summaries_by_playlist.items():
        cleaned_playlist_name = file_utils.clean_filename(playlist_name)
        # Use the new naming convention: [playlistname]_playlist_log.md
        playlist_log_path = config.SUMMARIES_DIR / cleaned_playlist_name / f"{cleaned_playlist_name}_playlist_log.md"
        print(f"  - Generating log for playlist: {playlist_name}...")
        
        by_date = defaultdict(list)
        for item in items:
            mod_date_str = datetime.fromtimestamp(item['mod_time']).strftime('%Y-%m-%d')
            by_date[mod_date_str].append(item)
        
        sorted_dates = sorted(by_date.keys(), reverse=True)
        
        playlist_log_md = ""
        for date_str in sorted_dates:
            playlist_log_md += f"## Processed on {date_str}\n\n"
            for item in by_date[date_str]:
                display_text = f"{item['playlist_name']} – {item['video_title']}"
                link_target_stem = item['filepath'].name.removesuffix('.md')
                
                playlist_log_md += f"{item['video_url']}\n"
                playlist_log_md += f"[[{link_target_stem}|{display_text}]]\n\n"
                
        try:
            playlist_log_path.write_text(playlist_log_md, encoding="utf-8")
        except Exception as e:
            print(f"    - ERROR: Could not write log file for playlist {playlist_name}. Reason: {e}")

    # --- Generate Master Log ---
    print("\nGenerating new master summary log content...")
    master_log_md = ""
    all_summaries_by_date = defaultdict(list)
    for data in summary_data_list:
        mod_date_str = datetime.fromtimestamp(data['mod_time']).strftime('%Y-%m-%d')
        all_summaries_by_date[mod_date_str].append(data)
    
    sorted_all_dates = sorted(all_summaries_by_date.keys(), reverse=True)

    for date_str in sorted_all_dates:
        master_log_md += f"## Processed on {date_str}\n\n"
        for item in all_summaries_by_date[date_str]:
            display_text = f"{item['playlist_name']} – {item['video_title']}"
            link_target_str = str(item['link_target']).replace('\\', '/')
            link_target_stem = link_target_str.removesuffix('.md')
            
            master_log_md += f"{item['video_url']}\n"
            master_log_md += f"[[{link_target_stem}|{display_text}]]\n\n"
            
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
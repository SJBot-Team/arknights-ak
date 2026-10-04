# -*- coding: utf-8 -*-
"""用 yt-dlp 列出 B 站 UP 主视频（flat BV 列表或完整标题）。
用法: python bili_list.py <space_url> [full]
"""
import sys, json
import yt_dlp

def main():
    url = sys.argv[1]
    full = len(sys.argv) > 2 and sys.argv[2] == "full"
    opts = {
        "quiet": True, "no_warnings": True, "skip_download": True,
        "extract_flat": not full, "playlistend": 100,
        "http_headers": {"Referer": "https://www.bilibili.com"},
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        entries = info.get("entries") or []
        print(f"# uploader: {info.get('uploader')} entries: {len(entries)}")
        for e in entries:
            if full:
                print(f"{e.get('id')} | {e.get('upload_date')} | {e.get('duration')}s | {e.get('view_count')} | {e.get('title')}")
            else:
                print(e.get("id"))

if __name__ == "__main__":
    main()

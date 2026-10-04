# -*- coding: utf-8 -*-
"""获取 B 站视频元数据（时长/上传者/日期/标题）。
用法: python bili_meta.py <bvid...>
"""
import sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import yt_dlp

opts = {"quiet": True, "no_warnings": True, "skip_download": True}


def main():
    with yt_dlp.YoutubeDL(opts) as ydl:
        for bv in sys.argv[1:]:
            try:
                info = ydl.extract_info(f"https://www.bilibili.com/video/{bv}", download=False)
                dur = info.get("duration") or 0
                print(f"{bv} | {info.get('uploader')} | {info.get('upload_date')} | {dur//3600}:{(dur%3600)//60:02d}:{dur%60:02d} | {info.get('title')}")
            except Exception as e:
                print(f"{bv} | ERR {str(e)[:100]}")
            time.sleep(1)


if __name__ == "__main__":
    main()

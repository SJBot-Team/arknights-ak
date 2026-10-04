# -*- coding: utf-8 -*-
"""清洗 B 站专栏 md 中的 HTML 标签为可读文本。"""
import os, re, glob

ROOT = r"C:\Users\23922\Documents\ds_harness\ak\_raw\bilibili"


def clean_html(s):
    # 图片
    s = re.sub(r"<figure[^>]*>.*?</figure>", "\n[图]\n", s, flags=re.S)
    s = re.sub(r"<img[^>]*src=\"([^\"]+)\"[^>]*>", r"[图:\1]", s)
    # 标题
    s = re.sub(r"<h1[^>]*>", "\n# ", s)
    s = re.sub(r"<h2[^>]*>", "\n## ", s)
    s = re.sub(r"<h3[^>]*>", "\n### ", s)
    s = re.sub(r"</h[123]>", "\n", s)
    # 段落/换行
    s = re.sub(r"<p[^>]*>", "\n", s)
    s = re.sub(r"</p>", "\n", s)
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<div[^>]*>", "\n", s)
    s = re.sub(r"</div>", "\n", s)
    # 列表
    s = re.sub(r"<li[^>]*>", "\n- ", s)
    s = re.sub(r"</li>", "\n", s)
    s = re.sub(r"<ul[^>]*>", "\n", s)
    s = re.sub(r"<ol[^>]*>", "\n", s)
    # 强调
    s = re.sub(r"<strong[^>]*>", "**", s)
    s = re.sub(r"</strong>", "**", s)
    s = re.sub(r"<span[^>]*>", "", s)
    s = re.sub(r"</span>", "", s)
    s = re.sub(r"<em[^>]*>", "", s)
    s = re.sub(r"</em>", "", s)
    s = re.sub(r"<code[^>]*>", "`", s)
    s = re.sub(r"</code>", "`", s)
    # 链接
    s = re.sub(r'<a[^>]*href="([^"]+)"[^>]*>', r"[\1]", s)
    s = re.sub(r"</a>", "", s)
    # 残留标签
    s = re.sub(r"<[^>]+>", "", s)
    # 空白整理
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def main():
    n = 0
    for p in glob.glob(os.path.join(ROOT, "**", "*.md"), recursive=True):
        with open(p, encoding="utf-8") as f:
            txt = f.read()
        # 只清洗正文部分（head 之后的 --- 之后）
        if "---\n\n" in txt:
            head, body = txt.split("---\n\n", 1)
        else:
            head, body = "", txt
        new_body = clean_html(body)
        if new_body != body:
            with open(p, "w", encoding="utf-8") as f:
                f.write(head + "---\n\n" + new_body)
            n += 1
            print(f"cleaned: {os.path.basename(p)}")
    print(f"total cleaned: {n}")


if __name__ == "__main__":
    main()

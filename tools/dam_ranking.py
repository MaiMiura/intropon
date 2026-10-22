"""DAM公式サイトの「月間ランキング（総合）」を読み取って JSON に保存する。

使い方:
    python3 tools/dam_ranking.py            # 上位50曲 → playlists/dam-monthly.json
    python3 tools/dam_ranking.py --top 30   # 件数を変える

YouTube の動画は別のスクリプト（tools/match_youtube.py）で探して書き足す。
"""
import argparse
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

RANKING_URL = "https://www.clubdam.com/ranking/"
ROOT = Path(__file__).resolve().parent.parent


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "intropon-ranking-bot (+https://maimiura.github.io/intropon/)"})
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read().decode("utf-8")


def text(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def parse_monthly(page):
    # 「月間ランキング」の見出しから、その下の一覧（#monthly-ranking）の終わりまでを切り出す
    start = page.index('id="ranking-monthly"')
    section = page[start:]
    end = section.find('id="ranking-', 10)
    if end > 0:
        section = section[:end]

    m = re.search(r'p-section-header__date">\s*(\d{4})/(\d{2})/(\d{2})', section)
    if not m:
        raise ValueError("月間ランキングの更新日が見つかりません（ページの作りが変わったかも）")
    updated = f"{m[1]}-{m[2]}-{m[3]}"

    # 一覧は最初の <ul class="p-song-list p-ranking-list"> だけ（後ろには別ジャンルの一覧が続く）
    list_start = section.index('id="monthly-ranking"')
    ul_start = section.index('<ul class="p-song-list p-ranking-list"', list_start)
    ranking_list = section[ul_start:section.index("</ul>", ul_start)]

    songs = []
    for item in re.findall(r'<li class="p-song-list__item p-ranking-list__item">(.*?)</li>', ranking_list, re.S):
        rank = re.search(r'p-ranking__num[^"]*">\s*(\d+)', item)
        title = re.search(r'<h4 class="p-song__title">(.*?)</h4>', item, re.S)
        artist = re.search(r'<div class="p-song__artist">(.*?)</div>', item, re.S)
        req_no = re.search(r'requestNo=([\w-]+)', item)
        if not (rank and title and artist):
            continue
        songs.append({
            "rank": int(rank[1]),
            "title": text(title[1]),
            "artist": text(artist[1]),
            "damRequestNo": req_no[1] if req_no else None,
        })
    if not songs:
        raise ValueError("曲が1件も読み取れませんでした（ページの作りが変わったかも）")
    songs.sort(key=lambda s: s["rank"])
    return updated, songs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=50)
    ap.add_argument("--html", help="保存済みのHTMLから読む（テスト用）")
    args = ap.parse_args()

    page = Path(args.html).read_text(encoding="utf-8") if args.html else fetch(RANKING_URL)
    updated, songs = parse_monthly(page)
    songs = songs[: args.top]

    month = updated[:7]
    # 毎月同じファイルを上書きする（前の月から残った曲の動画IDを引き継げるように。過去の分は git に残る）
    out = ROOT / "playlists" / "dam-monthly.json"
    out.parent.mkdir(exist_ok=True)

    # 既にファイルがあれば、確認済みの動画IDなどは引き継ぐ（先月から続けてランクインした曲も）
    prev = {}
    if out.exists():
        for s in json.loads(out.read_text(encoding="utf-8"))["songs"]:
            prev[(s["title"], s["artist"])] = s
    for s in songs:
        old = prev.get((s["title"], s["artist"]), {})
        for key in ("videoId", "videoTitle", "channel", "status", "candidates"):
            if key in old:
                s[key] = old[key]

    data = {
        "name": f"DAM 月間TOP{len(songs)}（{int(month[5:])}月更新）",
        "source": RANKING_URL + "#ranking-monthly",
        "updated": updated,
        "songs": songs,
    }
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{out.relative_to(ROOT)}: {len(songs)}曲（{updated} 更新）", file=sys.stderr)


if __name__ == "__main__":
    main()

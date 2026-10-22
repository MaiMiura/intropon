"""DAMランキングの各曲に、YouTube の公式動画（videoId）を書き足す。

使い方:
    export YOUTUBE_API_KEY=...                # キーはリポジトリに入れない
    python3 tools/match_youtube.py            # playlists/dam-monthly.json の未設定の曲だけ探す
    python3 tools/match_youtube.py --force    # 全曲探し直す
    python3 tools/match_youtube.py --rank 4 13  # 指定した順位の曲だけ探し直す
    python3 tools/match_youtube.py --dry-run  # 保存せず結果だけ表示

YouTube Data API の検索は1回100ユニット（1日の上限は10,000）なので、50曲でだいたい半日分。
上限に達したらそこまでを保存して終わるので、翌日もう一度実行すれば続きから探す。

自信がない曲は videoId を入れずに status: "要確認" と候補（candidates）を残す。
候補を見て正しい動画を選んだら、その曲に "videoId" を書いて "status": "OK" にする。
"""
import argparse
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FILE = ROOT / "playlists" / "dam-monthly.json"
API = "https://www.googleapis.com/youtube/v3/"

# 動画タイトルにこれが入っていたら外す（曲名そのものに入っている場合は除く）
NG_WORDS = [
    "歌ってみた", "うたってみた", "cover", "カバー", "カラオケ", "karaoke", "live", "ライブ",
    "弾いてみた", "叩いてみた", "踊ってみた", "piano", "ピアノ", "guitar", "ギター", "instrumental",
    "off vocal", "オフボーカル", "inst", "remix", "acoustic", "アコースティック", "short", "切り抜き",
    "reaction", "リアクション", "歌詞動画", "fanmade", "nightcore", "1時間", "耐久", "メドレー", "medley",
    "tiktok", "teaser", "ティザー", "trailer", "予告", "dance practice", "踊り方", "lesson", "full ver. cover",
    "ツアー", "tour", "fes", "フェス", "コンサート", "concert", "first take", "collaboration", "コラボ",
    "記念", "海外の反応", "歌詞付き", "立体音響", "ai補正", "upscaling", "dance ver", "bootleg",
]
# 公式っぽさの手がかり
OFFICIAL_WORDS = ["music video", "official", "mv", "pv", "公式", "audio", "lyric video", "リリックビデオ"]

TIE_IN = re.compile(r"[(（【\[][^)）】\]]*(?:主題歌|映画|ドラマ|アニメ|CM|テーマ|挿入歌)[^)）】\]]*[)）】\]]", re.I)

MIN_SEC, MAX_SEC = 120, 600


class QuotaExceeded(Exception):
    pass


def api(endpoint, **params):
    params["key"] = os.environ["YOUTUBE_API_KEY"]
    url = API + endpoint + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as res:
            return json.load(res)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        if e.code == 403 and "quota" in body.lower():
            raise QuotaExceeded() from None
        raise RuntimeError(f"YouTube API エラー {e.code}: {body[:300]}") from None


def norm(s):
    """比較用：全角半角・大文字小文字・空白・記号の違いをなくす"""
    s = unicodedata.normalize("NFKC", s).lower()
    return "".join(c for c in s if unicodedata.category(c)[0] in "LN")


def core_title(title):
    """「奏(かなで)」「点描の唄(feat.井上苑子)」「アイノカタチ feat.HIDE(GReeeeN)」→ 本体の曲名だけ"""
    t = re.split(r"[(（]|\s+feat\.|\s+ft\.", title, maxsplit=1, flags=re.I)[0]
    return t.strip() or title


def duration_sec(iso):
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return ((d * 24 + h) * 60 + mi) * 60 + s


def score(song, video):
    """点数と、落とす理由（あれば）を返す"""
    sn = video["snippet"]
    title, channel = sn["title"], sn["channelTitle"]
    nt, nc = norm(title), norm(channel)
    song_t, song_a = norm(core_title(song["title"])), norm(song["artist"])
    song_full = norm(song["title"] + song["artist"])

    sec = duration_sec(video["contentDetails"]["duration"])
    if not video["status"].get("embeddable", False):
        return None, "外部再生不可"
    blocked = video["contentDetails"].get("regionRestriction", {})
    if "JP" in blocked.get("blocked", []) or ("allowed" in blocked and "JP" not in blocked["allowed"]):
        return None, "日本で再生不可"
    if not MIN_SEC <= sec <= MAX_SEC:
        return None, f"長さ{sec}秒"
    for w in NG_WORDS:
        nw = norm(w)
        if nw and nw in nt and nw not in song_full:
            return None, f"「{w}」を含む"
    # 「(映画『366日』主題歌)」のようなタイアップ表記は除いてから曲名を探す（別の曲を拾わないように）
    if song_t not in norm(TIE_IN.sub("", title)):
        return None, "曲名が入っていない"

    pts = 10
    # 「2008 Ver.」「第5期ver.」など別バージョンはイントロが違うことがあるので自動では選ばない（「full ver.」はOK）
    if re.search(r"(?<!full )ver\b", title, re.I) and "ver" not in song_full:
        pts -= 6
    # 「最後の雨2025」「【茅ケ崎2023】」のような年入り（リメイク・ライブ）、「A × B」のコラボも同様
    if any(y not in song_full for y in re.findall(r"(?:19|20)\d\d", title)):
        pts -= 6
    if re.search(r"\s[×x]\s", title) and "×" not in song["title"]:
        pts -= 6
    is_topic = channel.endswith(" - Topic")
    if song_a and (song_a in nc or (len(nc) >= 2 and nc in song_a)):
        pts += 6  # アーティスト本人のチャンネル（「〇〇 - Topic」も含む）
    elif song_a in nt:
        pts += 2  # タイトルに歌手名はある（レーベルの公式チャンネルなど）
    if is_topic:
        pts += 1  # 音源のみ（映像なし）でもイントロクイズには十分
    if any(norm(w) in nt for w in OFFICIAL_WORDS):
        pts += 2
    if any(w in nc for w in ("official", "公式", "records", "music", "vevo")):
        pts += 2  # 「SUKIMASWITCH OFFICIAL」のように英語表記の公式チャンネル、レーベルのチャンネル
    return pts, None


def search(song):
    q = f"{song['artist']} {core_title(song['title'])}"
    res = api("search", part="snippet", type="video", q=q, maxResults=10,
              regionCode="JP", relevanceLanguage="ja", videoEmbeddable="true")
    ids = [it["id"]["videoId"] for it in res.get("items", [])]
    if not ids:
        return []
    details = api("videos", part="snippet,contentDetails,status", id=",".join(ids))
    by_id = {v["id"]: v for v in details.get("items", [])}

    results = []
    for order, vid in enumerate(ids):
        v = by_id.get(vid)
        if not v:
            continue
        pts, why = score(song, v)
        results.append({
            "videoId": vid,
            "videoTitle": v["snippet"]["title"],
            "channel": v["snippet"]["channelTitle"],
            "score": pts,
            "reason": why,
            "order": order,
        })
    # 点数が同じなら YouTube の検索順を優先
    results.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0), r["order"]))
    return results


def apply(song, results):
    ok = [r for r in results if r["score"] is not None]
    for key in ("videoId", "videoTitle", "channel", "status", "candidates"):
        song.pop(key, None)
    # 本人のチャンネルで公式表記もある（または本人の「- Topic」の音源）なら自動で決める
    if ok and ok[0]["score"] >= 16:
        best = ok[0]
        song.update(videoId=best["videoId"], videoTitle=best["videoTitle"], channel=best["channel"], status="OK")
    else:
        song["status"] = "要確認"
        song["candidates"] = [
            {"videoId": r["videoId"], "videoTitle": r["videoTitle"], "channel": r["channel"],
             **({"note": r["reason"]} if r["reason"] else {})}
            for r in (ok or results)[:3]
        ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?", default=str(DEFAULT_FILE))
    ap.add_argument("--force", action="store_true", help="videoId がある曲も探し直す")
    ap.add_argument("--rank", type=int, nargs="+", help="この順位の曲だけ探し直す（例: --rank 4 13）")
    ap.add_argument("--dry-run", action="store_true", help="保存しない")
    args = ap.parse_args()

    if not os.environ.get("YOUTUBE_API_KEY"):
        sys.exit("環境変数 YOUTUBE_API_KEY を設定してください")

    path = Path(args.file)
    data = json.loads(path.read_text(encoding="utf-8"))

    def write():
        if not args.dry_run:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.rank:
        todo = [s for s in data["songs"] if s["rank"] in args.rank]
    else:
        todo = [s for s in data["songs"] if args.force or (not s.get("videoId") and s.get("status") != "要確認")]
    print(f"{len(todo)}曲を探します", file=sys.stderr)
    try:
        for s in todo:
            apply(s, search(s))
            mark = "✓" if s["status"] == "OK" else "?"
            got = s.get("videoTitle") or " / ".join(c["videoTitle"] for c in s["candidates"]) or "（候補なし）"
            print(f"{mark} {s['rank']:>2}. {s['title']} / {s['artist']} → {got}", file=sys.stderr)
            write()  # 途中で止まっても、そこまでの結果は残す
    except QuotaExceeded:
        print("YouTube API の1日の上限に達しました。明日もう一度実行すると続きから探します。", file=sys.stderr)

    songs = data["songs"]
    ok = sum(1 for s in songs if s.get("status") == "OK")
    check = sum(1 for s in songs if s.get("status") == "要確認")
    print(f"OK {ok}曲 / 要確認 {check}曲 / 未検索 {len(songs) - ok - check}曲", file=sys.stderr)


if __name__ == "__main__":
    main()

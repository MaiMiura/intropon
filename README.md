# イントロポン（スマホ版）

YouTubeのプレイリストを使ったイントロクイズアプリです。ログイン不要・`index.html` 1枚で動きます。

## 遊び方
1. YouTubeのプレイリストURL（公開 or 限定公開）を貼る。動画URLを1行ずつ並べてもOK
2. 「▶ 再生」で曲の頭から流れる（映像は「?」で隠れています）
3. わかったら「■ ストップ」
4. 「正解を見る」で曲名と映像を表示／「続きを流す」「最初から流す」でもう一度聴く
5. 「次の曲へ」

## 公開方法
GitHub Pages（Settings → Pages → Branch を選択）で公開すればスマホから開けます。

## DAMランキングの自動取り込み（作業中）

1. `python3 tools/dam_ranking.py` … DAM公式の月間ランキング（総合）上位50曲を `playlists/dam-monthly-YYYY-MM.json` に保存
2. （次に作る）`tools/match_youtube.py` … 各曲の公式動画を YouTube Data API で探して `videoId` を書き足す
   - APIキーは環境変数 `YOUTUBE_API_KEY` から読む（リポジトリには入れない）
   - 「歌ってみた」「cover」「カラオケ」「Live」などを除外し、公式チャンネル・MV・Official Audio を優先
   - 外部再生できる動画だけ（`videoEmbeddable=true`）、長さ2〜10分
   - 自信がない曲は `status: "要確認"` にして候補を残す
3. （次に作る）アプリのプルダウンに「DAM 月間TOP50」を追加し、正解表示に DAM の正式な曲名・歌手名を使う

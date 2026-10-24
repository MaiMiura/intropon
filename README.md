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

## DAMランキングの自動取り込み

プルダウンの「🏆 DAM 月間TOP50」は `playlists/dam-monthly.json` を読み込みます。正解表示には DAM の正式な曲名・歌手名を使います。

毎月2日に GitHub Actions（`.github/workflows/dam-monthly.yml`）が下の 1・2 を自動で実行し、変わっていればコミットします。
- 事前に Settings → Secrets and variables → Actions → New repository secret で `YOUTUBE_API_KEY` を登録しておく
- Actions タブの「DAM月間ランキング更新」→「Run workflow」で手動でも実行できる
- 実行結果のページに「要確認」の曲の一覧が出る

手で実行するときの手順：

1. `python3 tools/dam_ranking.py` … DAM公式の月間ランキング（総合）上位50曲を `playlists/dam-monthly.json` に上書き保存
   - 先月から続けてランクインした曲は、決まっている動画をそのまま引き継ぐ
2. `python3 tools/match_youtube.py` … 動画が決まっていない曲の公式動画を YouTube Data API で探して `videoId` を書き足す
   - APIキーは環境変数 `YOUTUBE_API_KEY` から読む（リポジトリには入れない）
   - 「歌ってみた」「cover」「カラオケ」「Live」「ツアー」などを除外し、本人・公式チャンネルの MV や「- Topic」の音源を優先
   - 外部再生できて日本で見られる動画だけ、長さ2〜10分
   - 検索は1曲あたり約100ユニット（1日の上限10,000）。上限に達したらそこまで保存して止まるので、翌日もう一度実行すれば続きから
   - `--rank 4 13` で指定した順位の曲だけ探し直せる
3. `status: "要確認"` の曲は `candidates` を見て正しい動画を選び、その曲に `"videoId"` を書いて `"status": "OK"` にする
   - 要確認のままの曲はゲームに出ない

# 画像プレビュー検証用 MD

このファイルを Cursor / VS Code で開いて **Cmd+Shift+V**（または右上の Open Preview to the Side）で
プレビューしてください。下のセクションに画像が並んで表示されれば成功です。

ネット必須なので、Wi-Fi が繋がっていることを確認してください。

---

## 1. PH の thumbnail（imgix CDN 直リンク）

### Ghost — Open-source self-hosted game servers

![Ghost のサムネイル](https://ph-files.imgix.net/f431ed24-8d0b-481b-900d-316ae71959d2.png?auto=format&w=480)

### Pop — Voice messaging

![Pop のサムネイル](https://ph-files.imgix.net/9c14c696-adb2-4ea2-8b48-c4a3c02b1779.svg?auto=format&w=480)

### BugDrop — In-app feedback to GitHub Issues

![BugDrop のサムネイル](https://ph-files.imgix.net/36c63150-48c3-44f0-a23f-288ddb8ba850.png?auto=format&w=480)

---

## 2. PH の media（実際のプロダクトスクショ）

### Ghost のメディア 2 枚

![Ghost media 1](https://ph-files.imgix.net/47018802-fdc4-4946-877d-e05242c51c01.png?auto=format&w=720)

![Ghost media 2](https://ph-files.imgix.net/2e5c35b4-3edb-46e7-986e-825f9ee9bae6.png?auto=format&w=720)

### BugDrop のスクリーンショット

![BugDrop screenshot](https://ph-files.imgix.net/5df60b13-7197-408f-9068-943ee309b738.png?auto=format&w=720)

---

## 3. サマリ表に thumbnail を入れる例（80px 幅）

| サムネ | 名前 | 一言 |
|---|---|---|
| <img src="https://ph-files.imgix.net/f431ed24-8d0b-481b-900d-316ae71959d2.png?auto=format&w=80" width="80"> | Ghost | OSS self-hosted ゲームサーバー |
| <img src="https://ph-files.imgix.net/9c14c696-adb2-4ea2-8b48-c4a3c02b1779.svg?auto=format&w=80" width="80"> | Pop | 音声ファースト・メッセージング |
| <img src="https://ph-files.imgix.net/36c63150-48c3-44f0-a23f-288ddb8ba850.png?auto=format&w=80" width="80"> | BugDrop | アプリ内フィードバック → GitHub Issue |

---

## 4. HTML タグでサイズ制御（width=320）

<img src="https://ph-files.imgix.net/47018802-fdc4-4946-877d-e05242c51c01.png?auto=format" width="320" alt="Ghost screenshot small">

---

## 5. 画像が出ないとき

- Cursor / VS Code を再起動して "Trust" を承認
- 設定 → markdown.preview で `markdown.preview.openMarkdownLinks` 等を確認
- ネット未接続だと当然出ない
- `?auto=format&w=480` の **クエリパラメータが imgix で効いて軽量化されているか**確認するなら、ブラウザで URL を直接開いてみる

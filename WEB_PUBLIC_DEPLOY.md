# Streamlit Web公開手順

このプロジェクトは Streamlit Community Cloud で公開できます。

## 1. ローカルで最終確認

```bash
cd '/Users/yuki/Desktop/code AI/スタホ4シミュレーション'
'/Users/yuki/Desktop/code AI/スタホ4シミュレーション/.venv/bin/python' -m streamlit run app.py
```

## 2. GitHubリポジトリを作成してpush

このフォルダはまだ Git 管理されていないため、最初に初期化します。

```bash
cd '/Users/yuki/Desktop/code AI/スタホ4シミュレーション'
git init
git add .
git commit -m "Initial commit for Streamlit deploy"
```

GitHubで新規リポジトリを作成したら、表示されるURLで push:

```bash
git remote add origin <YOUR_GITHUB_REPO_URL>
git branch -M main
git push -u origin main
```

## 3. Streamlit Community Cloudで公開

1. https://share.streamlit.io にログイン
2. New app をクリック
3. 以下を指定
   - Repository: あなたのGitHubリポジトリ
   - Branch: main
   - Main file path: app.py
4. Deploy を実行

数分でURLが発行されます。

## 4. 更新の反映

コードや saved_configs.json を更新したら、GitHubへ push すると再デプロイされます。

```bash
git add .
git commit -m "Update presets"
git push
```

## 5. 注意点（saved_configs.json の扱い）

- このアプリは `saved_configs.json` を書き換える機能があります。
- Community Cloud は実行環境のローカルファイルが永続ではないため、Web上で行った保存内容は再起動で消える可能性があります。
- 永続化が必要なら次のどれかに変更するのがおすすめです。
  - GitHub / Gist API へ保存
  - Supabase / Firebase / SQLite(外部永続ストレージ)に保存
  - ユーザーにJSONダウンロード・アップロード機能を追加

必要なら次に、永続化対応（例: Supabase保存）まで実装します。

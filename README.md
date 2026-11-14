# USD/JPY 市場ダッシュボード
TradingViewを使わない、静的HTMLとGitHub Actionsによる自動データ取得の試作版です。

## 公開手順
1. GitHubで新しい公開リポジトリを作成し、このフォルダ内のファイルと `.github/workflows/update.yml` をアップロード。
2. リポジトリの **Actions** → **Update market data** → **Run workflow** で初回データ取得。
3. **Settings → Pages → Deploy from a branch → main / (root)** を設定。
4. PagesのURLをAndroidのChromeで開き、「ホーム画面に追加」。

## 制限
- 10指標のうち日本2年債・日本10年債は無料・安定的な自動配信元が未確定のため未取得表示です。
- 米10年−2年は同一観測日のデータのみから算出します。日米金利差は日本のデータがないため未算出です。
- 米国金利・実質金利・VIXはFREDの日次データ。DXY・WTI・ブレントはYahoo Financeの非公式チャートエンドポイントを試行。アクセス拒否時は未取得となります。
- Actionsの15分スケジュールは実行時刻が遅れる場合があります。利用条件や再配布条件を確認して個人利用してください。

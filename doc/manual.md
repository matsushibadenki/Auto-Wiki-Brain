# **Auto-Wiki-Brain 運用マニュアル**

このドキュメントでは、自律型Wiki構築システム **Auto-Wiki-Brain** のインストール、初期設定、日々の運用、およびサーバー移転の手順について説明します。

## **1\. 動作要件 (Prerequisites)**

本システムは Docker コンテナ上で動作します。以下のソフトウェアがインストールされている環境を用意してください。

* **OS**: Linux (Ubuntu 22.04推奨), macOS (Apple Silicon/Intel), Windows (WSL2)  
* **Docker Engine**: v24.0 以上  
* **Docker Compose**: v2.0 以上  
* **メモリ**: 8GB以上推奨 (4GB環境ではスワップ必須)  
* **ディスク容量**: 20GB以上の空き容量（Wikipediaダンプをインポートする場合は+50GB以上推奨）

## **2\. インストール手順 (Installation)**

### **Step 1: ソースコードの配置**

任意のディレクトリ（例: /opt/auto-wiki や \~/auto-wiki）を作成し、ソースコード一式を配置します。

\# ディレクトリの作成と移動  
mkdir auto-wiki  
cd auto-wiki

\# (Gitを使用する場合)  
\# git clone \<repository-url\> .

### **Step 2: 設定ファイルの準備**

配布されているテンプレートファイルを、実際の設定ファイル名に変更します。

1. 環境変数ファイル  
   env.txt を .env にリネームします。  
   mv env.txt .env

   ※ .env ファイルを開き、必要に応じてパスワードやユーザー名を変更してください（デフォルトでも動作します）。  
2. Dockerfile  
   Dockerfile.txt を Dockerfile にリネームします。  
   mv Dockerfile.txt Dockerfile

### **Step 2-2: 編集方針（システムプロンプト）の作成**

Botが記事を執筆する際の「文体」や「構成ルール」を指定するファイルを準備します。

1. **ディレクトリの作成**  
   mkdir config

2. 編集方針ファイルの作成  
   config/ ディレクトリ内に edit\_policy\_ja.txt （英語環境の場合は edit\_policy\_en.txt）を作成し、Botへの指示を記述します。  
   **記述例 (config/edit\_policy\_ja.txt):**  
   あなたはプロの技術ライターです。  
   以下のトピックについて、提供された情報を元に解説記事を書いてください。

   \# ルール  
   \- 「だ・である」調で統一すること。  
   \- 初心者にもわかりやすい平易な言葉を使うこと。  
   \- 箇条書きを多用して構造化すること。  
   \- 冒頭には必ず3行以内の要約を入れること。

### **Step 3: 権限の設定**

各種スクリプトに実行権限を付与します。統合管理ツール manager.sh を使用するため、これに権限を与えておけば十分ですが、念のため全てに付与します。

chmod \+x \*.sh  
chmod \+x maintenance/\*.sh  
chmod \+x maintenance/toolbox/\*.sh

### **Step 4: システムの構築と起動**

まずは自動セットアップスクリプトを実行して、コンテナのビルドと初期設定を行います。

./setup.sh

【推奨】Linux環境（VPSなど）の場合:  
メモリ不足を防ぐため、統合管理ツールを使ってスワップ領域を作成することを強く推奨します。  
./manager.sh  
\# メニューから "3. Setup Swap Memory" を選択

### **Step 5: Wikipedia初期データのインポート（オプション）**

Wikiを最初から知識で満たしたい場合、Wikipediaの日本語ダンプデータをインポートできます。  
この作業には数時間かかり、数十GBのディスク容量を消費するため、必須ではありません。  
実行方法:

./manager.sh  
\# メニューから "10. Import Wikipedia Dump" を選択

## **3\. 動作確認 (Verification)**

セットアップスクリプトが「**🎉 Setup Complete\!**」と表示したら完了です。

### **📘 Wiki サイト**

* **URL**: [http://localhost:8080](https://www.google.com/search?q=http://localhost:8080)  
* Botが稼働すると自動的に記事が増えていきます。

### **⚙️ 管理ダッシュボード**

* **URL**: [http://localhost:8000/dashboard](https://www.google.com/search?q=http://localhost:8000/dashboard)  
* **認証情報** (デフォルト):  
  * User: admin  
  * Pass: secret\_dashboard\_pass

**ダッシュボードの新機能:**

* **System Health Check**: 「Run Diagnostics」ボタンを押すと、AIやデータベースへの接続状況を診断できます。  
* **System Logs**: Botのリアルタイムな思考プロセス（検索・執筆状況）を確認できます。

## **4\. 運用・メンテナンス (Operations)**

本システムは、**統合管理ツール manager.sh** を使用して一元管理できます。

### **統合管理ツールの使い方**

プロジェクトルートで以下のコマンドを実行します。

./manager.sh

表示されるメニューから番号を選んで実行します。

#### **\[ Configuration & Features \]**

1. **Enable Progress Logs (ログ機能有効化)**  
   * ダッシュボードに詳細なBotの活動ログを表示するようにします。  
2. **Create Bot User (Botユーザー作成)**  
   * MediaWiki上にBot用のアカウントを再作成します。「Login Failed」エラーが出る場合に有効です。  
3. **Setup Swap Memory (スワップ領域作成)**  
   * Linux環境でのメモリ不足（OOM Kill）を防ぐため、8GBのスワップファイルを作成します。

#### **\[ Troubleshooting & Fixes \]**

4. **Fix Internal Network (内部ネットワーク修復)**  
   * Botが「接続拒否」される場合や、Wikiがリダイレクトループする場合に使用します。Bot用と人間用のアクセスURLを自動で振り分ける設定を適用します。  
5. **Fix Server Port 8080 (ポート設定修正)**  
   * WikiのURL設定 ($wgServer) を localhost:8080 に明示的に設定します。  
6. **Fix Diagnostics Bug (診断機能修正)**  
   * ダッシュボードの診断機能でエラーが出る場合、プログラムのバグを修正します。  
7. **Repair Wiki Settings (設定ファイル修復)**  
   * LocalSettings.php が破損したり空になった場合に、設定ファイルを再生成します。  
8. **Force Re-install MediaWiki (強制再インストール)**  
   * Dockerのマウント問題でインストールが失敗する場合、一時コンテナを使用して強制的にインストールを実行します。

#### **\[ System Maintenance \]**

9. **Factory Reset (初期化・データ削除)**  
   * **注意**: 全ての記事、画像、データベースを削除し、インストール直後の状態に戻します（確認プロンプトあり）。  
10. **Import Wikipedia Dump (ダンプインポート)**  
    * WikipediaのXMLダンプデータをダウンロードしてインポートします。  
11. **Backup/Migrate (バックアップ・移行)**  
    * 現在のデータ一式を圧縮してバックアップファイルを作成、またはバックアップからの復元を行います。

### **基本操作 (Docker Compose)**

日々の起動・停止は通常のDockerコマンドを使用します。

* **システムの起動**:  
  docker compose up \-d

* **システムの停止**:  
  docker compose down

* **ログの確認 (Botのみ)**:  
  docker compose logs \-f wiki-bot-ja

### **サーバーの移転・バックアップ (Migration)**

サーバー移転や完全バックアップには、manager.sh のメニュー **"11. Backup/Migrate"** を使用します。

1. 旧サーバー (Export):  
   メニューから "11" を選び、export を選択します。auto-wiki-migration.tar.gz が生成されます。  
2. 新サーバー (Import):  
   ファイルを配置し、メニューから "11" を選び、import を選択します。環境が復元されます。

### **ローカル知識の追加 (Importing Local Documents)**

インターネット上の情報だけでなく、手持ちのテキストファイルや社内資料をBotに学習させることができます。

1. ファイルの配置:  
   data/inputs/ ディレクトリに、学習させたい .txt または .md ファイルを置きます。  
   cp my\_document.txt data/inputs/

2. 自動取り込み:  
   システムは 10分ごと にこのフォルダを監視しています。ファイルが検知されると自動的にベクトルデータベースに取り込まれ、data/inputs/processed/ に移動されます。  
3. 活用:  
   取り込まれた知識は、今後の記事執筆時の引用ソースとして使用されるほか、ダッシュボードのチャット機能で質問できるようになります。

## **5\. トラブルシューティング (FAQ)**

**Q. ダッシュボードで "Login Failed" が出る**

* ./manager.sh を実行し、**"2. Create Bot User"** を実行してください。

**Q. Wiki (8080) にアクセスすると localhost (80) に飛ばされる / 接続できない**

* ./manager.sh を実行し、**"5. Fix Server Port 8080"** を実行してください。それでも直らない場合は **"4. Fix Internal Network"** を試してください。

**Q. 記事作成タスクが "PENDING" から進まない**

* BotがWikiに接続できていない可能性があります。./manager.sh から **"4. Fix Internal Network"** を実行し、Botとブラウザの両方がアクセスできる設定に修正してください。

**Q. セットアップ中に "MariaDB timed out" エラーが出る**

* スペックの低いマシンではDBの起動に時間がかかることがあります。setup.sh をもう一度実行してみてください。

**Q. システム診断で "FAIL" が出る**

* **Ollama**: コンテナが起動しているか (docker compose ps) 確認してください。  
* **MediaWiki API**: ./manager.sh の **"6. Fix Diagnostics Bug"** を試してみてください。古いバージョンのバグである可能性があります。

## **6\. ディレクトリ構成**

auto-wiki-brain/  
├── manager.sh           \# 【メイン】統合管理ツール  
├── setup.sh             \# 初回構築スクリプト  
├── docker-compose.yml  
├── .env  
├── src/                 \# ソースコード  
├── data/                \# 永続化データ (DB, 画像, ベクトル)  
├── config/              \# 編集方針ファイル  
└── maintenance/         \# メンテナンス用スクリプト群  
    ├── toolbox/         \# (修復・設定変更用スクリプト)  
    │   ├── fix\_\*.sh  
    │   ├── repair\_\*.sh  
    │   └── ...  
    ├── setup\_swap.sh  
    ├── factory\_reset.sh  
    ├── import\_dump.sh  
    └── migrate.sh  

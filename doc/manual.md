# **Auto-Wiki-Brain 運用マニュアル**

このドキュメントでは、自律型Wiki構築システム **Auto-Wiki-Brain** のインストール、初期設定、日々の運用、およびサーバー移転の手順について説明します。

## **1\. 動作要件 (Prerequisites)**

本システムは Docker コンテナ上で動作します。以下のソフトウェアがインストールされている環境を用意してください。

* **OS**: Linux (Ubuntu 22.04推奨), macOS (Apple Silicon/Intel), Windows (WSL2)  
* **Docker Engine**: v24.0 以上  
* **Docker Compose**: v2.0 以上  
* **メモリ**: 8GB以上推奨 (4GB環境ではスワップ必須)  
* **ディスク容量**: 20GB以上の空き容量

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

各種スクリプトに実行権限を付与します。

chmod \+x setup.sh maintenance/\*.sh

### **Step 4: システムの構築と起動**

自動セットアップスクリプトを実行します。

./setup.sh

Linux環境（VPSなど）の場合:  
メモリ不足を防ぐため、事前にスワップ領域作成スクリプトを実行することを推奨します。  
sudo ./maintenance.sh

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
* **Chat with Wiki Brain**: 右下のチャットボックスから、蓄積された知識についてBotに質問できます。

## **4\. 運用・メンテナンス (Operations)**

### **基本操作**

* **システムの停止**:  
  docker compose down

* **システムの再起動** (設定反映時など):  
  docker compose restart

* **ログの確認**:  
  \# Botの動作ログ（執筆・思考プロセス）  
  docker compose logs \-f wiki-bot

  \# 全体のログ  
  docker compose logs \-f

### **サーバーの移転・完全バックアップ (Migration)**

サーバーを移転する場合や、完全なバックアップを取得する場合は、付属の migrate.sh ツールを使用します。これにより、データベース、画像、AIモデル、設定ファイルの全てを1つのファイルにまとめられます。

#### **A. 旧サーバーでの作業 (Export)**

\# バックアップファイルの作成  
sudo ./maintenance/migrate.sh export my\_wiki\_backup.tar.gz

実行するとDockerが一時停止し、my\_wiki\_backup.tar.gz が生成されます。このファイルを新サーバーへ転送してください。

#### **B. 新サーバーでの作業 (Import)**

新サーバーにファイルを配置し、以下の手順で復元します。

\# 1\. アーカイブの展開  
tar \-xzvf my\_wiki\_backup.tar.gz

\# 2\. リストアとシステムの起動  
sudo ./maintenance/migrate.sh import my\_wiki\_backup.tar.gz

これで旧サーバーの状態がそのまま復元され、Wikiが再開します。

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

**Q. セットアップ中に "MariaDB timed out" エラーが出る**

* スペックの低いマシンではDBの起動に時間がかかることがあります。setup.sh をもう一度実行してみてください。

**Q. "404 Not Found" でWikiが表示されない**

* data/mediawiki\_html/ ディレクトリが空になっていないか確認してください。もし空の場合は、一度コンテナを削除 (docker compose down \-v) してから再度 setup.sh を実行してください。

**Q. 記事が生成されない**

* Botのログを確認してください (docker compose logs wiki-bot)。  
* Ollamaコンテナがモデルをロード中の場合、最初の生成まで数分かかることがあります。

**Q. システム診断で "FAIL" が出る**

* **Ollama**: コンテナが起動しているか (docker compose ps) 確認してください。  
* **Internet**: サーバーのDNS設定やファイアウォールを確認してください。
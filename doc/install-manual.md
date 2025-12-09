# **Auto-Wiki-Brain インストールマニュアル**

このドキュメントでは、自律型Wiki構築システム **Auto-Wiki-Brain** のインストールと初期設定の手順について説明します。

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

Gitを使用する場合はリポジトリをクローンしてください。

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

これらは config/ ディレクトリに配置することで、データベース等のシステムデータ（data/）とは独立して管理され、システム初期化時にも設定を保持できます。

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

   ※ このファイルが存在しない場合、Botはデフォルトのシステムプロンプトを使用します。

### **Step 3: 権限の設定**

セットアップ用スクリプトに実行権限を付与します。

chmod \+x setup.sh maintenance.sh

### **Step 4: システムの構築と起動**

自動セットアップスクリプトを実行します。このスクリプトは以下の処理を自動で行います。

* コンテナのビルドと起動  
* データベース (MariaDB) の初期化待機  
* MediaWiki の自動インストール  
* AIモデル (Gemma 2\) のダウンロード  
* Bot と API サーバーの起動

./setup.sh

Linux環境（VPSなど）の場合:

メモリ不足を防ぐため、事前にスワップ領域作成スクリプトを実行することを推奨します。

sudo ./maintenance.sh

*(macOS環境ではこのスクリプトは自動的にスキップされるため、実行不要です)*

## **3\. 動作確認 (Verification)**

セットアップスクリプトが「**🎉 Setup Complete\!**」と表示したら、インストールは完了です。ブラウザから以下のURLにアクセスしてください。

### **📘 Wiki サイト**

* **URL**: [http://localhost:8080](https://www.google.com/search?q=http://localhost:8080)  
* 記事がまだない場合はトップページが表示されます。Botが稼働すると自動的に記事が増えていきます。

### **⚙️ 管理ダッシュボード**

* **URL**: [http://localhost:8000/dashboard](https://www.google.com/search?q=http://localhost:8000/dashboard)  
* **認証情報** (デフォルト):  
  * User: admin  
  * Pass: secret\_dashboard\_pass  
  * *(.envファイルで変更した場合はその値を使用してください)*

ダッシュボードで「System Status」がすべて緑色になり、「Task Queue」にタスクが表示されていれば、システムは正常に自律動作しています。

## **4\. 運用・メンテナンス (Operations)**

### **システムの停止**

docker compose down

### **システムの再起動**

設定変更などを反映させる場合に使用します。config/ 内のプロンプトファイルを書き換えた場合も再起動が必要です。

docker compose restart

### **ログの確認**

Botの動作状況（検索、執筆のログ）を確認するには以下のコマンドを使用します。

\# Botのログをリアルタイム表示    
docker compose logs \-f wiki-bot

\# 全コンテナのログを表示    
docker compose logs \-f

### **データのバックアップと初期化**

本システムは「設定」と「データ」を分離して管理しています。

* **設定 (config/)**: ユーザーが作成した編集方針ファイルなど。  
* **データ (data/)**: データベース、Wikiの画像、ベクトルインデックス、AIモデルなど。

バックアップ:  
config/ と data/ ディレクトリをバックアップしてください。  
システムの完全初期化（Factory Reset）:  
記事データや学習データを全て消去し、設定（プロンプト等）だけを残して再構築したい場合は、data/ ディレクトリの中身を削除してから再セットアップしてください。  
\# 注意: 全てのWiki記事が消えます！  
docker compose down  
sudo rm \-rf data/\*  
./setup.sh

これにより、config/ に保存された「あなたのBotの人格・編集方針」を維持したまま、新しいWikiとして再スタートできます。

## **5\. トラブルシューティング (FAQ)**

**Q. セットアップ中に "MariaDB timed out" エラーが出る**

* スペックの低いマシンではDBの起動に時間がかかることがあります。setup.sh をもう一度実行してみてください。

**Q. "404 Not Found" でWikiが表示されない**

* data/mediawiki\_html/ ディレクトリが空になっていないか確認してください。もし空の場合は、一度コンテナを削除 (docker compose down \-v) してから再度 setup.sh を実行してください。

**Q. 記事が生成されない**

* Botのログを確認してください (docker compose logs wiki-bot)。  
* Ollamaコンテナがモデルをロード中の場合、最初の生成まで数分かかることがあります。

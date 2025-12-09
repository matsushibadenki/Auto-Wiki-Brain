# **Auto-Wiki-Brain 運用マニュアル**

このドキュメントでは、自律型Wiki構築システム **Auto-Wiki-Brain** のインストール、初期設定、日々の運用、およびトラブルシューティングの手順について説明します。

## **1\. 動作要件 (Prerequisites)**

本システムは Docker コンテナ上で動作します。

* **OS**: Linux (Ubuntu 22.04推奨), macOS (Apple Silicon/Intel), Windows (WSL2)  
* **Docker Engine**: v24.0 以上  
* **Docker Compose**: v2.0 以上  
* **メモリ**: 8GB以上推奨 (4GB以下の環境ではスワップ領域が必須)  
* **ディスク容量**: 20GB以上の空き容量

## **2\. インストール手順 (Installation)**

### **Step 1: ソースコードの配置**

mkdir auto-wiki  
cd auto-wiki  
\# (または git clone \<repository-url\> .)

### **Step 2: 設定ファイルの準備**

テンプレートファイルをリネームして使用します。

1. 環境変数ファイル  
   env.txt を .env にリネームし、パスワード等を設定します。  
   mv env.txt .env

2. Dockerfile  
   Dockerfile.txt を Dockerfile にリネームします。  
   mv Dockerfile.txt Dockerfile

### **Step 3: 編集方針の作成 (Edit Policy)**

Botの記事執筆ルールを指定するファイルを作成します。

1. config ディレクトリを作成。  
2. config/edit\_policy\_ja.txt を作成し、Botへの指示（文体や構成ルール）を記述します。

### **Step 4: システム構築と起動**

初回セットアップスクリプトを実行します。

chmod \+x setup.sh manager.sh  
./setup.sh

【重要】統合管理ツールの使用  
本システムには、設定やメンテナンスを一元管理するツール manager.sh が付属しています。  
セットアップ後は、基本的にこのツール経由で操作を行います。  
./manager.sh

推奨される初期設定:

* **メモリ対策**: メニュー 3\. Setup Swap Memory (Linux環境のみ)  
* **Wiki設定修復**: メニュー 8\. Force Re-install MediaWiki (初回接続エラーが出る場合)

## **3\. 動作確認 (Verification)**

### **📘 Wiki サイト**

* **URL**: [http://localhost:8080](https://www.google.com/search?q=http://localhost:8080)  
* AIが執筆した記事がここに蓄積されます。

### **⚙️ 管理ダッシュボード**

* **URL**: [http://localhost:8000/dashboard](https://www.google.com/search?q=http://localhost:8000/dashboard)  
* **認証**: admin / secret\_dashboard\_pass (デフォルト)

**主な機能:**

* **Manual Task**: 好きなキーワードで記事作成を指示できます。  
* **System Logs**: Botの思考プロセス（検索・執筆状況）をリアルタイムで確認できます。  
* **Diagnostics**: システムの健全性を診断します。

## **4\. 運用・保守 (Operations)**

### **統合管理ツール (manager.sh)**

プロジェクトルートで ./manager.sh を実行すると、以下のメニューが利用可能です。

#### **\[ Configuration & Features \]**

* **1\. Enable Progress Logs**: ダッシュボードでの詳細ログ表示を有効化します。  
* **2\. Create Bot User**: WikiのBotアカウントを再作成します（Login Failed対策）。  
* **3\. Setup Swap Memory**: 8GBのスワップファイルを作成します。

#### **\[ Troubleshooting & Fixes \]**

* **4\. Fix Internal Network**: BotとブラウザのアクセスURL競合を解決します。  
* **5\. Fix Server Port 8080**: WikiのURL設定を修正します。  
* **6\. Fix Diagnostics Bug**: 診断機能のバグを修正します。  
* **7\. Repair Wiki Settings**: LocalSettings.php を修復します。  
* **8\. Force Re-install MediaWiki**: 設定不整合時に、Wikiの設定とBotアカウントを完全再構築します（**推奨**）。

#### **\[ System Maintenance \]**

* **9\. Factory Reset**: 全データを削除し、初期状態に戻します。  
* **10\. Import Wikipedia Dump**: Wikipediaのダンプデータをインポートします。  
* **11\. Backup/Migrate**: データのバックアップ(Export)と復元(Import)を行います。

### **基本操作**

* **起動**: docker compose up \-d  
* **停止**: docker compose down  
* **Botログ確認**: docker compose logs \-f wiki-bot-ja

## **5\. ローカル知識の学習 (Local RAG)**

手持ちのドキュメントをBotに学習させることができます。

1. data/inputs/ に .txt または .md ファイルを配置。  
2. システムが10分ごとに自動検知して学習（ベクトル化）。  
3. ダッシュボードのチャット機能で、その知識について質問可能になります。

## **6\. トラブルシューティング (FAQ)**

**Q. Wiki (8080) につながらない / localhost (80) にリダイレクトされる**

* ./manager.sh の **"8. Force Re-install MediaWiki"** を実行してください。これにより、動的なURL設定を含む正しい設定ファイルが生成されます。

**Q. Botが動かない (500 Server Error)**

* 設定ファイルの構文エラーの可能性があります。上記同様、**"8. Force Re-install MediaWiki"** で設定ファイルをクリーンインストールしてください。

**Q. ダッシュボードで "Login Failed"**

* ./manager.sh の **"2. Create Bot User"** を実行してください。

## **7\. ディレクトリ構成**

auto-wiki-brain/  
├── manager.sh           \# 【メイン】統合管理ツール  
├── setup.sh             \# 初回構築スクリプト  
├── docker-compose.yml  
├── .env  
├── src/                 \# アプリケーションコード  
├── data/                \# 永続化データ (DB, 画像, ベクトル)  
└── maintenance/         \# メンテナンス用スクリプト群  
    ├── toolbox/         \# (修復・設定変更用スクリプト)  
    │   ├── fix\_\*.sh  
    │   ├── repair\_\*.sh  
    │   └── ...  
    ├── setup\_swap.sh  
    └── ...  

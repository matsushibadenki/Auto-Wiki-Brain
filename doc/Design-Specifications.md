# **Auto-Wiki-Brain: 自律進化型ローカルLLM知識ベースシステム**

## **1\. プロジェクト概要 (Overview)**

Auto-Wiki-Brain は、人間の介入を必要とせず、インターネットから自動的に情報を収集・学習し、自身の知識（Wiki記事）を更新・拡張し続ける自律型AIシステムです。  
Wikipediaの全データを初期知識として継承し、ローカルLLM（Ollama/Gemma/Llama）を活用することで、外部APIコストを極限まで抑えた運用を可能にします。さらに、蓄積された知識はRAG（検索拡張生成）APIを通じて外部AIから利用可能です。

## **2\. 設計思想 (Core Philosophy)**

本システムは以下の3つの柱に基づいて設計されています。

### **2.1. 知識の継承 (Standing on the Shoulders of Giants)**

ゼロから知識を構築するのではなく、既存のWikipedia日本語版ダンプデータ（数百万記事）をインポートしてベースラインとします。AIの役割は「全書き」ではなく、ベースラインに対する「差分更新（Patching）」と「新規トピックの発見」に特化させ、計算リソースを効率化します。

### **2.2. 完全ローカル・コストゼロ (Local & Cost-Efficient)**

情報の「検索（Discovery）」、「吟味（Vetting）」、「執筆（Writing）」、「ベクトル化（Embedding）」の全工程を、自社サーバー内のオープンソースモデルで完結させます。

* **推論**: Ollama (Gemma 2 / Llama 3\)  
* **検索**: DuckDuckGo (APIレス) / RSS  
* ベクトルDB: ChromaDB (Local)  
  これにより、記事を1万回更新しても追加コストは発生しません。

### **2.3. 自律性と品質管理 (Autonomy with Quality Control)**

「何をいつ書くか」を人間が指示するのではなく、**優先度付きスケジューラー**が情報の「鮮度（Volatility）」に基づいて決定します。また、AIがネット上の情報を鵜呑みにしないよう、\*\*多段階推論による吟味プロセス（Vetting Agent）\*\*を実装し、情報の信頼性を担保します。

## **3\. システムアーキテクチャ (Architecture)**

システムはDocker Compose上で連携するマイクロサービス群として構成されます。

### **3.1. コンポーネント構成**

graph TD  
    Internet((Internet)) \--\>|RSS/Search| Scheduler\[Task Scheduler\]  
    Scheduler \--\>|Task Queue| Bot\[Wiki Bot Agent\]  
      
    subgraph "VPS Server (Docker)"  
        Bot \--\>|1. Search & Vetting| Ollama\[Local LLM (Ollama)\]  
        Bot \--\>|2. Image Search| Commons\[Wikimedia Commons\]  
        Bot \--\>|3. Update Article| MW\[MediaWiki\]  
        Bot \--\>|4. Update Vector| Chroma\[ChromaDB\]  
          
        MW \<--\> MariaDB\[(MariaDB)\]  
        Chroma \<--\> RAG\_API\[RAG API Server\]  
    end  
      
    External\_AI((External AI)) \--\>|Query| RAG\_API

### **3.2. データフロー**

1. **Discovery (発見)**: スケジューラーがRSSやGoogle Trendsから「急上昇ワード」を検知、または既存記事の「更新期限切れ」を検知し、タスクキューに積む。  
2. **Research (調査)**: BotがWeb検索を実行。検索結果（HTML/Text）を収集。  
3. **Vetting (吟味)**: LLMが検索結果を読み、「記事の出典として適切か（広告やスパムではないか）」を判定。不適切な情報を除外。  
4. **Drafting (執筆)**: 吟味済み情報と既存記事（Old Content）をLLMに渡し、差分更新用のWikitextを生成。  
5. **Publishing (反映)**: MediaWiki API経由で記事を更新。同時にChromaDBのベクトルインデックスも更新。

## **4\. 技術仕様 (Technical Specifications)**

Xserver VPS等の制限されたリソース環境での稼働を前提とした仕様です。

### **4.1. 推奨ハードウェア要件**

* **CPU**: 4 vCPU以上 (推論・ベクトル化用)  
* **RAM**: 8GB以上 (推奨 16GB)  
  * *Note*: 8GB環境ではOllamaとMediaWikiの競合を防ぐため、**必ず4GB以上のスワップ領域**を設定してください。  
* **Storage**: SSD 200GB以上  
  * Wikipedia Dump (XML): \~30GB  
  * MariaDB (Text): \~50GB  
  * ChromaDB (Vector): \~50GB (全記事ベクトル化時)

### **4.2. ソフトウェアスタック**

* **OS**: Ubuntu 22.04 LTS / 24.04 LTS  
* **Container**: Docker 24+, Docker Compose v2  
* **Wiki Engine**: MediaWiki 1.39+ (LTS)  
* **Database**: MariaDB 10.11+  
* **Vector Engine**: ChromaDB  
* **LLM Runtime**: Ollama (モデル: gemma2:9b-quantized または llama3.1:8b)  
* **Language**: Python 3.10+ (Agents & API)

## **5\. ディレクトリ構成 (Directory Structure)**

/opt/auto-wiki/ をルートディレクトリとし、永続化データとコードを分離管理します。

/opt/auto-wiki/  
├── docker-compose.yml       \# サービス定義  
├── .env                     \# 環境変数（パスワード、モデル設定）  
├── README.md                \# 本ドキュメント  
├── src/                     \# アプリケーションソースコード  
│   ├── main.py              \# 自律エージェントのエントリーポイント  
│   ├── api\_server.py        \# 外部AI用 RAG API  
│   ├── bot/                 \# Botロジック  
│   │   ├── wiki\_bot.py      \# 執筆・更新メインクラス  
│   │   ├── commons.py       \# 画像検索エージェント  
│   │   └── vetter.py        \# 情報吟味ロジック  
│   ├── rag/                 \# ベクトル検索ロジック  
│   │   └── vector\_store.py  
│   └── scheduler/           \# タスク管理・トレンド取得  
│       └── task\_manager.py  
├── data/                    \# 【重要】永続化データ（バックアップ対象）  
│   ├── mediawiki\_html/      \# Wiki設定 (LocalSettings.php), 画像  
│   ├── mediawiki\_db/        \# 記事テキストデータ (MariaDB)  
│   ├── chromadb/            \# ベクトルインデックス  
│   ├── ollama/              \# LLMモデルファイル  
│   └── scheduler.db         \# タスク管理DB (SQLite)  
└── maintenance/             \# 運用・保守スクリプト  
    ├── import\_dump.sh       \# Wikiダンプインポート  
    └── setup\_swap.sh        \# メモリ不足対策用スワップ作成

## **6\. セットアップ手順 (Installation)**

### **Step 1: 環境準備 (VPS)**

\# Dockerのインストール  
curl \-fsSL \[https://get.docker.com\](https://get.docker.com) | sh

\# ディレクトリ作成  
mkdir \-p /opt/auto-wiki/data/{mediawiki\_db,mediawiki\_html,chromadb,ollama}  
cd /opt/auto-wiki

\# ソースコードの配置 (git clone または アップロード)  
\# ...

### **Step 2: スワップ領域の作成 (必須)**

LLMロード時のOOM Killを防ぐため、スワップファイルを作成します。

\# maintenance/setup\_swap.sh として作成・実行  
sudo fallocate \-l 8G /swapfile  
sudo chmod 600 /swapfile  
sudo mkswap /swapfile  
sudo swapon /swapfile  
echo '/swapfile none swap sw 0 0' | sudo tee \-a /etc/fstab

### **Step 3: システム起動**

\# .envファイルを編集し、パスワード等を設定  
vim .env

\# コンテナ起動  
docker compose up \-d

### **Step 4: MediaWiki初期設定**

1. ブラウザで http://\<VPS\_IP\>:8080 にアクセス。  
2. GUIに従ってセットアップ（DBホストは mariadb、DBユーザは .env で設定したもの）。  
3. 生成された LocalSettings.php をダウンロードし、サーバーの /opt/auto-wiki/data/mediawiki\_html/ に配置。  
4. **重要**: LocalSettings.php に以下を追記（画像表示用）。  
   $wgEnableUploads \= true;  
   $wgUseInstantCommons \= true; // Wikimedia Commonsの画像を直接表示

### **Step 5: モデルの準備**

docker compose exec ollama ollama pull gemma2

## **7\. 運用・保守 (Operations)**

### **ログの確認**

\# Botの活動ログ（検索、執筆の様子）を確認  
docker compose logs \-f wiki-bot

\# APIサーバーのログ  
docker compose logs \-f rag-api

### **バックアップ**

data/ ディレクトリを丸ごとバックアップすれば復元可能です。ただし、MariaDB稼働中のコピーは整合性が壊れる可能性があるため、ダンプ推奨です。

\# 定期バックアップ例  
docker compose exec mariadb mysqldump \-u root \-p\<ROOT\_PASS\> \--all-databases \> backup\_db.sql  
tar \-czvf wiki\_backup\_$(date \+%F).tar.gz data/ backup\_db.sql

### **トラブルシューティング**

* **Q: Wiki Botが動かない。**  
  * A: docker compose logs wiki-bot でエラーを確認してください。Ollamaへの接続エラーの場合、Ollamaコンテナがモデルロード中で応答していない可能性があります。  
* **Q: 記事生成が遅い。**  
  * A: CPU実行のため、1記事あたり数分かかるのは正常です。高速化したい場合は量子化レベルを下げる（例: 4bit量子化モデルを使用）か、VPSのコア数を増やしてください。

## **8\. ライセンス**

This project is licensed under the MIT License.  
Wikipedia content is licensed under CC BY-SA 3.0.
# **Auto-Wiki-Brain: 自律進化型ローカルLLM知識ベースシステム**

## **1\. プロジェクト概要 (Overview)**

Auto-Wiki-Brain は、人間の介入を必要とせず、インターネットから自動的に情報を収集・学習し、自身の知識（Wiki記事）を更新・拡張し続ける自律型AIシステムです。  
Wikipediaの全データを初期知識として継承し、ローカルLLM（Ollama/Gemma/Llama）を活用することで、外部APIコストを極限まで抑えた運用を可能にします。

## **2\. コントロールパネル (Control Panel) \[NEW\]**

システムの稼働状況を可視化・操作するためのWebダッシュボードを提供します。

### **2.1 機能**

* **Status Monitor**: CPU/メモリ使用率、ディスク容量、Ollamaの接続状態をリアルタイム表示。  
* **Task Queue**: 現在実行中のタスク、待機中のタスク、最近完了したタスクの一覧表示。  
* **Manual Trigger**: 任意のキーワードを入力し、即座に調査・執筆タスクをキューに追加。  
* **Log Viewer**: Botの活動ログ（検索クエリ、吟味結果など）の閲覧。

### **2.2 アクセス方法**

* URL: http://\<VPS\_IP\>:8000/dashboard  
* 認証: Basic認証（.env ファイルの ADMIN\_USER, ADMIN\_PASS で設定）

## **3\. システムアーキテクチャ (Architecture)**

graph TD  
    Internet((Internet)) \--\>|RSS/Search| Scheduler\[Task Scheduler\]  
    AdminUser((Admin User)) \--\>|Web UI| Dashboard\[Control Panel (FastAPI)\]  
    Dashboard \--\>|Manage| Scheduler  
      
    subgraph "VPS Server (Docker)"  
        Bot\[Wiki Bot Agent\] \--\>|Polls| Scheduler  
        Bot \--\>|1. Search & Vetting| Ollama\[Local LLM (Ollama)\]  
        Bot \--\>|2. Image Search| Commons\[Wikimedia Commons\]  
        Bot \--\>|3. Update Article| MW\[MediaWiki\]  
          
        Dashboard \-.-\>|Monitor| Bot  
        Dashboard \-.-\>|Monitor| Ollama  
    end

## **4\. 技術仕様 (Technical Specifications)**

### **4.1 ソフトウェアスタック (追加分)**

* **Dashboard UI**: HTML5 \+ Bootstrap 5 (Jinja2 Template)  
* **Monitoring**: psutil (Python System Monitor)  
* **Security**: HTTP Basic Auth

## **5\. ディレクトリ構成 (Directory Structure)**

src/templates/ ディレクトリを追加し、UIファイルを配置します。

/opt/auto-wiki/
├── docker-compose.yml       # (確認済: 正しい場所にあります)
├── maintenance.sh           # (確認済: 実行権限 chmod +x を忘れずに)
├── Dockerfile               # ⚠️ Dockerfile.txt から名前変更が必要です
├── .env                     # ⚠️ env.txt から名前変更が必要です
├── src/
│   ├── main.py              # (確認済)
│   ├── api_server.py        # (確認済)
│   ├── templates/
│   │   └── dashboard.html   # (確認済)
│   ├── bot/
│   │   ├── __init__.py      # (推奨: 空ファイルでOK)
│   │   ├── wiki_bot.py      # (確認済)
│   │   ├── commons.py       # (確認済)
│   │   └── vetter.py        # (確認済)
│   ├── scheduler/
│   │   ├── __init__.py      # (推奨: 空ファイルでOK)
│   │   └── task_manager.py  # (確認済)
│   └── rag/
│       ├── __init__.py      # (推奨: 空ファイルでOK)
│       └── vector_store.py  # (確認済)
└── data/                    # (Docker起動時に自動作成されますが、フォルダだけ作っておくと安心です)

## **6\. セットアップ手順 (Installation)**

(基本手順は変更なし。.env に管理用パスワードを追加してください)

\# .env に以下を追加  
ADMIN\_USER=admin  
ADMIN\_PASS=secret\_dashboard\_pass  

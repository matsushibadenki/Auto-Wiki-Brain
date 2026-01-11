#!/bin/bash

# enable_progress_log.sh
# Botの動作ログをファイルに記録し、ダッシュボードから見れるようにするスクリプト

echo "📜 Enabling Real-time Progress Logs..."

# --- 1. Botのメインプログラムを修正 (ログ出力機能の追加) ---
# src/main.py を上書きして、標準出力をファイルにも分岐させるLoggerクラスを追加します
cat <<EOF > ./src/main.py
# /opt/auto-wiki/src/main.py
# 日本語タイトル: システム全体の司令塔 (Log-Enabled)
# 目的: スケジューラー、Bot、およびファイル取込のメインループを実行する

import time
import schedule
import os
import sys
import datetime

# パスの追加
sys.path.append("/app")

from src.bot.wiki_bot import LocalWikiBotV2
from src.scheduler.task_manager import WikiScheduler
from src.rag.file_ingestor import LocalFileIngestor

# --- Logger Class Injection ---
# print文をキャプチャしてファイルにも書き込むクラス
class DualLogger(object):
    def __init__(self):
        self.terminal = sys.stdout
        # コンテナ間で共有されている /app/src/ ディレクトリにログを出力
        self.log = open("/app/src/bot.log", "a", encoding="utf-8")
    
    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()
        
    def flush(self):
        self.terminal.flush()
        self.log.flush()

# 標準出力をフック
sys.stdout = DualLogger()

def main():
    # 環境変数からの設定読み込み
    WIKI_LANG = os.getenv("WIKI_LANG", "ja")
    print(f"🚀 Initializing Autonomous Wiki System ({WIKI_LANG.upper()})...")

    WIKI_HOST = os.getenv("WIKI_HOST", "mediawiki:80")
    BOT_USER = os.getenv("BOT_USER", "AdminBot")
    BOT_PASS = os.getenv("BOT_PASS", "password")
    MODEL_NAME = os.getenv("MODEL_NAME", "gemma2")
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434/v1")
    TRENDS_RSS = os.getenv("TRENDS_RSS", "https://trends.google.com/trends/trendingsearches/daily/rss?geo=JP")

    # リトライロジック付きで初期化
    max_retries = 10
    bot = None
    
    for i in range(max_retries):
        try:
            print(f"⏳ Connection attempt {i+1}/{max_retries}...")
            bot = LocalWikiBotV2(
                wiki_host=WIKI_HOST,
                bot_user=BOT_USER,
                bot_pass=BOT_PASS,
                model_name=MODEL_NAME,
                base_url=OLLAMA_HOST,
                lang=WIKI_LANG
            )
            print("✅ Connected to Wiki and AI!")
            break
        except Exception as e:
            print(f"⚠️ Connection failed (Service might be warming up): {e}")
            time.sleep(10)
    
    if not bot:
        print("❌ Fatal Error: Could not connect to services.")
        return

    # スケジューラーとインジェスターの初期化
    scheduler = WikiScheduler(db_path="/app/scheduler.db", rss_url=TRENDS_RSS)
    ingestor = LocalFileIngestor(input_dir="/app/data/inputs")

    # 定期ジョブ
    schedule.every(4).hours.do(scheduler.fetch_external_trends)
    schedule.every(10).minutes.do(ingestor.process_new_files)

    # 初回実行
    scheduler.fetch_external_trends()
    ingestor.process_new_files()

    print("🔄 Starting main loop...")
    while True:
        try:
            schedule.run_pending()
            
            task_topic = scheduler.get_next_task()
            if task_topic:
                print(f"▶ PROCESSING: {task_topic}")
                bot.update_article(task_topic)
                scheduler.complete_task(task_topic)
                
                print("💤 Cooling down (30s)...")
                time.sleep(30)
            else:
                time.sleep(10)
                
        except Exception as e:
            print(f"❌ Error in main loop: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
EOF

# --- 2. APIサーバーを修正 (ログ読み込み機能の追加) ---
# src/api_server.py を上書きして、/api/logs で実際のファイルを返すようにします
cat <<EOF > ./src/api_server.py
# /opt/auto-wiki/src/api_server.py
# 日本語タイトル: RAG APIサーバー + システム管理ダッシュボード (Log-Enabled)

import os
import psutil
from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
import secrets
import sys
from openai import OpenAI

sys.path.append("/app")
from src.scheduler.task_manager import WikiScheduler
from src.rag.vector_store import WikiVectorDB
from src.utils.diagnostics import SystemDiagnostics

app = FastAPI(title="Auto-Wiki Control Panel", version="2.5.0")
templates = Jinja2Templates(directory="/app/src/templates")
security = HTTPBasic()

# DB接続
scheduler = WikiScheduler(db_path="/app/scheduler.db")
vector_db = WikiVectorDB()
diagnostics = SystemDiagnostics()

# LLM接続
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "gemma2")
llm_client = OpenAI(base_url=OLLAMA_HOST, api_key="ollama")

SYSTEM_LANG = os.getenv("WIKI_LANG", "ja")

# 翻訳辞書 (省略せず保持)
TRANSLATIONS = {
    "ja": {
        "title": "Auto-Wiki Brain 管理パネル",
        "chat_title": "Wiki Brainと対話",
        "chat_placeholder": "蓄積された知識について質問してください...",
        "btn_send": "送信",
        "system_status": "システムステータス",
        "cpu": "CPU使用率",
        "memory": "メモリ",
        "disk": "ディスク空き容量",
        "ai_engine": "AIエンジン",
        "task_queue": "タスクキュー",
        "refresh": "更新",
        "col_topic": "トピック",
        "col_priority": "優先度",
        "col_status": "ステータス",
        "col_next": "次回実行",
        "no_tasks": "タスクはありません。",
        "manual_task": "手動タスク追加",
        "label_topic": "トピック / キーワード",
        "label_priority": "優先度",
        "prio_high": "高 (即時)",
        "prio_normal": "通常",
        "btn_add": "キューに追加",
        "logs": "システムログ",
        "placeholder_topic": "例: GPT-5, 量子コンピュータ",
        "badge_high": "高",
        "badge_norm": "並"
    },
    "en": {
        "title": "Auto-Wiki Brain Dashboard",
        "chat_title": "Chat with Wiki Brain",
        "chat_placeholder": "Ask about accumulated knowledge...",
        "btn_send": "Send",
        "system_status": "System Status",
        "cpu": "CPU Usage",
        "memory": "Memory",
        "disk": "Disk Free",
        "ai_engine": "AI Engine",
        "task_queue": "Task Queue",
        "refresh": "Refresh",
        "col_topic": "Topic",
        "col_priority": "Priority",
        "col_status": "Status",
        "col_next": "Next Run",
        "no_tasks": "No tasks found.",
        "manual_task": "Add Manual Task",
        "label_topic": "Topic / Keyword",
        "label_priority": "Priority",
        "prio_high": "High (Immediate)",
        "prio_normal": "Normal",
        "btn_add": "Add to Queue",
        "logs": "System Logs",
        "placeholder_topic": "e.g. GPT-5, Quantum Computing",
        "badge_high": "High",
        "badge_norm": "Normal"
    }
}

def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = os.getenv("ADMIN_USER", "admin").encode("utf8")
    correct_password = os.getenv("ADMIN_PASS", "password").encode("utf8")
    if not (secrets.compare_digest(credentials.username.encode("utf8"), correct_username) and
            secrets.compare_digest(credentials.password.encode("utf8"), correct_password)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password", headers={"WWW-Authenticate": "Basic"})
    return credentials.username

class TaskCreate(BaseModel):
    topic: str
    priority: int = 10

class SearchQuery(BaseModel):
    query: str
    limit: int = 3

class ChatRequest(BaseModel):
    message: str

@app.get("/")
async def root():
    return RedirectResponse(url="/dashboard")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, username: str = Depends(get_current_username)):
    trans = TRANSLATIONS.get(SYSTEM_LANG, TRANSLATIONS["en"])
    return templates.TemplateResponse("dashboard.html", {"request": request, "username": username, "lang": SYSTEM_LANG, "trans": trans})

@app.get("/api/status")
def get_system_status(username: str = Depends(get_current_username)):
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "memory_percent": vm.percent,
        "memory_used_gb": round(vm.used / (1024**3), 2),
        "memory_total_gb": round(vm.total / (1024**3), 2),
        "disk_free_gb": round(disk.free / (1024**3), 2),
        "ollama_status": "Online"
    }

@app.get("/api/tasks")
def get_tasks(limit: int = 50, username: str = Depends(get_current_username)):
    return scheduler.get_recent_tasks(limit=limit)

@app.post("/api/tasks")
def add_manual_task(task: TaskCreate, username: str = Depends(get_current_username)):
    scheduler.add_or_update_task(task.topic, priority=task.priority)
    return {"message": f"Task '{task.topic}' added successfully."}

@app.get("/api/logs")
def get_bot_logs(username: str = Depends(get_current_username)):
    """Botのログファイルを読み込んで返す"""
    log_path = "/app/src/bot.log"
    logs = []
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                # 最後の30行を取得して新しい順に並べる
                lines = f.readlines()
                logs = [line.strip() for line in lines[-30:]]
                logs.reverse() 
        except Exception:
            logs = ["Could not read log file."]
    else:
        logs = ["Waiting for bot activity..."]
    
    return {"logs": logs}

@app.get("/api/diagnostics/run")
def run_system_diagnostics(username: str = Depends(get_current_username)):
    results = diagnostics.run_all_checks()
    return {"results": results}

@app.post("/api/rag/search")
def search_knowledge_base(query: SearchQuery):
    results = vector_db.search(query.query, n_results=query.limit)
    return {
        "query": query.query,
        "documents": results['documents'][0],
        "metadatas": results['metadatas'][0]
    }

@app.post("/api/rag/chat")
def chat_with_brain(req: ChatRequest):
    user_msg = req.message
    search_res = vector_db.search(user_msg, n_results=3)
    documents = search_res['documents'][0]
    metadatas = search_res['metadatas'][0]
    
    context_text = ""
    for i, doc in enumerate(documents):
        topic = metadatas[i].get("topic", "Unknown")
        context_text += f"[Source: {topic}]\n{doc}\n\n"
        
    if not context_text:
        context_text = "No relevant knowledge found in the database."

    system_prompt = "You are 'Wiki Brain'. Answer using the Context Information."
    if SYSTEM_LANG == "ja":
        system_prompt = """
        あなたは「Wiki Brain」です。以下の【参照知識】のみを使用して答えてください。
        知識がない場合は「情報がありません」と答えてください。
        """

    prompt = f"【参照知識】\n{context_text}\n\n【質問】\n{user_msg}"

    try:
        resp = llm_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        return {"answer": resp.choices[0].message.content, "sources": [m.get("topic") for m in metadatas]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
EOF

# --- 3. 再起動 ---
echo "🔄 Restarting Bot and Dashboard to apply logging..."
docker compose restart wiki-bot-ja dashboard-ja

echo "🎉 Done! Check the 'System Logs' on your dashboard."
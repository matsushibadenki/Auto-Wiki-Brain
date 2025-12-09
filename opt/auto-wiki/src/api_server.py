# /opt/auto-wiki/src/api_server.py
# 日本語タイトル: RAG APIサーバー + システム管理ダッシュボード (Log-Enabled + Task Deletion)

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

app = FastAPI(title="Auto-Wiki Control Panel", version="2.6.0")
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
        "col_action": "操作", # 追加
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
        "col_action": "Action", # 追加
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

# --- 追加: タスク削除エンドポイント ---
@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int, username: str = Depends(get_current_username)):
    try:
        scheduler.delete_task(task_id)
        return {"message": f"Task ID {task_id} deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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

# /opt/auto-wiki/src/api_server.py
# RAG APIサーバー + システム管理ダッシュボード
# 目的: 管理画面の提供と外部AI向けの検索API提供

import os
import psutil
from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
import secrets
import sys

sys.path.append("/app")
from src.scheduler.task_manager import WikiScheduler
from src.rag.vector_store import WikiVectorDB

app = FastAPI(
    title="Auto-Wiki Control Panel",
    description="自律型Wikiシステムの管理とRAG API",
    version="2.0.0"
)

templates = Jinja2Templates(directory="/app/src/templates")
security = HTTPBasic()

# DB接続
scheduler = WikiScheduler(db_path="/app/scheduler.db")
vector_db = WikiVectorDB()

# --- 認証ロジック ---
def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = os.getenv("ADMIN_USER", "admin").encode("utf8")
    correct_password = os.getenv("ADMIN_PASS", "password").encode("utf8")
    
    is_correct_username = secrets.compare_digest(credentials.username.encode("utf8"), correct_username)
    is_correct_password = secrets.compare_digest(credentials.password.encode("utf8"), correct_password)
    
    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# --- API Models ---
class TaskCreate(BaseModel):
    topic: str
    priority: int = 10

class SearchQuery(BaseModel):
    query: str
    limit: int = 3

# --- Dashboard Endpoints ---

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, username: str = Depends(get_current_username)):
    """管理画面のHTMLを返す"""
    return templates.TemplateResponse("dashboard.html", {"request": request, "username": username})

@app.get("/api/status")
def get_system_status(username: str = Depends(get_current_username)):
    """サーバーのリソース状況を返す"""
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # Ollama簡易チェック
    ollama_status = "Online" # 実際はrequests.get(OLLAMA_HOST)などで確認推奨

    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "memory_percent": vm.percent,
        "memory_used_gb": round(vm.used / (1024**3), 2),
        "memory_total_gb": round(vm.total / (1024**3), 2),
        "disk_free_gb": round(disk.free / (1024**3), 2),
        "ollama_status": ollama_status
    }

@app.get("/api/tasks")
def get_tasks(limit: int = 50, username: str = Depends(get_current_username)):
    """タスク一覧を取得"""
    return scheduler.get_recent_tasks(limit=limit)

@app.post("/api/tasks")
def add_manual_task(task: TaskCreate, username: str = Depends(get_current_username)):
    """手動でタスクを追加"""
    scheduler.add_or_update_task(task.topic, priority=task.priority)
    return {"message": f"Task '{task.topic}' added successfully."}

@app.get("/api/logs")
def get_bot_logs(username: str = Depends(get_current_username)):
    """ログ表示（簡易実装）"""
    return {"logs": ["Logs should be viewed via 'docker compose logs' in production."]}

# --- RAG Endpoints (Public) ---

@app.post("/api/rag/search")
def search_knowledge_base(query: SearchQuery):
    """外部AI向けの知識検索API"""
    results = vector_db.search(query.query, n_results=query.limit)
    return {
        "query": query.query,
        "documents": results['documents'][0],
        "metadatas": results['metadatas'][0]
    }
# /opt/auto-wiki/src/api_server.py
# 日本語タイトル: RAG APIサーバー + システム管理ダッシュボード (v2.3)
# 目的: 管理画面の提供、およびRAGチャット機能のバックエンド処理

import os
import psutil
from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
import secrets
import sys
from openai import OpenAI
from src.utils.diagnostics import SystemDiagnostics

sys.path.append("/app")
from src.scheduler.task_manager import WikiScheduler
from src.rag.vector_store import WikiVectorDB

app = FastAPI(
    title="Auto-Wiki Control Panel",
    description="自律型Wikiシステムの管理とRAG API",
    version="2.3.0"
)

templates = Jinja2Templates(directory="/app/src/templates")
security = HTTPBasic()

# DB接続
scheduler = WikiScheduler(db_path="/app/scheduler.db")
vector_db = WikiVectorDB()

# LLM接続 (Ollama) - チャット応答用
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "gemma2")
llm_client = OpenAI(base_url=OLLAMA_HOST, api_key="ollama")


# 診断クラスのインスタンス化
diagnostics = SystemDiagnostics()

# --- 言語設定と翻訳辞書 ---
SYSTEM_LANG = os.getenv("WIKI_LANG", "ja")

TRANSLATIONS = {
    "ja": {
        "title": "Auto-Wiki Brain 管理パネル",
        "chat_title": "Wiki Brainと対話",
        "chat_placeholder": "蓄積された知識について質問してください...",
        "btn_send": "送信",
        "system_status": "システムステータス",
        # ... (既存の翻訳は維持) ...
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
        # ... (Existing translations) ...
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

# --- 認証ロジック (既存維持) ---
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

class ChatRequest(BaseModel):
    message: str

# --- Dashboard Endpoints ---

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, username: str = Depends(get_current_username)):
    trans = TRANSLATIONS.get(SYSTEM_LANG, TRANSLATIONS["en"])
    return templates.TemplateResponse(
        "dashboard.html", 
        {
            "request": request, 
            "username": username,
            "lang": SYSTEM_LANG,
            "trans": trans
        }
    )

@app.get("/api/status")
def get_system_status(username: str = Depends(get_current_username)):
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    ollama_status = "Online" 
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
    return scheduler.get_recent_tasks(limit=limit)

@app.post("/api/tasks")
def add_manual_task(task: TaskCreate, username: str = Depends(get_current_username)):
    scheduler.add_or_update_task(task.topic, priority=task.priority)
    return {"message": f"Task '{task.topic}' added successfully."}

@app.get("/api/logs")
def get_bot_logs(username: str = Depends(get_current_username)):
    return {"logs": ["Logs should be viewed via 'docker compose logs' in production."]}

# --- RAG Endpoints ---

@app.post("/api/rag/search")
def search_knowledge_base(query: SearchQuery):
    """単純なベクトル検索結果を返す"""
    results = vector_db.search(query.query, n_results=query.limit)
    return {
        "query": query.query,
        "documents": results['documents'][0],
        "metadatas": results['metadatas'][0]
    }

@app.post("/api/rag/chat")
def chat_with_brain(req: ChatRequest):
    """
    [NEW] Wiki Brainとの対話API
    1. VectorDBから関連知識を検索
    2. LLMにコンテキストとして与えて回答生成
    """
    user_msg = req.message
    
    # 1. 知識検索
    search_res = vector_db.search(user_msg, n_results=3)
    documents = search_res['documents'][0]
    metadatas = search_res['metadatas'][0]
    
    context_text = ""
    for i, doc in enumerate(documents):
        topic = metadatas[i].get("topic", "Unknown")
        context_text += f"[Source: {topic}]\n{doc}\n\n"
        
    if not context_text:
        context_text = "No relevant knowledge found in the database."

    # 2. 回答生成
    system_prompt = """
    You are 'Wiki Brain', an intelligent assistant powered by a local knowledge base.
    Answer the user's question using ONLY the provided Context Information.
    If the answer is not in the context, say "I don't have that information in my knowledge base yet."
    """
    if SYSTEM_LANG == "ja":
        system_prompt = """
        あなたは「Wiki Brain」、ローカル知識ベースを持つAIアシスタントです。
        以下の【参照知識】のみを使用して、ユーザーの質問に答えてください。
        もし知識ベースに答えがない場合は、「私のデータベースにはまだその情報がありません。」と答えてください。
        """

    prompt = f"""
    【参照知識】
    {context_text}

    【ユーザーの質問】
    {user_msg}
    """

    try:
        resp = llm_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        answer = resp.choices[0].message.content
        return {
            "answer": answer,
            "sources": [m.get("topic") for m in metadatas]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
        
# --- Diagnostics Endpoints ---
@app.get("/api/diagnostics/run")
def run_system_diagnostics(username: str = Depends(get_current_username)):
    """システム診断を実行して結果を返す"""
    results = diagnostics.run_all_checks()
    return {"results": results}

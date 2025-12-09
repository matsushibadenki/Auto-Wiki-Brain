# /opt/auto-wiki/src/main.py
# 日本語タイトル: システム全体の司令塔 (Idle-Maintenance Enabled)
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
class DualLogger(object):
    def __init__(self):
        self.terminal = sys.stdout
        self.log = open("/app/log/bot.log", "a", encoding="utf-8")
    
    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()
        
    def flush(self):
        self.terminal.flush()
        self.log.flush()

sys.stdout = DualLogger()

def main():
    WIKI_LANG = os.getenv("WIKI_LANG", "ja")
    print(f"🚀 Initializing Autonomous Wiki System ({WIKI_LANG.upper()})...")

    WIKI_HOST = os.getenv("WIKI_HOST", "mediawiki:80")
    BOT_USER = os.getenv("BOT_USER", "AdminBot")
    BOT_PASS = os.getenv("BOT_PASS", "password")
    MODEL_NAME = os.getenv("MODEL_NAME", "gemma2")
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434/v1")
    TRENDS_RSS = os.getenv("TRENDS_RSS", "https://trends.google.com/trends/trendingsearches/daily/rss?geo=JP")

    # Retry Connection
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
            print(f"⚠️ Connection failed: {e}")
            time.sleep(10)
    
    if not bot:
        print("❌ Fatal Error: Could not connect to services.")
        return

    scheduler = WikiScheduler(db_path="/app/scheduler.db", rss_url=TRENDS_RSS)
    ingestor = LocalFileIngestor(input_dir="/app/data/inputs")

    # Regular Jobs
    schedule.every(4).hours.do(scheduler.fetch_external_trends)
    schedule.every(10).minutes.do(ingestor.process_new_files)

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
                
                # 【修正】クールダウンを30秒から1秒に短縮
                # 次のタスクがあれば即座に取り掛かる
                print("⚡ Ready for next task...") 
                time.sleep(1) 
            else:
                # タスクがない時は少し休む（CPU節約）
                time.sleep(5)
                
        except Exception as e:
            print(f"❌ Error in main loop: {e}")
            time.sleep(60)
                
        except Exception as e:
            print(f"❌ Error in main loop: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()

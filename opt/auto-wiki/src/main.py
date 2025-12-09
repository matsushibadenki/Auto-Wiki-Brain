# /opt/auto-wiki/src/main.py
# 日本語タイトル: システム全体の司令塔 (v2.2)
# 目的: スケジューラー、Bot、およびファイル取込のメインループを実行する

import time
import schedule
import os
import sys

# パスの追加
sys.path.append("/app")

from src.bot.wiki_bot import LocalWikiBotV2
from src.scheduler.task_manager import WikiScheduler
from src.rag.file_ingestor import LocalFileIngestor # 追加

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
    ingestor = LocalFileIngestor(input_dir="/app/data/inputs") # 追加

    # 定期ジョブ
    schedule.every(4).hours.do(scheduler.fetch_external_trends)
    schedule.every(10).minutes.do(ingestor.process_new_files) # 10分ごとにローカルファイルを確認

    # 初回実行
    scheduler.fetch_external_trends()
    ingestor.process_new_files()

    print("🔄 Starting main loop...")
    while True:
        try:
            schedule.run_pending()
            
            task_topic = scheduler.get_next_task()
            if task_topic:
                print(f"\n▶ PROCESSING: {task_topic}")
                bot.update_article(task_topic)
                scheduler.complete_task(task_topic)
                
                print("💤 Cooling down (30s)...")
                time.sleep(30)
            else:
                time.sleep(10)
                
        except Exception as e:
            print(f"\n❌ Error in main loop: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()

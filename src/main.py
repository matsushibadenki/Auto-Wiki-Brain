# /opt/auto-wiki/src/main.py
# システム全体の司令塔
# 目的: スケジューラーとBotのメインループを実行する

import time
import schedule
import os
import sys

# パスの追加
sys.path.append("/app")

from src.bot.wiki_bot import LocalWikiBotV2
from src.scheduler.task_manager import WikiScheduler

def main():
    print("🚀 Initializing Autonomous Wiki System...")
    
    # 環境変数からの設定読み込み
    WIKI_HOST = os.getenv("WIKI_HOST", "mediawiki:80")
    BOT_USER = os.getenv("BOT_USER", "AdminBot")
    BOT_PASS = os.getenv("BOT_PASS", "password")
    MODEL_NAME = os.getenv("MODEL_NAME", "gemma2")
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434/v1")

    # リトライロジック付きで初期化 (WikiやOllamaの起動待ち)
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
                base_url=OLLAMA_HOST
            )
            print("✅ Connected to Wiki and AI!")
            break
        except Exception as e:
            print(f"⚠️ Connection failed (Service might be warming up): {e}")
            time.sleep(10)
    
    if not bot:
        print("❌ Fatal Error: Could not connect to services.")
        # ここで終了せず、リトライし続けるか、あるいは終了させるかは運用方針による
        # 今回はDockerのリスタートポリシーに任せて終了する
        return

    scheduler = WikiScheduler(db_path="/app/scheduler.db")

    # 定期ジョブ: 4時間ごとにトレンド収集
    schedule.every(4).hours.do(scheduler.fetch_external_trends)
    
    # 初回起動時にトレンド取得を一回実行
    scheduler.fetch_external_trends()

    print("🔄 Starting main loop...")
    while True:
        try:
            schedule.run_pending()
            
            task_topic = scheduler.get_next_task()
            if task_topic:
                print(f"\n▶ PROCESSING: {task_topic}")
                bot.update_article(task_topic)
                scheduler.complete_task(task_topic)
                
                # GPU/CPU Cool down
                print("💤 Cooling down (30s)...")
                time.sleep(30)
            else:
                # アイドル時は少し長めに待機
                time.sleep(10)
                
        except Exception as e:
            print(f"\n❌ Error in main loop: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
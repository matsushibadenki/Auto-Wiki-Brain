# /opt/auto-wiki/src/scheduler/task_manager.py
# タスク管理マネージャー
# 目的: タスクのキューイング、トレンド情報の取得、DB操作を行う

import sqlite3
import time
import feedparser
from datetime import datetime, timedelta

class WikiScheduler:
    def __init__(self, db_path="/app/scheduler.db", rss_url="https://trends.google.com/trends/trendingsearches/daily/rss?geo=JP"):
        self.db_path = db_path
        self.rss_url = rss_url
        self._init_db()
        self._reset_stuck_tasks() # 起動時にスタックしたタスクをリセット

    def _init_db(self):
        """データベースとテーブルの初期化"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT UNIQUE NOT NULL,
                priority INTEGER DEFAULT 5,
                status TEXT DEFAULT 'PENDING',  -- PENDING, RUNNING, FINISHED
                next_run TIMESTAMP,
                last_run TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    def _reset_stuck_tasks(self):
        """起動時にRUNNING状態のままのタスクをPENDINGに戻す（異常終了対策）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE tasks SET status = 'PENDING' WHERE status = 'RUNNING'")
        if cursor.rowcount > 0:
            print(f"🔄 Reset {cursor.rowcount} stuck tasks from RUNNING to PENDING.")
        conn.commit()
        conn.close()

    def fetch_external_trends(self):
        """Google Trends (RSS) から急上昇ワードを取得してタスクに追加"""
        print(f"🌍 Fetching external trends from {self.rss_url}...")
        
        try:
            feed = feedparser.parse(self.rss_url)
            
            count = 0
            for entry in feed.entries:
                topic = entry.title
                # 新規トレンドは高優先度(8)で追加
                if self.add_or_update_task(topic, priority=8):
                    count += 1
            print(f"🌍 Added {count} new trending topics.")
        except Exception as e:
            print(f"⚠️ Failed to fetch trends: {e}")

    def add_or_update_task(self, topic: str, priority: int = 5, volatility_days: int = 1):
        """
        タスクを追加または更新する
        Return: True if new task added, False if existed
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 既存チェック
        cursor.execute("SELECT id, status FROM tasks WHERE topic = ?", (topic,))
        row = cursor.fetchone()
        
        if row:
            conn.commit()
            conn.close()
            return False
        else:
            # 新規追加
            next_run = datetime.now()
            cursor.execute('''
                INSERT INTO tasks (topic, priority, status, next_run)
                VALUES (?, ?, 'PENDING', ?)
            ''', (topic, priority, next_run))
            conn.commit()
            conn.close()
            return True

    def get_next_task(self):
        """実行すべきタスクを一つ取得し、RUNNING状態にする"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now()
        
        # 優先度順、かつ実行時刻が到来しているもの
        cursor.execute('''
            SELECT id, topic FROM tasks 
            WHERE status = 'PENDING' AND next_run <= ?
            ORDER BY priority DESC, next_run ASC
            LIMIT 1
        ''', (now,))
        
        row = cursor.fetchone()
        if row:
            task_id, topic = row
            cursor.execute("UPDATE tasks SET status = 'RUNNING' WHERE id = ?", (task_id,))
            conn.commit()
            conn.close()
            return topic
        
        conn.close()
        return None

    def complete_task(self, topic: str):
        """タスクを完了状態にする"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE tasks 
            SET status = 'FINISHED', last_run = ? 
            WHERE topic = ?
        ''', (datetime.now(), topic))
        conn.commit()
        conn.close()

    def get_recent_tasks(self, limit: int = 50) -> list:
        """
        管理画面用：タスク一覧を取得する
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # 実行中、保留中、完了の順に取得
        cursor.execute('''
            SELECT topic, priority, status, next_run 
            FROM tasks
            ORDER BY 
                CASE status
                    WHEN 'RUNNING' THEN 1
                    WHEN 'PENDING' THEN 2
                    ELSE 3
                END,
                next_run ASC
            LIMIT ?
        ''', (limit,))
        
        tasks = []
        for row in cursor.fetchall():
            tasks.append({
                "topic": row[0],
                "priority": row[1],
                "status": row[2],
                "next_run": row[3] if row[3] else "Now"
            })
        conn.close()
        return tasks

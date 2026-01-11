# /opt/auto-wiki/src/scheduler/task_manager.py
# タスク管理マネージャー (v2.8 - タスク削除機能追加)
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

    def _get_conn(self):
        """タイムアウト設定付きのDB接続を取得"""
        return sqlite3.connect(self.db_path, timeout=30.0)

    def _init_db(self):
        """データベースとテーブルの初期化"""
        conn = self._get_conn()
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
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("UPDATE tasks SET status = 'PENDING' WHERE status = 'RUNNING'")
        if cursor.rowcount > 0:
            print(f"🔄 Reset {cursor.rowcount} stuck tasks from RUNNING to PENDING.")
        conn.commit()
        conn.close()

    def schedule_maintenance_tasks(self, interval_days=7):
        """アイドル時に実行: 古い記事を再チェックリストに追加する"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        threshold = datetime.now() - timedelta(days=interval_days)
        cursor.execute('''
            SELECT id, topic FROM tasks 
            WHERE status = 'FINISHED' 
            AND (last_run IS NULL OR last_run < ?)
            ORDER BY last_run ASC
            LIMIT 1
        ''', (threshold,))
        
        row = cursor.fetchone()
        if row:
            task_id, topic = row
            print(f"♻️  Scheduling maintenance for old article: {topic}")
            cursor.execute('''
                UPDATE tasks 
                SET status = 'PENDING', priority = 3, next_run = ? 
                WHERE id = ?
            ''', (datetime.now(), task_id))
            conn.commit()
            conn.close()
            return True
            
        conn.close()
        return False

    def fetch_external_trends(self):
        """Google Trends (RSS) から急上昇ワードを取得してタスクに追加"""
        print(f"🌍 Fetching external trends from {self.rss_url}...")
        
        try:
            feed = feedparser.parse(self.rss_url)
            
            count = 0
            for entry in feed.entries:
                topic = entry.title
                if self.add_or_update_task(topic, priority=8):
                    count += 1
            print(f"🌍 Added {count} new trending topics.")
        except Exception as e:
            print(f"⚠️ Failed to fetch trends: {e}")

    def add_or_update_task(self, topic: str, priority: int = 5, volatility_days: int = 1):
        """タスクを追加または更新する"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, status FROM tasks WHERE topic = ?", (topic,))
        row = cursor.fetchone()
        
        if row:
            if row[1] == 'FINISHED':
                next_run = datetime.now()
                cursor.execute('''
                    UPDATE tasks 
                    SET status = 'PENDING', priority = ?, next_run = ? 
                    WHERE id = ?
                ''', (priority, next_run, row[0]))
                conn.commit()
                conn.close()
                return True
            
            conn.commit()
            conn.close()
            return False
        else:
            next_run = datetime.now()
            cursor.execute('''
                INSERT INTO tasks (topic, priority, status, next_run)
                VALUES (?, ?, 'PENDING', ?)
            ''', (topic, priority, next_run))
            conn.commit()
            conn.close()
            return True

    # --- 追加: タスク削除メソッド ---
    def delete_task(self, task_id: int):
        """指定されたIDのタスクを削除する"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        conn.close()

    def get_next_task(self):
        """実行すべきタスクを一つ取得し、RUNNING状態にする"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        now = datetime.now()

        # ゾンビタスクの救出 (30分タイムアウト)
        timeout_threshold = now - timedelta(minutes=30)
        cursor.execute('''
            UPDATE tasks 
            SET status = 'PENDING' 
            WHERE status = 'RUNNING' AND last_run < ?
        ''', (timeout_threshold,))
        if cursor.rowcount > 0:
            print(f"🚑 Recovered {cursor.rowcount} timed-out tasks.")
            conn.commit()
        
        cursor.execute('''
            SELECT id, topic FROM tasks 
            WHERE status = 'PENDING' AND next_run <= ?
            ORDER BY priority DESC, next_run ASC
            LIMIT 1
        ''', (now,))
        
        row = cursor.fetchone()
        if row:
            task_id, topic = row
            cursor.execute("UPDATE tasks SET status = 'RUNNING', last_run = ? WHERE id = ?", (now, task_id))
            conn.commit()
            conn.close()
            return topic
        
        conn.close()
        return None

    def complete_task(self, topic: str):
        """タスクを完了状態にする"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE tasks 
            SET status = 'FINISHED', last_run = ?, next_run = NULL 
            WHERE topic = ?
        ''', (datetime.now(), topic))
        conn.commit()
        conn.close()

    def get_recent_tasks(self, limit: int = 50) -> list:
        """
        管理画面用：タスク一覧を取得する
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        # 実行中、保留中、完了の順に取得
        cursor.execute('''
            SELECT id, topic, priority, status, next_run 
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
                "id": row[0],      # IDを追加
                "topic": row[1],
                "priority": row[2],
                "status": row[3],
                "next_run": row[4] if row[4] else "Now"
            })
        conn.close()
        return tasks
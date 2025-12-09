# /opt/auto-wiki/src/utils/diagnostics.py
# システム診断ユーティリティ
# 目的: 外部サービス(Ollama, Wiki, Net)の接続状況を能動的にテストする

import os
import requests
import shutil
import mwclient
from openai import OpenAI

class SystemDiagnostics:
    def __init__(self):
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://ollama:11434/v1")
        self.wiki_host = os.getenv("WIKI_HOST", "mediawiki:80")
        self.wiki_user = os.getenv("BOT_USER", "AdminBot")
        self.wiki_pass = os.getenv("BOT_PASS", "password")
        # OllamaのベースURL調整 (/v1 を除く)
        self.ollama_base = self.ollama_host.replace("/v1", "")

    def run_all_checks(self) -> list:
        """全診断を実行し、結果リストを返す"""
        results = []
        results.append(self._check_internet())
        results.append(self._check_ollama())
        results.append(self._check_mediawiki_api())
        results.append(self._check_disk_space())
        return results

    def _check_internet(self):
        """1. インターネット接続確認 (Google Trendsへのアクセス)"""
        try:
            # 実際に使用しているRSS URLへアクセス
            url = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=JP"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                return {"name": "Internet Connection", "status": "OK", "msg": "Online (Google Trends Reachable)"}
            else:
                return {"name": "Internet Connection", "status": "WARN", "msg": f"Status {resp.status_code}"}
        except Exception as e:
            return {"name": "Internet Connection", "status": "FAIL", "msg": str(e)}

    def _check_ollama(self):
        """2. AIエンジン (Ollama) 接続確認"""
        try:
            # 単純なバージョン確認などで生存確認
            # OpenAI互換エンドポイントではなく、Ollamaネイティブのルートを叩く
            resp = requests.get(self.ollama_base, timeout=3)
            if resp.status_code == 200:
                return {"name": "AI Engine (Ollama)", "status": "OK", "msg": "Ready to Generate"}
            else:
                return {"name": "AI Engine (Ollama)", "status": "FAIL", "msg": f"Unreachable (Status {resp.status_code})"}
        except Exception as e:
            return {"name": "AI Engine (Ollama)", "status": "FAIL", "msg": f"Connection Error: {e}"}

    def _check_mediawiki_api(self):
        """3. MediaWiki API ログイン確認"""
        try:
            site = mwclient.Site(self.wiki_host, path='/', scheme='http')
            site.login(self.wiki_user, self.wiki_pass)
            # サイト情報を取得してみる
            info = site.site_info
            return {"name": "MediaWiki API", "status": "OK", "msg": f"Connected ({info.get('sitename', 'Wiki')})"}
        except Exception as e:
            return {"name": "MediaWiki API", "status": "FAIL", "msg": f"Login Failed: {e}"}

    def _check_disk_space(self):
        """4. ディスク容量チェック (1GB未満で警告)"""
        try:
            total, used, free = shutil.disk_usage("/")
            free_gb = free // (2**30)
            if free_gb < 1:
                return {"name": "Disk Space", "status": "WARN", "msg": f"Low Space: {free_gb}GB free"}
            return {"name": "Disk Space", "status": "OK", "msg": f"Healthy ({free_gb}GB free)"}
        except Exception as e:
            return {"name": "Disk Space", "status": "FAIL", "msg": str(e)}
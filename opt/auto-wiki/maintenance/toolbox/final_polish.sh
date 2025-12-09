#!/bin/bash

# final_polish.sh
# 1. MediaWikiのCSSパス設定を修正
# 2. ダッシュボードのインターネット接続診断URLを修正

echo "✨ Applying Final Polish..."

# --- 1. CSS/パス設定の修正 ---
CONFIG_FILE="./data/mediawiki_html_ja/LocalSettings.php"

if [ -f "$CONFIG_FILE" ]; then
    echo "🎨 Fixing CSS paths in LocalSettings.php..."
    
    # 念のため既存の設定があれば削除（重複防止）
    # Linux/Mac両対応のため一時ファイルを使用
    sed '/$wgScriptPath/d' "$CONFIG_FILE" > "${CONFIG_FILE}.tmp" && mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
    sed '/$wgResourceBasePath/d' "$CONFIG_FILE" > "${CONFIG_FILE}.tmp" && mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"

    # 正しいパス設定を追記
    cat <<EOF >> "$CONFIG_FILE"

# --- Fix CSS/Resource Paths ---
# これによりCSSや画像が正しく読み込まれます
\$wgScriptPath = "";
\$wgResourceBasePath = "";
EOF
else
    echo "⚠️ Warning: LocalSettings.php not found. Skipping CSS fix."
fi

# --- 2. 診断プログラムの修正 (URL変更) ---
DIAG_FILE="./src/utils/diagnostics.py"

if [ -f "$DIAG_FILE" ]; then
    echo "🏥 Updating Diagnostics URL to a more stable one..."
    
    # Pythonファイルを書き換えて、不安定なRSS URLではなく Wikipediaのトップページを確認するように変更
    cat <<EOF > "$DIAG_FILE"
# /opt/auto-wiki/src/utils/diagnostics.py
# システム診断ユーティリティ (Fixed: Stable URL & site object)

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
        self.ollama_base = self.ollama_host.replace("/v1", "")

    def run_all_checks(self) -> list:
        results = []
        results.append(self._check_internet())
        results.append(self._check_ollama())
        results.append(self._check_mediawiki_api())
        results.append(self._check_disk_space())
        return results

    def _check_internet(self):
        """1. インターネット接続確認"""
        try:
            # 変更: Google Trends RSS -> Wikipedia (より安定)
            url = "https://www.wikipedia.org"
            headers = {
                "User-Agent": "Mozilla/5.0 (Auto-Wiki-Brain HealthCheck)"
            }
            resp = requests.get(url, headers=headers, timeout=5)
            
            if resp.status_code == 200:
                return {"name": "Internet Connection", "status": "OK", "msg": "Online (Wikipedia Reachable)"}
            else:
                return {"name": "Internet Connection", "status": "WARN", "msg": f"Status {resp.status_code}"}
        except Exception as e:
            return {"name": "Internet Connection", "status": "FAIL", "msg": str(e)}

    def _check_ollama(self):
        """2. AIエンジン (Ollama) 接続確認"""
        try:
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
            info = site.site 
            return {"name": "MediaWiki API", "status": "OK", "msg": f"Connected ({info.get('sitename', 'Wiki')})"}
        except Exception as e:
            return {"name": "MediaWiki API", "status": "FAIL", "msg": f"Login Failed: {e}"}

    def _check_disk_space(self):
        """4. ディスク容量チェック"""
        try:
            total, used, free = shutil.disk_usage("/")
            free_gb = free // (2**30)
            if free_gb < 1:
                return {"name": "Disk Space", "status": "WARN", "msg": f"Low Space: {free_gb}GB free"}
            return {"name": "Disk Space", "status": "OK", "msg": f"Healthy ({free_gb}GB free)"}
        except Exception as e:
            return {"name": "Disk Space", "status": "FAIL", "msg": str(e)}
EOF
else
    echo "⚠️ Warning: $DIAG_FILE not found. Skipping Diagnostics fix."
fi

# 再起動
echo "🔄 Restarting services..."
docker compose restart mediawiki-ja dashboard-ja

echo "✅ All polish tasks complete!"
echo "   - Check Wiki (Correct Design): http://localhost:8080"
echo "   - Check Dashboard (Green Status): http://localhost:8000/dashboard"
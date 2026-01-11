#!/bin/bash

# fix_internal_network.sh
# ブラウザ(localhost)とBot(内部通信)の両方に対応できるよう設定を修正するスクリプト

echo "🔧 Configuring Dual-Access Network Settings..."

CONFIG_FILE="./data/mediawiki_html_ja/LocalSettings.php"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Error: LocalSettings.php not found."
    exit 1
fi

# 1. 以前の固定設定($wgServer = ...)を削除
#    Linux/Mac互換のため一時ファイルを使用
sed '/$wgServer = "http:\/\/localhost:8080";/d' "$CONFIG_FILE" > "${CONFIG_FILE}.tmp" && mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"

# 2. 動的な設定を追記
#    アクセスしてくる相手(Hostヘッダ)に合わせて、$wgServerを自動切替します
cat <<EOF >> "$CONFIG_FILE"

# --- Dynamic Server URL Setting ---
# ブラウザからのアクセスと、Botからの内部アクセスを両立させる設定
if ( isset( \$_SERVER['HTTP_HOST'] ) && \$_SERVER['HTTP_HOST'] ) {
    \$wgServer = "http://" . \$_SERVER['HTTP_HOST'];
} else {
    \$wgServer = "http://localhost:8080"; # CLIやフォールバック用
}
EOF

echo "✅ Configuration updated."

# 3. サービス再起動
#    Botが停止している可能性が高いので、Botも明示的に再起動します
echo "🔄 Restarting Wiki and Bot..."
docker compose restart mediawiki-ja wiki-bot-ja

echo "🎉 Fix applied!"
echo "   1. Check Dashboard: Task should change to RUNNING soon."
echo "   2. If not, please run: 'docker compose logs wiki-bot-ja'"
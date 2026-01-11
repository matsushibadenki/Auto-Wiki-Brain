#!/bin/bash

# fix_server_port.sh
# MediaWikiの$wgServer設定にポート8080を明記して、リダイレクト地獄を直すスクリプト

echo "🔧 Fixing MediaWiki Server URL setting..."

# 対象の設定ファイル
CONFIG_FILE="./data/mediawiki_html_ja/LocalSettings.php"

# ファイルがあるか確認
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Error: $CONFIG_FILE not found."
    exit 1
fi

# 既に設定があるか確認して、なければ追記
if grep -q "\$wgServer =" "$CONFIG_FILE"; then
    echo "ℹ️  \$wgServer is already set. Updating it..."
    # 既存の行を置換（sedコマンドで強制書き換え）
    # Linux/Mac両対応のため一時ファイルを使用
    sed '/$wgServer =/d' "$CONFIG_FILE" > "${CONFIG_FILE}.tmp" && mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
fi

# 正しい設定を追記
cat <<EOF >> "$CONFIG_FILE"

# --- Fix Server Port ---
# これがないと http://localhost (80) にリダイレクトされてしまいアクセスできません
\$wgServer = "http://localhost:8080";
EOF

echo "✅ Configuration updated."

# 再起動して設定を読み込ませる
echo "🔄 Restarting MediaWiki container..."
docker compose restart mediawiki-ja

echo "🎉 Done! Please try accessing: http://localhost:8080"
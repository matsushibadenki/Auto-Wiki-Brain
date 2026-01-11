#!/bin/bash

# fix_config_syntax.sh
# LocalSettings.php の構文エラーを修正し、Bot接続を安定させるスクリプト

echo "🔧 Fixing LocalSettings.php Syntax..."

CONFIG_FILE="./data/mediawiki_html_ja/LocalSettings.php"

# パス補正（どこから実行されても大丈夫なように）
if [ ! -f "$CONFIG_FILE" ]; then
    # もし toolbox 内で実行された場合
    CONFIG_FILE="../../data/mediawiki_html_ja/LocalSettings.php"
fi

if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Error: LocalSettings.php not found at $CONFIG_FILE"
    exit 1
fi

# 1. バックアップ作成
cp "$CONFIG_FILE" "${CONFIG_FILE}.bak"

# 2. 問題のある箇所（$wgServerの設定部分）を一旦削除
#    Linux/Mac互換のため一時ファイルを使用
grep -v "\$wgServer =" "$CONFIG_FILE" > "${CONFIG_FILE}.tmp" && mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"

# 3. 正しいロジックを追記
#    CLIモード（Botからのアクセス）とWebモードを判定する安全な書き方
cat <<EOF >> "$CONFIG_FILE"

# --- Fixed Server URL Setting ---
if ( defined( 'MW_API' ) || ( isset( \$_SERVER['HTTP_HOST'] ) && \$_SERVER['HTTP_HOST'] ) ) {
    // WebブラウザまたはAPI経由のアクセス
    \$wgServer = "http://" . \$_SERVER['HTTP_HOST'];
} else {
    // CLIまたは内部通信のフォールバック
    \$wgServer = "http://localhost:8080";
}

// Botがコンテナ名でアクセスしてきた場合の特例対応
if ( isset( \$_SERVER['SERVER_NAME'] ) && \$_SERVER['SERVER_NAME'] === 'mediawiki-ja' ) {
    \$wgServer = "http://mediawiki-ja";
}
EOF

# 4. 権限修正
chmod 666 "$CONFIG_FILE"

# 5. 再起動
echo "🔄 Restarting System..."
docker compose restart mediawiki-ja wiki-bot-ja

echo "✅ Fix applied!"
echo "   Please check logs: 'docker compose logs -f wiki-bot-ja'"
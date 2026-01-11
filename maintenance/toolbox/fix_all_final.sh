#!/bin/bash

# fix_all_final.sh
# CSSパスの自動検出設定と、Bot接続の完全修復を行う最終スクリプト

# 色設定
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# 環境変数の読み込み補正
PROJECT_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$PROJECT_ROOT" || exit

CONFIG_FILE="./data/mediawiki_html_ja/LocalSettings.php"

if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}❌ Error: LocalSettings.php not found.${NC}"
    exit 1
fi

echo -e "${GREEN}🔧 Applying Final Fixes (CSS & Bot Connection)...${NC}"

# 1. バックアップ
cp "$CONFIG_FILE" "${CONFIG_FILE}.bak_final"

# 2. 既存のパス設定を削除 (grep -v で除外)
grep -v "\$wgScriptPath =" "$CONFIG_FILE" | \
grep -v "\$wgResourceBasePath =" | \
grep -v "\$wgStylePath =" | \
grep -v "\$wgLogo =" | \
grep -v "\$wgServer =" > "${CONFIG_FILE}.tmp"

# 3. 決定版の設定を追記
#    $wgScriptPath を固定値ではなく、Webサーバー環境変数から自動検出させます。
#    これにより、/html でも /w でも空文字でも、正しいパスが適用されます。

cat <<EOF >> "${CONFIG_FILE}.tmp"

# --- Final Auto-Configuration ---

# 1. パスの自動検出 (CSS/画像崩れ対策)
# SCRIPT_NAME (/html/index.php) からディレクトリ部分 (/html) を抽出します
if ( isset( \$_SERVER['SCRIPT_NAME'] ) ) {
    \$wgScriptPath = preg_replace( '/\/[^\/]+$/', '', \$_SERVER['SCRIPT_NAME'] );
} else {
    \$wgScriptPath = ""; # フォールバック
}

\$wgResourceBasePath = \$wgScriptPath;
\$wgStylePath = "\$wgScriptPath/skins";
\$wgLogo = "\$wgResourceBasePath/resources/assets/wiki.png";

# 2. サーバーURLの自動検出 (Bot接続対策)
if ( isset( \$_SERVER['HTTP_HOST'] ) && \$_SERVER['HTTP_HOST'] ) {
    \$wgServer = "http://" . \$_SERVER['HTTP_HOST'];
} else {
    \$wgServer = "http://localhost:8080";
}

# 3. 必須設定
\$wgEnableUploads = true;
\$wgUseInstantCommons = true;
\$wgHashedUploadDirectory = false;
\$wgShowExceptionDetails = true;
EOF

# ファイルの置き換え
mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
chmod 666 "$CONFIG_FILE"

# 4. Botユーザーの権限再設定 (念のため)
echo "   🤖 Refreshing Bot Permissions..."
docker compose restart mediawiki-ja
sleep 5
docker compose exec mediawiki-ja php maintenance/createAndPromote.php \
    --bot --force \
    AdminBot password > /dev/null 2>&1

# 5. Bot再起動
echo "   🔄 Restarting Bot..."
docker compose restart wiki-bot-ja

echo -e "${GREEN}✅ All Fixes Applied!${NC}"
echo "   1. Reload Wiki (Ctrl+F5/Cmd+Shift+R): http://localhost:8080"
echo "   2. Check if CSS is loaded."
echo "   3. Add a NEW task (e.g., 'Apple') to Dashboard and wait."
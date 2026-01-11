#!/bin/bash

# /opt/auto-wiki/maintenance/generate_settings.sh
# MediaWikiの設定ファイル (LocalSettings.php) をCLIで自動再生成するスクリプト
# 使用法: ./maintenance/generate_settings.sh [ja|en]

LANG_TARGET=${1:-"ja"} # デフォルトは ja
CONTAINER_NAME="mediawiki-${LANG_TARGET}"
SETTINGS_PATH="./data/mediawiki_html_${LANG_TARGET}/LocalSettings.php"

# 色の定義
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# ルートディレクトリへ移動
cd "$(dirname "$0")/.." || exit

# .envの読み込み
if [ -f .env ]; then
    export $(cat .env | grep -v '#' | xargs)
else
    echo -e "${RED}❌ Error: .env file not found.${NC}"
    exit 1
fi

echo -e "${YELLOW}⚙️  Regenerating LocalSettings.php for [${LANG_TARGET}]...${NC}"

# 1. コンテナ実行確認
if ! docker compose ps --services --filter "status=running" | grep -q "${CONTAINER_NAME}"; then
    echo -e "${RED}❌ Error: Container ${CONTAINER_NAME} is not running.${NC}"
    echo "   Please start the system first: docker compose up -d"
    exit 1
fi

# 2. 既存ファイルのバックアップ
if [ -f "$SETTINGS_PATH" ]; then
    BACKUP_NAME="${SETTINGS_PATH}.bak.$(date +%Y%m%d%H%M%S)"
    echo -e "   📦 Backing up existing file to: ${BACKUP_NAME}"
    mv "$SETTINGS_PATH" "$BACKUP_NAME"
fi

# 3. インストーラーの実行 (LocalSettings.phpの生成)
# 注意: 既にDBが存在する場合、インストーラーは警告を出すことがありますが、
# 設定ファイルの生成自体は行われます。
echo -e "   🚀 Running MediaWiki installer..."

DB_NAME="my_wiki_${LANG_TARGET}"

docker compose exec ${CONTAINER_NAME} php maintenance/install.php \
    --dbname="${DB_NAME}" \
    --dbuser=wikiuser \
    --dbpass="${WIKI_DB_PASS}" \
    --dbserver=mariadb \
    --lang="${LANG_TARGET}" \
    --pass="${ADMIN_PASS}" \
    --scriptpath="" \
    "AutoWiki-${LANG_TARGET^^}" "${ADMIN_USER}"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ LocalSettings.php generated successfully.${NC}"
else
    echo -e "${RED}❌ Installation command failed.${NC}"
    # 失敗した場合はバックアップを戻す
    if [ -f "$BACKUP_NAME" ]; then
        mv "$BACKUP_NAME" "$SETTINGS_PATH"
        echo "   Restored backup."
    fi
    exit 1
fi

# 4. カスタム設定の追記
echo -e "   📝 Appending custom settings..."

cat <<EOF >> "$SETTINGS_PATH"

// --- Auto-Wiki-Brain Custom Settings ---
\$wgEnableUploads = true;
\$wgUseInstantCommons = true;
\$wgHashedUploadDirectory = false;
\$wgAllowExternalImages = true;

// Performance Tuning
\$wgMainCacheType = CACHE_ACCEL;
EOF

echo -e "${GREEN}🎉 Done! MediaWiki has been reconfigured.${NC}"
echo -e "   You may need to restart the container: docker compose restart ${CONTAINER_NAME}"
```

### 使い方

1.  スクリプトに実行権限を与えます。
    ```bash
    chmod +x maintenance/generate_settings.sh
    ```

2.  実行します（引数で言語 `ja` または `en` を指定できます）。
    ```bash
    # 日本語Wikiの設定を再生成
    ./maintenance/generate_settings.sh ja
    
    # 英語Wikiの設定を再生成
    ./maintenance/generate_settings.sh en
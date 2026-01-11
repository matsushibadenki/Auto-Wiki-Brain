#!/bin/bash

# fix_fatal_error.sh
# MediaWikiのDBと設定を完全に初期化して再構築するスクリプト

# 色設定
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# .envの読み込み
if [ -f .env ]; then
    export $(cat .env | grep -v '#' | xargs)
else
    echo -e "${RED}❌ Error: .env file not found.${NC}"
    exit 1
fi

echo -e "${GREEN}🔧 Starting Deep Repair for MediaWiki (JA)...${NC}"

# 1. データベースのクリーンアップ (整合性を確保するため一旦削除)
echo "   🧹 Dropping existing database to ensure clean install..."
docker compose exec mariadb mysql -u root -p"${DB_ROOT_PASS}" -e "DROP DATABASE IF EXISTS my_wiki_ja;"

# 2. LocalSettings.php を空にする（ホスト側）
#    これをしておかないと、インストーラーが「既に設定済み」と誤認することがあります
> ./data/mediawiki_html_ja/LocalSettings.php

# 3. インストーラーの実行
#    --confpath /tmp に出力させ、既存のバインドマウントとの競合を避けます
echo "   🚀 Running MediaWiki installer..."
docker compose exec mediawiki-ja php maintenance/install.php \
    --dbname=my_wiki_ja \
    --dbuser=wikiuser \
    --dbpass="${WIKI_DB_PASS}" \
    --dbserver=mariadb \
    --lang=ja \
    --pass="${ADMIN_PASS}" \
    "AutoWiki-JA" "${ADMIN_USER}" \
    --confpath /tmp

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Installer failed. Check logs above.${NC}"
    exit 1
fi

# 4. 設定ファイルの適用
#    生成された一時ファイルをホスト側のファイルに上書きコピーします
echo "   📝 Applying new configuration..."
docker compose exec -T mediawiki-ja cat /tmp/LocalSettings.php > ./data/mediawiki_html_ja/LocalSettings.php

# 5. ファイルの中身チェック（空でないか確認）
if [ ! -s ./data/mediawiki_html_ja/LocalSettings.php ]; then
    echo -e "${RED}❌ Error: Generated LocalSettings.php is empty! Something went wrong.${NC}"
    exit 1
fi

# 6. カスタム設定とデバッグ設定の追記
#    $wgShowExceptionDetails = true; を追加して、もしエラーが出ても詳細が見えるようにします
cat <<EOF >> ./data/mediawiki_html_ja/LocalSettings.php

# --- Auto-Wiki-Brain Custom Settings ---
\$wgEnableUploads = true;
\$wgUseInstantCommons = true;
\$wgHashedUploadDirectory = false;

# エラー詳細表示（デバッグ用）
\$wgShowExceptionDetails = true;
\$wgDebugLogFile = "/var/log/mediawiki/debug.log";
EOF

# 7. 権限修正と再起動
chmod 666 ./data/mediawiki_html_ja/LocalSettings.php
echo "   🔄 Restarting services..."
docker compose restart mediawiki-ja dashboard-ja

echo -e "${GREEN}✅ Repair Complete!${NC}"
echo "   Please access: http://localhost:8080"
echo "   (If you still see an error, it will now show detailed debug info.)"
#!/bin/bash

# force_reinstall.sh (v2: with Network Fix & Bot Creation)
# マウント干渉を回避してインストールし、ネットワーク設定も完璧な状態にするスクリプト

# 色設定
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# .envの読み込み
if [ -f .env ]; then
    export $(cat .env | grep -v '#' | xargs)
else
    # maintenance/toolbox/ にいる場合、2つ上を探す
    if [ -f ../../.env ]; then
        export $(cat ../../.env | grep -v '#' | xargs)
    elif [ -f ../.env ]; then
        export $(cat ../.env | grep -v '#' | xargs)
    else
        echo -e "${RED}❌ Error: .env file not found.${NC}"
        exit 1
    fi
fi

# パス補正（どこから実行されても大丈夫なように）
# このスクリプトが toolbox にある前提で、プロジェクトルート(opt/auto-wiki)を特定
PROJECT_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$PROJECT_ROOT" || exit

echo -e "${GREEN}🔧 Starting Perfect Re-install (Database & Config Reset)...${NC}"

# 1. データベースのクリーンアップ
echo "   🧹 Dropping database..."
docker compose exec mariadb mysql -u root -p"${DB_ROOT_PASS}" -e "DROP DATABASE IF EXISTS my_wiki_ja;"

# 2. ネットワークIDの取得
NETWORK=$(docker compose ps -q mediawiki-ja | xargs docker inspect -f '{{range .NetworkSettings.Networks}}{{.NetworkID}}{{end}}')

if [ -z "$NETWORK" ]; then
    echo -e "${RED}❌ Error: Docker network not found. Is docker-compose up?${NC}"
    exit 1
fi

# 3. 一時コンテナでのインストール実行
echo "   🚀 Running installer in a clean temporary container..."

docker run --rm --network "$NETWORK" \
  mediawiki:lts \
  /bin/bash -c "php maintenance/install.php \
    --dbname=my_wiki_ja \
    --dbuser=wikiuser \
    --dbpass='${WIKI_DB_PASS}' \
    --dbserver=mariadb \
    --lang=ja \
    --pass='${ADMIN_PASS}' \
    'AutoWiki-JA' '${ADMIN_USER}' \
    --confpath /tmp > /dev/stderr 2>&1 && cat /tmp/LocalSettings.php" \
  > ./data/mediawiki_html_ja/LocalSettings.php

# 4. 成功判定
if [ ! -s ./data/mediawiki_html_ja/LocalSettings.php ]; then
    echo -e "${RED}❌ Error: Installation failed. The config file is empty.${NC}"
    exit 1
fi

# 5. カスタム設定の追記（ここにネットワーク設定も含める！）
echo "   📝 Appending custom settings..."
cat <<EOF >> ./data/mediawiki_html_ja/LocalSettings.php

# --- Auto-Wiki-Brain Custom Settings ---
\$wgEnableUploads = true;
\$wgUseInstantCommons = true;
\$wgHashedUploadDirectory = false;
\$wgShowExceptionDetails = true;

# --- Dynamic Server URL Setting ---
# ブラウザ(localhost)とBot(内部通信)を両立させる設定
if ( isset( \$_SERVER['HTTP_HOST'] ) && \$_SERVER['HTTP_HOST'] ) {
    \$wgServer = "http://" . \$_SERVER['HTTP_HOST'];
} else {
    \$wgServer = "http://localhost:8080";
}
EOF

# 6. 権限修正
chmod 666 ./data/mediawiki_html_ja/LocalSettings.php

# 7. Botユーザーの作成（これもここでやってしまう）
echo "   🤖 Creating Bot User..."
# 設定反映のために一旦再起動が必要
docker compose restart mediawiki-ja
# 起動待ち
sleep 5

docker compose exec mediawiki-ja php maintenance/createAndPromote.php \
    --bot --force \
    "${BOT_USER}" "${BOT_PASS}"

# 8. 全再起動
echo "   🔄 Restarting System..."
docker compose restart mediawiki-ja dashboard-ja wiki-bot-ja

echo -e "${GREEN}✅ Perfect Re-install Complete!${NC}"
echo "   - Wiki: http://localhost:8080"
echo "   - Dashboard: http://localhost:8000/dashboard"
echo "   Please check the logs now."

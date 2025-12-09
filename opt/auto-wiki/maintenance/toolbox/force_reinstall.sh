#!/bin/bash

# force_reinstall.sh
# マウントの干渉を避けるため、一時コンテナを使用してインストールを強制実行するスクリプト

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

echo -e "${GREEN}🔧 Starting Forced Re-install (Bypassing Mount Issue)...${NC}"

# 1. データベースのクリーンアップ
echo "   🧹 Dropping database..."
docker compose exec mariadb mysql -u root -p"${DB_ROOT_PASS}" -e "DROP DATABASE IF EXISTS my_wiki_ja;"

# 2. ネットワークIDの取得 (既存のDBコンテナと通信するため)
NETWORK=$(docker compose ps -q mediawiki-ja | xargs docker inspect -f '{{range .NetworkSettings.Networks}}{{.NetworkID}}{{end}}')

if [ -z "$NETWORK" ]; then
    echo -e "${RED}❌ Error: Could not detect Docker network. Is the system running?${NC}"
    exit 1
fi

# 3. 一時コンテナでのインストール実行
#    - ボリュームをマウントせずに起動することで "LocalSettings.php exists" エラーを回避
#    - 生成された設定ファイルの中身だけを標準出力(stdout)に出して、ホスト側のファイルに書き込む
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

# 4. 成功判定（ファイルが空でないか）
if [ ! -s ./data/mediawiki_html_ja/LocalSettings.php ]; then
    echo -e "${RED}❌ Error: Installation failed. The config file is empty.${NC}"
    exit 1
fi

# 5. カスタム設定の追記
echo "   📝 Appending custom settings..."
cat <<EOF >> ./data/mediawiki_html_ja/LocalSettings.php

# --- Auto-Wiki-Brain Custom Settings ---
\$wgEnableUploads = true;
\$wgUseInstantCommons = true;
\$wgHashedUploadDirectory = false;
\$wgShowExceptionDetails = true;
EOF

# 6. 権限修正と再起動
chmod 666 ./data/mediawiki_html_ja/LocalSettings.php
echo "   🔄 Restarting main container..."
docker compose restart mediawiki-ja dashboard-ja

echo -e "${GREEN}✅ Re-install Complete!${NC}"
echo "   Please access: http://localhost:8080"
#!/bin/bash

# 色の定義
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Auto-Wiki-Brain Setup Script Started...${NC}"

# .envの読み込み
if [ -f .env ]; then
    export $(cat .env | grep -v '#' | xargs)
else
    echo -e "${RED}❌ Error: .env file not found.${NC}"
    exit 1
fi

# 1. 基本インフラの起動
echo -e "${YELLOW}📦 Starting Infrastructure (DB, Wiki, Ollama)...${NC}"
docker compose up -d mariadb mediawiki ollama

# 2. MariaDBの起動待機
echo -e "${YELLOW}⏳ Waiting for MariaDB to be ready...${NC}"
MAX_RETRIES=30
COUNT=0
while ! docker compose exec mariadb mysqladmin ping -h"localhost" -u"root" -p"${DB_ROOT_PASS}" --silent; do
    sleep 2
    echo -n "."
    COUNT=$((COUNT+1))
    if [ $COUNT -ge $MAX_RETRIES ]; then
        echo -e "\n${RED}❌ Error: MariaDB timed out.${NC}"
        exit 1
    fi
done
echo -e "\n${GREEN}✅ MariaDB is ready!${NC}"

# 3. MediaWikiの自動インストール (LocalSettings.phpの生成)
if [ ! -f ./data/mediawiki_html/LocalSettings.php ]; then
    echo -e "${YELLOW}⚙️  Installing MediaWiki via CLI...${NC}"
    
    # install.php を実行
    docker compose exec mediawiki php maintenance/install.php \
        --dbname=my_wiki \
        --dbuser=wikiuser \
        --dbpass="${WIKI_DB_PASS}" \
        --dbserver=mariadb \
        --lang=ja \
        --pass="${ADMIN_PASS}" \
        "AutoWiki" "${ADMIN_USER}"

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ MediaWiki installed successfully.${NC}"
        
        # 必要な設定を追記
        echo -e "${YELLOW}📝 Configuring LocalSettings.php...${NC}"
        LSPATH="./data/mediawiki_html/LocalSettings.php"
        
        # 画像アップロードとInstantCommonsの有効化
        echo "" >> $LSPATH
        echo "// Auto-Wiki-Brain Custom Settings" >> $LSPATH
        echo "\$wgEnableUploads = true;" >> $LSPATH
        echo "\$wgUseInstantCommons = true;" >> $LSPATH
        
        # Botアカウントの作成 (install.phpで作ったAdminとは別にBotを作る場合)
        # ここではAdminBotを使用するため、createAndPromote.phpを使用
        echo -e "${YELLOW}🤖 Creating Bot Account...${NC}"
        docker compose exec mediawiki php maintenance/createAndPromote.php \
            --bot --force \
            "${BOT_USER}" "${BOT_PASS}"
            
    else
        echo -e "${RED}❌ MediaWiki installation failed.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✅ LocalSettings.php already exists. Skipping installation.${NC}"
fi

# 4. AIモデルのプル
echo -e "${YELLOW}🧠 Pulling AI Model (${MODEL_NAME})...${NC}"
# モデルが既にあるか確認するのは難しいので、常にpullを試みる（キャッシュがあれば早いため）
docker compose exec ollama ollama pull ${MODEL_NAME}

# 5. 全サービスの起動 (Bot, API)
echo -e "${YELLOW}🚀 Starting Agents and API...${NC}"
docker compose up -d --build

echo -e "${GREEN}🎉 Setup Complete!${NC}"
echo -e "   - Wiki URL: http://localhost:8080"
echo -e "   - Dashboard: http://localhost:8000/dashboard"
echo -e "   - User/Pass: ${ADMIN_USER} / ${ADMIN_PASS}"
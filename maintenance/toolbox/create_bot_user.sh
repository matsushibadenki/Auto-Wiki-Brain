#!/bin/bash

# create_bot_user.sh
# データベース初期化後に、Bot用のアカウントを再作成するスクリプト

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

echo -e "${GREEN}🤖 Creating Bot User for MediaWiki (JA)...${NC}"

# MediaWikiのメンテナンススクリプトを使ってBotを作成
# --bot: Bot権限を付与
# --force: 既に存在してもパスワードを上書き更新
docker compose exec mediawiki-ja php maintenance/createAndPromote.php \
    --bot --force \
    "${BOT_USER}" "${BOT_PASS}"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Bot User '${BOT_USER}' created successfully!${NC}"
    echo -e "   Password has been synced with .env settings."
    
    # 念のためDashboardを再起動して再接続させる
    echo "🔄 Restarting Dashboard..."
    docker compose restart dashboard-ja
    
    echo -e "${GREEN}🎉 All fixes applied. Please reload the Dashboard.${NC}"
else
    echo -e "${RED}❌ Failed to create bot user.${NC}"
fi
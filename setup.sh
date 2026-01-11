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

# --- ユーザーへの確認 (多言語設定) ---
echo -e "${YELLOW}🌐 Language Setup Selection${NC}"
read -p "多言語対応モード（日本語 + 英語）でセットアップしますか？ (y/N): " ENABLE_MULTI_LANG

# 対象言語リストの作成
LANG_TARGETS=("ja") # デフォルトは日本語のみ
if [[ "$ENABLE_MULTI_LANG" =~ ^[yY] ]]; then
    echo -e "${GREEN}✅ Multi-language mode selected (ja, en).${NC}"
    LANG_TARGETS+=("en")
else
    echo -e "${GREEN}✅ Single-language mode selected (ja only).${NC}"
fi

# 【修正1】マウント用の空ファイルを作成しておく
echo -e "${YELLOW}📁 Preparing configuration files...${NC}"
for lang in "${LANG_TARGETS[@]}"; do
    DIR="./data/mediawiki_html_${lang}"
    FILE="$DIR/LocalSettings.php"
    mkdir -p "$DIR"
    mkdir -p "./data/mediawiki_images_${lang}"
    
    # ファイルが存在しない場合は空ファイルを作成（Dockerマウント用）
    if [ ! -f "$FILE" ]; then
        touch "$FILE"
        chmod 666 "$FILE" # コンテナ内のユーザーが書き込めるように
        echo -e "   - Created empty placeholder for: $FILE"
    fi
done

# 1. 基本インフラの起動
echo -e "${YELLOW}📦 Starting Common Infrastructure (MariaDB, Ollama)...${NC}"
docker compose up -d mariadb ollama

# 選択された言語のサービスを起動
SERVICES_TO_START=""
for lang in "${LANG_TARGETS[@]}"; do
    SERVICES_TO_START="$SERVICES_TO_START mediawiki-${lang} wiki-bot-${lang}"
    if [ "$lang" == "ja" ]; then
        SERVICES_TO_START="$SERVICES_TO_START dashboard-ja"
    fi
done

echo -e "${YELLOW}📦 Starting Wiki Services: ${SERVICES_TO_START}...${NC}"
docker compose up -d $SERVICES_TO_START

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

# 3. MediaWikiの自動インストール (各言語でループ実行)
for lang in "${LANG_TARGETS[@]}"; do
    echo -e "${YELLOW}⚙️  Configuring MediaWiki for [${lang}]...${NC}"
    
    SETTINGS_FILE="./data/mediawiki_html_${lang}/LocalSettings.php"
    CONTAINER_NAME="mediawiki-${lang}"
    DB_NAME="my_wiki_${lang}"

    # 【修正2】ファイルが存在しない OR 空ファイルの場合にインストールを実行
    if [ ! -s "$SETTINGS_FILE" ]; then
        echo -e "   Installing MediaWiki via CLI in ${CONTAINER_NAME}..."
        
        # install.php を実行 (LocalSettings.php はマウントされているのでホスト側にも反映される)
        docker compose exec ${CONTAINER_NAME} php maintenance/install.php \
            --dbname="${DB_NAME}" \
            --dbuser=wikiuser \
            --dbpass="${WIKI_DB_PASS}" \
            --dbserver=mariadb \
            --lang="${lang}" \
            --pass="${ADMIN_PASS}" \
            "AutoWiki-${lang^^}" "${ADMIN_USER}"

        if [ $? -eq 0 ]; then
            echo -e "   ✅ Installation successful for ${lang}."
            
            echo -e "   📝 Configuring LocalSettings.php for ${lang}..."
            
            # 追記設定
            cat <<EOF >> "$SETTINGS_FILE"

// Auto-Wiki-Brain Custom Settings
\$wgEnableUploads = true;
\$wgUseInstantCommons = true;
EOF
            
            # Botアカウントの作成
            echo -e "   🤖 Creating Bot Account for ${lang}..."
            docker compose exec ${CONTAINER_NAME} php maintenance/createAndPromote.php \
                --bot --force \
                "${BOT_USER}" "${BOT_PASS}"
                
        else
            echo -e "${RED}❌ MediaWiki installation failed for ${lang}.${NC}"
            exit 1
        fi
    else
        echo -e "${GREEN}✅ LocalSettings.php already exists (size > 0) for ${lang}. Skipping.${NC}"
    fi
done

# 4. AIモデルのプル
echo -e "${YELLOW}🧠 Pulling AI Model (${MODEL_NAME})...${NC}"
docker compose exec ollama ollama pull ${MODEL_NAME}

# 5. 再起動（設定反映のため）
echo -e "${YELLOW}🔄 Restarting services to apply settings...${NC}"
docker compose restart $SERVICES_TO_START

echo -e "${GREEN}🎉 Setup Complete!${NC}"
echo -e "   - Wiki (JA): http://localhost:8080"
if [[ "$ENABLE_MULTI_LANG" =~ ^[yY] ]]; then
    echo -e "   - Wiki (EN): http://localhost:8081"
fi
echo -e "   - Dashboard (JA): http://localhost:8000/dashboard"
echo -e "   - User/Pass: ${ADMIN_USER} / ${ADMIN_PASS}"
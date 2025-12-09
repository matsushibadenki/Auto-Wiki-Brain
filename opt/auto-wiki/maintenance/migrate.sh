#!/bin/bash

# /opt/auto-wiki/maintenance/migrate.sh
# サーバー移転・バックアップ用スクリプト
# Usage: 
#   Export: ./maintenance/migrate.sh export [backup_filename.tar.gz]
#   Import: ./maintenance/migrate.sh import [backup_filename.tar.gz]

# 色の定義
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

MODE=$1
FILENAME=${2:-"auto-wiki-migration.tar.gz"}

# ルートディレクトリへの移動（スクリプトがどこから呼ばれても対応）
cd "$(dirname "$0")/.." || exit

if [ "$MODE" == "export" ]; then
    echo -e "${YELLOW}📦 Starting System Export (Backup)...${NC}"
    
    # 1. データの整合性を保つためコンテナを停止
    echo -e "   Stopping services to ensure data consistency..."
    docker compose down

    # 2. 必要なディレクトリとファイルの存在確認
    if [ ! -d "data" ] || [ ! -f ".env" ]; then
        echo -e "${RED}❌ Error: 'data' directory or '.env' file not found.${NC}"
        exit 1
    fi

    # 3. 圧縮アーカイブの作成
    # data/ (DB, 画像, ベクトル), config/ (プロンプト), .env (設定), src/ (コード)
    # ※ src/ も含めることで、コードの改造状態も引き継げます
    echo -e "   Archiving data (This may take time depending on DB/Model size)..."
    tar -czvf "$FILENAME" data/ config/ src/ .env docker-compose.yml Dockerfile setup.sh maintenance.sh

    echo -e "${GREEN}✅ Export Complete!${NC}"
    echo -e "   File created: ${YELLOW}$FILENAME${NC}"
    echo -e "   -> Download this file and upload it to your new server."
    echo -e "   -> To restart services on THIS server: 'docker compose up -d'"

elif [ "$MODE" == "import" ]; then
    echo -e "${YELLOW}📦 Starting System Import (Restore)...${NC}"

    # 1. アーカイブファイルの確認
    if [ ! -f "$FILENAME" ]; then
        echo -e "${RED}❌ Error: Archive file '$FILENAME' not found.${NC}"
        exit 1
    fi

    # 2. 解凍
    echo -e "   Extracting archive..."
    tar -xzvf "$FILENAME"

    # 3. 権限の調整 (オプショナル: Dockerユーザー用)
    # chmod -R 755 data/

    # 4. セットアップスクリプトの再実行（DB待機やコンテナ起動を行うため）
    echo -e "   🚀 Booting up the system..."
    
    # スワップ領域の確保（新サーバーで初回の場合のみ）
    if [ -f "maintenance.sh" ]; then
        sudo ./maintenance.sh
    fi
    
    # コンテナ起動と初期化チェック
    ./setup.sh

    echo -e "${GREEN}🎉 Migration Complete! The system has been restored.${NC}"

else
    echo "Usage:"
    echo "  Export (Old Server): sudo ./maintenance/migrate.sh export [filename]"
    echo "  Import (New Server): sudo ./maintenance/migrate.sh import [filename]"
fi
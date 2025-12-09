#!/bin/bash

# /opt/auto-wiki/maintenance/factory_reset.sh
# システム初期化（ファクトリーリセット）スクリプト (Fixed: Recreate empty DB files)
# 目的: 蓄積された記事・ベクトルデータ・設定を削除し、インストール直後の状態に戻す
# オプション: --all をつけるとAIモデル(Ollama)も削除する

# 色の定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ルートディレクトリへ移動
cd "$(dirname "$0")/.." || exit

echo -e "${RED}🚨 WARNING: FACTORY RESET 🚨${NC}"
echo -e "This will delete ALL Wiki articles, images, and learned knowledge."
echo -e "Configuration files (.env, config/) and source code will be KEPT."
echo ""

# オプション判定
DELETE_MODELS=false
if [ "$1" == "--all" ]; then
    DELETE_MODELS=true
    echo -e "${YELLOW}⚠️  Option '--all' detected: AI Models will also be DELETED.${NC}"
else
    echo -e "${GREEN}ℹ️  AI Models (Ollama) will be KEPT to save download time.${NC}"
    echo -e "   (Use './maintenance/factory_reset.sh --all' to delete everything)"
fi

echo ""
read -p "Are you sure you want to continue? (Type 'yes' to confirm): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

# 1. サービスの停止
echo -e "\n${YELLOW}🛑 Stopping services...${NC}"
docker compose down -v

# 2. データの削除
echo -e "${YELLOW}🗑️  Deleting data files...${NC}"

# 削除対象
targets=(
    "data/mediawiki_db"
    "data/mediawiki_html_ja"
    "data/mediawiki_images_ja"
    "data/mediawiki_html_en"
    "data/mediawiki_images_en"
    "data/chromadb_ja"
    "data/chromadb_en"
    "data/scheduler_ja.db"
    "data/scheduler_en.db"
    "data/inputs/processed/*"
)

for target in "${targets[@]}"; do
    if [ -e "$target" ]; then
        echo "   - Removing $target"
        sudo rm -rf $target
    fi
done

# AIモデルの削除
if [ "$DELETE_MODELS" = true ]; then
    if [ -d "data/ollama" ]; then
        echo "   - Removing AI Models (data/ollama)"
        sudo rm -rf data/ollama
    fi
fi

# [修正] 空のDBファイルを再作成（ディレクトリ化防止）
echo -e "${YELLOW}✨ Recreating empty database files...${NC}"
touch data/scheduler_ja.db
touch data/scheduler_en.db

echo -e "${GREEN}✅ Reset Complete.${NC}"
echo ""

# 3. 再セットアップの案内
read -p "Do you want to run setup.sh now to reinstall? (y/N): " run_setup
if [[ "$run_setup" =~ ^[yY] ]]; then
    echo -e "\n${YELLOW}🚀 Starting setup...${NC}"
    ./setup.sh
else
    echo -e "\nSystem is reset. Run './setup.sh' when you are ready to start again."
fi
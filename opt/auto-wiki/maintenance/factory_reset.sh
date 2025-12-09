#!/bin/bash

# /opt/auto-wiki/maintenance/factory_reset.sh
# システム初期化（ファクトリーリセット）スクリプト (Fixed: Aggressive Cleanup)
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

# 1. サービスの停止とボリューム削除
echo -e "\n${YELLOW}🛑 Stopping services and removing volumes...${NC}"
# -v: 匿名ボリュームを削除
# --remove-orphans: 定義されていないコンテナも削除
docker compose down -v --remove-orphans

# 2. データの物理削除
echo -e "${YELLOW}🗑️  Deleting data directories...${NC}"

# 削除対象のディレクトリ（物理的に削除する）
dirs_to_delete=(
    "data/mediawiki_db"
    "data/mediawiki_html_ja"
    "data/mediawiki_images_ja"
    "data/mediawiki_html_en"
    "data/mediawiki_images_en"
    "data/chromadb_ja"
    "data/chromadb_en"
    "data/inputs/processed"
)

# 削除対象のファイル
files_to_delete=(
    "data/scheduler_ja.db"
    "data/scheduler_en.db"
)

# ディレクトリの削除
for dir in "${dirs_to_delete[@]}"; do
    if [ -d "$dir" ]; then
        echo "   - Deleting: $dir"
        sudo rm -rf "$dir"
    fi
done

# ファイルの削除
for file in "${files_to_delete[@]}"; do
    if [ -e "$file" ]; then
        echo "   - Deleting: $file"
        sudo rm -rf "$file"
    fi
done

# AIモデルの削除
if [ "$DELETE_MODELS" = true ]; then
    if [ -d "data/ollama" ]; then
        echo "   - Removing AI Models (data/ollama)"
        sudo rm -rf data/ollama
    fi
fi

# 3. 再作成（Docker誤認防止）
echo -e "${YELLOW}✨ Preparing empty files for Docker...${NC}"

# DBファイルを空ファイルとして作成（ディレクトリ化防止）
touch data/scheduler_ja.db
touch data/scheduler_en.db
chmod 666 data/scheduler_ja.db data/scheduler_en.db

# inputsディレクトリの作成
mkdir -p data/inputs/processed
chmod 777 data/inputs/processed

echo -e "${GREEN}✅ Reset Complete.${NC}"
echo ""

# 4. 再セットアップの案内
read -p "Do you want to run setup.sh now to reinstall? (y/N): " run_setup
if [[ "$run_setup" =~ ^[yY] ]]; then
    echo -e "\n${YELLOW}🚀 Starting setup...${NC}"
    
    # setup.shの実行
    ./setup.sh
else
    echo -e "\nSystem is reset. Run './setup.sh' when you are ready to start again."
fi

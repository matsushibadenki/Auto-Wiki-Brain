#!/bin/bash

# /opt/auto-wiki/maintenance/factory_reset.sh
# システム初期化（ファクトリーリセット）スクリプト (Fixed: Permission & 404 Error Robustness)
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
# -v オプションでDocker管理下のボリュームも削除

# 2. データの削除と再作成
echo -e "${YELLOW}🗑️  Resetting data directories...${NC}"

# リセット対象のディレクトリ（削除して作り直す）
# 注意: MediaWikiのHTMLディレクトリを確実に空にしておかないと、コンテナ起動時にファイルコピーがスキップされて404になる
dirs_to_reset=(
    "data/mediawiki_db"
    "data/mediawiki_html_ja"
    "data/mediawiki_images_ja"
    "data/mediawiki_html_en"
    "data/mediawiki_images_en"
    "data/chromadb_ja"
    "data/chromadb_en"
    "data/inputs/processed"
)

# リセット対象のファイル（削除して空ファイルを作る）
# Dockerが誤ってディレクトリとしてマウントするのを防ぐため
files_to_reset=(
    "data/scheduler_ja.db"
    "data/scheduler_en.db"
)

# ディレクトリの処理
for dir in "${dirs_to_reset[@]}"; do
    if [ -d "$dir" ]; then
        echo "   - Removing directory: $dir"
        sudo rm -rf "$dir"
    fi
    # [重要] 権限777で作成することで、コンテナ(www-data等)からの書き込みを許可する
    echo "   - Recreating directory: $dir"
    mkdir -p -m 777 "$dir"
done

# ファイルの処理
for file in "${files_to_reset[@]}"; do
    if [ -e "$file" ]; then
        echo "   - Removing existing path: $file"
        sudo rm -rf "$file"
    fi
    # 空ファイルを作成し、書き込み権限を与える
    echo "   - Recreating empty file: $file"
    touch "$file"
    chmod 666 "$file"
done

# AIモデルの削除
if [ "$DELETE_MODELS" = true ]; then
    if [ -d "data/ollama" ]; then
        echo "   - Removing AI Models (data/ollama)"
        sudo rm -rf data/ollama
    fi
fi

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

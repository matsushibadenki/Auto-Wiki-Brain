#!/bin/bash

# /opt/auto-wiki/maintenance/import_dump.sh
# Wikipediaのダンプデータをダウンロードし、MediaWikiにインポートするスクリプト

# 設定
DUMP_URL="https://dumps.wikimedia.org/jawiki/latest/jawiki-latest-pages-articles.xml.bz2"
DUMP_FILE="jawiki-latest-pages-articles.xml.bz2"
DATA_DIR="./data/dump"

# 色の定義
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}📦 Wikipedia Dump Import Tool${NC}"
echo -e "${YELLOW}⚠️  WARNING: This process requires ~30GB of disk space and takes several hours.${NC}"
read -p "Are you sure you want to continue? (y/N): " confirm
if [[ $confirm != "y" && $confirm != "Y" ]]; then
    echo "Aborted."
    exit 0
fi

# 1. 保存用ディレクトリの作成
mkdir -p $DATA_DIR

# 2. ダンプファイルのダウンロード
if [ -f "$DATA_DIR/$DUMP_FILE" ]; then
    echo -e "${GREEN}✅ Dump file already exists. Skipping download.${NC}"
else
    echo -e "${YELLOW}⬇️  Downloading Wikipedia Dump (This may take a while)...${NC}"
    # curlを使用してダウンロード（進捗バーを表示）
    curl -L -o "$DATA_DIR/$DUMP_FILE" "$DUMP_URL" --progress-bar
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Download failed.${NC}"
        exit 1
    fi
fi

# 3. インポート処理 (importDump.php)
echo -e "${YELLOW}⚙️  Importing to MediaWiki (Grab a coffee ☕, this takes hours)...${NC}"

# Dockerコンテナにダンプファイルをマウントして実行する必要があるため、
# 一時的にコンテナ経由で実行するのではなく、docker runでメンテナンスを実行するのが安全だが、
# ここでは稼働中のコンテナに対して、ホスト側のファイルをパイプで渡す方式をとる。
# (bzcatで展開しながら流し込む)

# 注意: ホストにbzcatがない場合を考慮し、docker内のツールを使う手もあるが、
# シンプルにホストのgzip/bzip2を使う。Mac/Linuxなら標準で入っているはず。

if ! command -v bzcat &> /dev/null; then
    echo -e "${RED}❌ 'bzcat' command not found. Please install bzip2.${NC}"
    exit 1
fi

# パイプライン: bzcat (ホスト) -> docker exec (コンテナ) -> importDump.php
bzcat "$DATA_DIR/$DUMP_FILE" | docker compose exec -T mediawiki php maintenance/importDump.php --conf ./LocalSettings.php /dev/stdin

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Import finished successfully!${NC}"
else
    echo -e "${RED}❌ Import failed during execution.${NC}"
    exit 1
fi

# 4. データベースの最適化と統計情報の更新
echo -e "${YELLOW}🧹 Rebuilding recent changes and statistics...${NC}"
docker compose exec mediawiki php maintenance/rebuildrecentchanges.php
docker compose exec mediawiki php maintenance/initSiteStats.php --update

echo -e "${GREEN}🎉 All done! Your Wiki is now full of knowledge.${NC}"
```

### 実行手順

1.  **スクリプトの作成と権限付与**
    ```bash
    mkdir -p maintenance
    # 上記のコードを maintenance/import_dump.sh に保存
    chmod +x maintenance/import_dump.sh
    ```

2.  **スクリプトの実行**
    プロジェクトのルートディレクトリ（`docker-compose.yml`がある場所）で実行します。
    ```bash
    ./maintenance/import_dump.sh
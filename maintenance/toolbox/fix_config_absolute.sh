#!/bin/bash

# fix_config_absolute.sh (Mac/Linux Universal)
# 設定ファイル(LocalSettings.php)をクリーンインストールし、
# 正しいネットワーク設定を埋め込む決定版スクリプト

# 色設定
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# 環境変数の読み込み補正
PROJECT_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$PROJECT_ROOT" || exit
if [ -f .env ]; then export $(cat .env | grep -v '#' | xargs); fi

echo -e "${GREEN}🔧 Starting Absolute Config Repair (Universal Mode)...${NC}"

# 1. データベースをリセット
echo "   🧹 Resetting Database..."
docker compose exec mariadb mysql -u root -p"${DB_ROOT_PASS}" -e "DROP DATABASE IF EXISTS my_wiki_ja;"

# 2. 既存の設定ファイルを削除
rm -f ./data/mediawiki_html_ja/LocalSettings.php

# 3. ネットワークID取得
NETWORK=$(docker compose ps -q mediawiki-ja | xargs docker inspect -f '{{range .NetworkSettings.Networks}}{{.NetworkID}}{{end}}')

# 4. インストーラーを実行して素のファイルを生成
echo "   🚀 Generating fresh LocalSettings.php..."
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
    --confpath /tmp > /dev/null 2>&1 && cat /tmp/LocalSettings.php" \
  > ./data/mediawiki_html_ja/LocalSettings.php.tmp

# 5. 生成されたファイルを加工 (sedを使わずgrepで除外)
#    - デフォルトの $wgServer 行を削除
#    - PHPの終了タグ ?> を削除
grep -v "\$wgServer =" ./data/mediawiki_html_ja/LocalSettings.php.tmp | grep -v "?>" > ./data/mediawiki_html_ja/LocalSettings.php

# 一時ファイル削除
rm ./data/mediawiki_html_ja/LocalSettings.php.tmp

# 6. 正しい設定を追記
cat <<EOF >> ./data/mediawiki_html_ja/LocalSettings.php

# --- Auto-Wiki-Brain Optimized Settings ---

# 1. 画像アップロード設定
\$wgEnableUploads = true;
\$wgUseInstantCommons = true;
\$wgHashedUploadDirectory = false;

# 2. デバッグ設定
\$wgShowExceptionDetails = true;

# 3. 動的ネットワーク設定
if ( isset( \$_SERVER['HTTP_HOST'] ) && \$_SERVER['HTTP_HOST'] ) {
    \$wgServer = "http://" . \$_SERVER['HTTP_HOST'];
} else {
    \$wgServer = "http://localhost:8080";
}
EOF

chmod 666 ./data/mediawiki_html_ja/LocalSettings.php

# 7. コンテナ再起動
echo "   🔄 Restarting Containers..."
docker compose restart mediawiki-ja

# 8. Botユーザーの作成
echo "   🤖 Re-creating Bot User..."
sleep 5
docker compose exec mediawiki-ja php maintenance/createAndPromote.php \
    --bot --force \
    "${BOT_USER}" "${BOT_PASS}" > /dev/null 2>&1

# 9. Bot再起動 (ここが重要)
docker compose restart wiki-bot-ja

echo -e "${GREEN}✅ Repair Complete!${NC}"
echo "   Please check logs: 'docker compose logs -f wiki-bot-ja'"
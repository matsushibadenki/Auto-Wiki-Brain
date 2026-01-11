#!/bin/bash

# repair_wiki.sh
# 壊れたLocalSettings.phpを修復するスクリプト

# .envの読み込み
if [ -f .env ]; then
    export $(cat .env | grep -v '#' | xargs)
else
    echo "❌ Error: .env file not found."
    exit 1
fi

echo "🔧 Repairing MediaWiki (JA) Settings..."

# 1. コンテナ内でインストーラーを実行し、一時ファイル(/tmp/LocalSettings.php)に出力させる
#    注意: --confpath /tmp を指定して既存ファイルとの競合を避けます
docker compose exec mediawiki-ja php maintenance/install.php \
    --dbname=my_wiki_ja \
    --dbuser=wikiuser \
    --dbpass="${WIKI_DB_PASS}" \
    --dbserver=mariadb \
    --lang=ja \
    --pass="${ADMIN_PASS}" \
    "AutoWiki-JA" "${ADMIN_USER}" \
    --confpath /tmp

# 2. 生成された設定ファイルをホスト側にコピー（上書き）
#    docker compose exec -T ... cat ... > ... の形式で中身を転送します
docker compose exec -T mediawiki-ja cat /tmp/LocalSettings.php > ./data/mediawiki_html_ja/LocalSettings.php

# 3. カスタム設定を追記
#    LocalSettings.phpはPHPファイルなので末尾に追記してOKです
cat <<EOF >> ./data/mediawiki_html_ja/LocalSettings.php

# --- Auto-Wiki-Brain Custom Settings ---
\$wgEnableUploads = true;
\$wgUseInstantCommons = true;
# デバッグ用（問題解決後コメントアウト可）
\$wgShowExceptionDetails = true;
EOF

# 4. 権限の修正（念のため）
chmod 666 ./data/mediawiki_html_ja/LocalSettings.php

# 5. コンテナ再起動
echo "🔄 Restarting MediaWiki..."
docker compose restart mediawiki-ja dashboard-ja

echo "✅ Repair Complete. Please check http://localhost:8080 again."
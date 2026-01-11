#!/bin/bash

# fix_css_path.sh (Mac-Safe Version v2)
# LocalSettings.php の $wgScriptPath を修正し、CSS/画像読み込みエラーを解消する
# sed -i を使用せず、grepで除外して追記する方法でOS間の互換性を確保

# 色設定
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# 環境変数の読み込み補正
PROJECT_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$PROJECT_ROOT" || exit

CONFIG_FILE="./data/mediawiki_html_ja/LocalSettings.php"

if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}❌ Error: LocalSettings.php not found at $CONFIG_FILE${NC}"
    exit 1
fi

echo -e "${GREEN}🎨 Fixing CSS/Resource Paths in LocalSettings.php...${NC}"

# 1. バックアップ作成
cp "$CONFIG_FILE" "${CONFIG_FILE}.bak_css_v2"

# 2. 既存の設定（$wgScriptPath, $wgResourceBasePath, $wgStyleDirectory, $wgStylePath）を除外して一時ファイルに書き出す
#    重複設定を防ぐため、関連する設定をすべてクリアします
grep -v "\$wgScriptPath =" "$CONFIG_FILE" | \
grep -v "\$wgResourceBasePath =" | \
grep -v "\$wgStylePath =" | \
grep -v "\$wgLogo =" > "${CONFIG_FILE}.tmp"

# 3. 正しい設定を追記
#    Docker公式イメージのMediaWikiは、Webルート直下(/var/www/html)に展開されるため、
#    ブラウザから見たパスは "/html" ではなく "" (空文字) が正解であるケースが大半です。
#    また、load.phpが正しく動作するためには $wgResourceBasePath も一致させる必要があります。

cat <<EOF >> "${CONFIG_FILE}.tmp"

# --- Fix CSS/Resource Paths (Auto-Generated v2) ---
# Dockerコンテナ(mediawiki:lts)の標準構成に合わせます。
# ドキュメントルート直下で動作しているため、パスは空文字または "/" です。
\$wgScriptPath = "";
\$wgResourceBasePath = "";

# スキンやロゴのパス設定
\$wgStylePath = "\$wgScriptPath/skins";
\$wgLogo = "\$wgResourceBasePath/resources/assets/wiki.png";

# load.php の動作を安定させるための追加設定
\$wgUseGzip = true;
EOF

# ファイルの置き換え
mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
chmod 666 "$CONFIG_FILE"

# 4. コンテナ再起動（設定反映のため）
echo "   🔄 Restarting MediaWiki..."
docker compose restart mediawiki-ja

echo -e "${GREEN}✅ CSS Path Fix Complete!${NC}"
echo "   Please clear browser cache and reload: http://localhost:8080"
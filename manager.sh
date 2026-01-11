#!/bin/bash

# manager.sh
# Auto-Wiki-Brain 統合管理ツール
# 散らばったスクリプトを一元管理・実行するためのランチャー

# 色設定
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# タイトル表示
show_header() {
    clear
    echo -e "${BLUE}=========================================${NC}"
    echo -e "${BLUE}   🧠 Auto-Wiki-Brain Control Center     ${NC}"
    echo -e "${BLUE}=========================================${NC}"
}

# 実行ヘルパー関数
run_script() {
    SCRIPT_PATH=$1
    if [ -f "$SCRIPT_PATH" ]; then
        echo -e "\n${YELLOW}▶ Executing: $SCRIPT_PATH${NC}"
        # ルートディレクトリのコンテキストで実行する
        bash "$SCRIPT_PATH"
        echo -e "\n${GREEN}✔ Operation finished.${NC}"
    else
        echo -e "\n${RED}❌ Error: Script not found ($SCRIPT_PATH)${NC}"
    fi
    read -p "Press Enter to return to menu..."
}

while true; do
    show_header
    echo "Please select an operation:"
    echo ""
    echo -e "${YELLOW}[ Configuration & Features ]${NC}"
    echo "  1. Enable Progress Logs (ログ機能有効化)"
    echo "  2. Create Bot User (Botユーザー作成)"
    echo "  3. Setup Swap Memory (スワップ領域作成)"
    echo ""
    echo -e "${YELLOW}[ Troubleshooting & Fixes ]${NC}"
    echo "  4. Fix Internal Network (内部ネットワーク修復)"
    echo "  5. Fix Server Port 8080 (ポート設定修正)"
    echo "  6. Fix Diagnostics Bug (診断機能修正)"
    echo "  7. Repair Wiki Settings (設定ファイル修復)"
    echo "  8. Force Re-install MediaWiki (強制再インストール)"
    echo ""
    echo -e "${YELLOW}[ System Maintenance ]${NC}"
    echo "  9. Factory Reset (初期化・データ削除)"
    echo " 10. Import Wikipedia Dump (ダンプインポート)"
    echo " 11. Backup/Migrate (バックアップ・移行)"
    echo ""
    echo "  0. Exit"
    echo ""
    read -p "Enter choice [0-11]: " choice

    case $choice in
        1) run_script "maintenance/toolbox/enable_progress_log.sh" ;;
        2) run_script "maintenance/toolbox/create_bot_user.sh" ;;
        3) run_script "maintenance/setup_swap.sh" ;;
        
        4) run_script "maintenance/toolbox/fix_internal_network.sh" ;;
        5) run_script "maintenance/toolbox/fix_server_port.sh" ;;
        6) run_script "maintenance/toolbox/fix_diagnostics_bug.sh" ;;
        7) run_script "maintenance/toolbox/repair_wiki.sh" ;;
        8) run_script "maintenance/toolbox/force_reinstall.sh" ;;
        
        9) run_script "maintenance/factory_reset.sh" ;;
        10) run_script "maintenance/import_dump.sh" ;;
        11) run_script "maintenance/migrate.sh" ;;
        
        0) echo "Bye!"; exit 0 ;;
        *) echo "Invalid option." ;;
    esac
done
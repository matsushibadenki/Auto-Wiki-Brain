#!/bin/bash
# メモリ不足対策：8GBのスワップファイルを作成するスクリプト

# OS判定
OS="$(uname -s)"
if [ "$OS" = "Darwin" ]; then
    echo "🍎 Mac OS detected. Docker Desktop manages memory automatically."
    echo "   Skipping swap file creation."
    exit 0
fi

# Linuxの場合のみ実行
SWAP_FILE="/swapfile"
SIZE="8G"

if [ -f "$SWAP_FILE" ]; then
    echo "Swap file already exists."
else
    echo "Creating swap file ($SIZE)..."
    fallocate -l $SIZE $SWAP_FILE
    chmod 600 $SWAP_FILE
    mkswap $SWAP_FILE
    swapon $SWAP_FILE
    echo "$SWAP_FILE none swap sw 0 0" >> /etc/fstab
    echo "Swap created successfully."
fi

# 現在のメモリ状況を表示
free -h
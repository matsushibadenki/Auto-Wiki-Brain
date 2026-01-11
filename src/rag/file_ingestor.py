# /opt/auto-wiki/src/rag/file_ingestor.py
# 日本語タイトル: ローカルファイル取込インジェスター
# 目的: inputディレクトリ内のテキストファイルを読み込み、VectorDBに知識として登録する

import os
import glob
import shutil
from src.rag.vector_store import WikiVectorDB

class LocalFileIngestor:
    def __init__(self, input_dir="/app/data/inputs", processed_dir="/app/data/inputs/processed"):
        self.input_dir = input_dir
        self.processed_dir = processed_dir
        self.vector_db = WikiVectorDB()
        
        # ディレクトリ作成
        os.makedirs(self.input_dir, exist_ok=True)
        os.makedirs(self.processed_dir, exist_ok=True)

    def process_new_files(self):
        """
        新規ファイルをスキャンし、ベクトルDBに登録後、processedフォルダへ移動する
        """
        # 対象拡張子
        extensions = ['*.txt', '*.md']
        files = []
        for ext in extensions:
            files.extend(glob.glob(os.path.join(self.input_dir, ext)))
            
        if not files:
            return 0

        print(f"📂 Found {len(files)} local documents to ingest...")
        count = 0
        
        for file_path in files:
            try:
                filename = os.path.basename(file_path)
                topic_name = os.path.splitext(filename)[0] # ファイル名をトピック名とする
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if content.strip():
                    # 記事としてではなく、知識ドキュメントとしてベクトル化
                    # ここでは簡易的に「トピック名＝ファイル名」の記事として登録する扱いにする
                    print(f"   - Ingesting: {filename}")
                    self.vector_db.upsert_article(topic_name, content)
                    
                    # 処理済み移動
                    dest_path = os.path.join(self.processed_dir, filename)
                    shutil.move(file_path, dest_path)
                    count += 1
            except Exception as e:
                print(f"❌ Failed to ingest {file_path}: {e}")
        
        if count > 0:
            print(f"✅ Successfully ingested {count} documents.")
        
        return count
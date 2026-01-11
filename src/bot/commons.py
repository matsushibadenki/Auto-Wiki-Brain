# /opt/auto-wiki/src/bot/commons.py
# 画像検索エージェント
# 目的: Wikimedia Commonsから適切な画像を検索・選定する

import mwclient
from openai import OpenAI

class CommonsAgent:
    def __init__(self, client: OpenAI, model_name: str):
        self.site = mwclient.Site('commons.wikimedia.org')
        self.client = client
        self.model_name = model_name

    def search_images(self, topic: str, limit: int = 5):
        """トピックに関連する画像を検索する"""
        print(f"🖼️ Searching Commons for: {topic}")
        results = []
        try:
            # File名前空間(6)で検索
            search_gen = self.site.search(topic, namespace=6)
            for i, page in enumerate(search_gen):
                if i >= limit: break
                if page.name.endswith(('.jpg', '.png', '.svg', '.jpeg')):
                    results.append(page.name)
        except Exception as e:
            print(f"⚠️ Commons search error: {e}")
        return results

    def select_best_image(self, topic: str, images: list) -> str | None:
        """検索結果の中から記事に最適な画像をLLMに選ばせる"""
        if not images:
            return None
        
        prompt = f"""
        Wikipedia記事「{topic}」のトップ画像として最も適切なファイルを選んでください。
    
        候補リスト:
        {chr(10).join(images)}
        
        ルール:
        1. ファイル名のみを返してください。
        2. 適切でない場合は "NONE" と返してください。
        """
        
        try:
            resp = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
        
            # --- 修正箇所: contentがNoneの場合を考慮 ---
            content = resp.choices[0].message.content
            if not content:
                return None
            
            selection = content.strip()
            # ------------------------------------------

            # 簡易的なクリーニング（余計な引用符などを除去）
            selection = selection.replace("'", "").replace('"', "")
        
            if selection in images:
                print(f"🖼️ Selected Image: {selection}")
                return selection
        except Exception as e:
            print(f"⚠️ Image selection error: {e}")
    
        return None
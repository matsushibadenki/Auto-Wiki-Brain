# /opt/auto-wiki/src/bot/wiki_bot.py
# 自律型Wiki Botのメインロジック
# 目的: 記事の検索・吟味・画像選定・執筆・投稿のワークフロー制御

import mwclient
from openai import OpenAI
from duckduckgo_search import DDGS
from src.bot.commons import CommonsAgent
from src.bot.vetter import InformationVetter
# RAGを有効にする場合は以下をコメントイン
from src.rag.vector_store import WikiVectorDB

class LocalWikiBotV2:
    def __init__(self, wiki_host, bot_user, bot_pass, model_name, base_url):
        print(f"🤖 Initializing WikiBot (Model: {model_name})...")
        
        # 1. MediaWiki接続
        # Dockerネットワーク内では http で接続
        self.site = mwclient.Site(wiki_host, path='/', scheme='http')
        try:
            self.site.login(bot_user, bot_pass)
        except Exception as e:
            print(f"⚠️ Wiki Login Warning: {e}")
        
        # 2. ローカルLLM接続
        self.client = OpenAI(base_url=base_url, api_key="ollama")
        self.model_name = model_name
        
        # 3. エージェント初期化
        self.ddgs = DDGS()
        self.commons = CommonsAgent(self.client, model_name)
        self.vetter = InformationVetter(self.client, model_name)
        self.vector_db = WikiVectorDB() # RAG用DB初期化

    def update_article(self, topic: str):
        """
        記事のライフサイクル管理: 検索 -> 吟味 -> 画像選定 -> 執筆 -> 投稿
        """
        print(f"\n📘 Processing Topic: {topic}")

        # --- Phase 1: Discovery & Research ---
        try:
            raw_results = self.ddgs.text(topic, max_results=10)
        except Exception as e:
            print(f"❌ Search failed: {e}")
            return

        if not raw_results:
            print("❌ No search results found.")
            return

        # --- Phase 2: Vetting (情報の吟味) ---
        vetted_info = self.vetter.vet_search_results(topic, raw_results)
        if not vetted_info:
            print("⚠️ All information was rejected by Vetting Agent.")
            return
        
        # --- Phase 3: Media Enrichment (画像選定) ---
        image_instruction = ""
        try:
            images = self.commons.search_images(topic)
            best_image = self.commons.select_best_image(topic, images)
            if best_image:
                # File: プレフィックスの有無を調整
                clean_name = best_image.replace("File:", "")
                image_instruction = f"\n[画像指示]\n記事の冒頭または適切な位置に [[File:{clean_name}|thumb|250px|{topic}]] を配置してください。"
        except Exception as e:
            print(f"⚠️ Image search failed: {e}")

        # --- Phase 4: Writing (執筆) ---
        page = self.site.pages[topic]
        old_text = page.text()
        
        prompt = self._build_prompt(topic, old_text, vetted_info, image_instruction)
        
        print("✍️  Generating content with Local LLM...")
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            new_text = response.choices[0].message.content
        except Exception as e:
            print(f"❌ Generation failed: {e}")
            return

        # --- Phase 5: Publishing (投稿) ---
        if "NO_CHANGE" not in new_text and len(new_text) > 50:
            summary = f"Auto-update: Incorporated external sources via Local LLM."
            
            # 簡易的なMarkdown -> WikiTextクリーニング（必要であれば実装）
            new_text = new_text.replace("```wikitext", "").replace("```", "")
            
            page.save(new_text, summary=summary)
            print("✅ Article saved successfully.")
            
            # VectorDBへの同期
            self.vector_db.upsert_article(topic, new_text)
        else:
            print("⏹️  No significant changes generated.")

    def _build_prompt(self, topic, old_text, info, image_inst):
        return f"""
        あなたはWikipediaの熟練編集者です。
        トピック「{topic}」について、最新情報に基づき記事を更新してください。

        # ルール
        1. 嘘（ハルシネーション）は厳禁です。提供された情報のみを使用してください。
        2. 既存の記事がある場合は、破壊せず、新しい情報を「追記」または「古い情報の更新」として統合してください。
        3. 常に中立的な観点（NPOV）で記述してください。
        4. 出力はWiki構文（Wikitext）のみで行ってください。Markdownは使用しないでください。
        5. 記事の冒頭は定義から始めてください。

        # 信頼できる情報源
        {info}

        # 画像指示
        {image_inst}

        # 既存の記事内容
        {old_text[:3000]}...

        更新された記事全文を出力してください。変更が不要な場合は "NO_CHANGE" と出力してください。
        """
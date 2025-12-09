# /opt/auto-wiki/src/bot/wiki_bot.py
# 自律型Wiki Botのメインロジック
# 目的: 記事の検索・吟味・画像選定・執筆・投稿のワークフロー制御

import mwclient
from openai import OpenAI
from duckduckgo_search import DDGS
from src.bot.commons import CommonsAgent
from src.bot.vetter import InformationVetter
from src.rag.vector_store import WikiVectorDB

class LocalWikiBotV2:
    def __init__(self, wiki_host, bot_user, bot_pass, model_name, base_url, lang="ja"):
        print(f"🤖 Initializing WikiBot (Model: {model_name}, Lang: {lang})...")
        self.lang = lang
        
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
        # Vetterにも言語設定を渡す
        self.vetter = InformationVetter(self.client, model_name, lang=lang)
        self.vector_db = WikiVectorDB()

    def update_article(self, topic: str):
        """
        記事のライフサイクル管理: 検索 -> 吟味 -> 画像選定 -> 執筆 -> 投稿
        """
        print(f"\n📘 Processing Topic ({self.lang}): {topic}")

        # --- Phase 1: Discovery & Research ---
        try:
            # 検索も言語に合わせて結果を取得（DuckDuckGoはregion指定可能）
            region = "jp-jp" if self.lang == "ja" else "us-en"
            raw_results = self.ddgs.text(topic, region=region, max_results=10)
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
                clean_name = best_image.replace("File:", "")
                if self.lang == "ja":
                    image_instruction = f"\n[画像指示]\n記事の冒頭または適切な位置に [[File:{clean_name}|thumb|250px|{topic}]] を配置してください。"
                else:
                    image_instruction = f"\n[Image Instruction]\nPlease place [[File:{clean_name}|thumb|250px|{topic}]] at the beginning or appropriate position."
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
            summary = "Auto-update via Local LLM"
            
            # クリーニング
            new_text = new_text.replace("```wikitext", "").replace("```", "")
            
            page.save(new_text, summary=summary)
            print("✅ Article saved successfully.")
            
            self.vector_db.upsert_article(topic, new_text)
        else:
            print("⏹️  No significant changes generated.")

    def _build_prompt(self, topic, old_text, info, image_inst):
        if self.lang == "en":
            return f"""
            You are an expert Wikipedia editor.
            Update the article for topic "{topic}" based on the latest information.

            # Rules
            1. No hallucinations. Use only provided information.
            2. Integrate new info into existing content. Do not destroy existing structure.
            3. Maintain Neutral Point of View (NPOV).
            4. Output ONLY Wikitext format. No Markdown.
            5. Start with a definition.

            # Trusted Sources
            {info}

            # Image Instructions
            {image_inst}

            # Existing Content
            {old_text[:3000]}...

            Output the full updated article. If no changes are needed, output "NO_CHANGE".
            """
        else:
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
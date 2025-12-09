# /opt/auto-wiki/src/bot/wiki_bot.py
# 日本語タイトル: 自律型Wiki Botのメインロジック (v2.4 - 既存記事の監査・改善機能搭載)
# 目的: 記事の調査(Deep)・吟味・画像・執筆・レビュー・リンク生成・投稿のワークフロー制御

import os
import mwclient
from openai import OpenAI
from src.bot.commons import CommonsAgent
from src.bot.vetter import InformationVetter
from src.bot.reviewer import ArticleReviewer
from src.bot.researcher import DeepResearcher
from src.rag.vector_store import WikiVectorDB

class LocalWikiBotV2:
    def __init__(self, wiki_host, bot_user, bot_pass, model_name, base_url, lang="ja"):
        print(f"🤖 Initializing WikiBot (Model: {model_name}, Lang: {lang})...")
        self.lang = lang
        
        # 1. MediaWiki接続
        self.site = mwclient.Site(wiki_host, path='/', scheme='http')
        try:
            self.site.login(bot_user, bot_pass)
        except Exception as e:
            print(f"⚠️ Wiki Login Warning: {e}")
        
        # 2. ローカルLLM接続
        self.client = OpenAI(base_url=base_url, api_key="ollama")
        self.model_name = model_name
        
        # 3. エージェント初期化
        self.researcher = DeepResearcher(self.client, model_name, lang=lang)
        self.commons = CommonsAgent(self.client, model_name)
        self.vetter = InformationVetter(self.client, model_name, lang=lang)
        self.reviewer = ArticleReviewer(self.client, model_name, lang=lang)
        self.vector_db = WikiVectorDB()

    def update_article(self, topic: str):
        """
        記事のライフサイクル管理: 
        DeepResearch -> Vetting -> Image -> Writing -> Review -> Linking -> Publish
        """
        print(f"\n📘 Processing Topic ({self.lang}): {topic}")

        # --- Phase 0: 既存記事の確認 ---
        page = self.site.pages[topic]
        old_text = ""
        is_existing = False
        
        if page.exists:
            print(f"   ℹ️ Article '{topic}' already exists. Checking for improvements...")
            old_text = page.text()
            is_existing = True
        else:
            print(f"   🆕 Creating NEW article: {topic}")

        # --- Phase 1: Deep Discovery & Research (深層調査) ---
        try:
            # 既存記事がある場合でも、最新情報との整合性をチェックするためにリサーチは必須
            raw_research_text = self.researcher.conduct_deep_research(topic)
        except Exception as e:
            print(f"❌ Research phase failed: {e}")
            return

        if not raw_research_text:
            print("❌ No research results found.")
            return

        # --- Phase 2: Vetting (情報の吟味) ---
        vetted_info = raw_research_text 
        
        # --- Phase 3: Media Enrichment (画像選定) ---
        image_instruction = ""
        # 画像がない場合のみ検索（既存記事の画像を尊重）
        if not is_existing or ("[[File:" not in old_text and "[[ファイル:" not in old_text):
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

        # --- Phase 4: Writing / Auditing (執筆・監査) ---
        
        if is_existing:
            # 既存記事の監査・修正モード
            prompt = self._build_audit_prompt(topic, old_text, vetted_info, image_instruction)
            action_type = "Auditing & Updating"
        else:
            # 新規作成モード
            prompt = self._build_creation_prompt(topic, old_text, vetted_info, image_instruction)
            action_type = "Creating"
        
        print(f"✍️  {action_type} content with Local LLM...")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            draft_text = response.choices[0].message.content
        except Exception as e:
            print(f"❌ Generation failed: {e}")
            return

        # --- Phase 4.5: Review & Refine (レビューと修正) ---
        if "NO_CHANGE" not in draft_text:
            # ドラフトが空でないか確認
            if not draft_text or len(draft_text) < 50:
                print("⚠️ Generated draft is too short or empty. Skipping.")
                return

            is_approved, feedback = self.reviewer.review_draft(topic, draft_text, vetted_info)
            if not is_approved:
                draft_text = self.reviewer.refine_draft(topic, draft_text, feedback)

        # --- Phase 4.6: Internal Linking (内部リンク生成) ---
        if "NO_CHANGE" not in draft_text:
            try:
                # 既存記事の場合は、既にリンクがあるかもしれないので慎重に追加
                if "== 関連項目 ==" not in draft_text and "== See Also ==" not in draft_text:
                    see_also = self._generate_see_also(topic)
                    if see_also:
                        draft_text += f"\n\n{see_also}"
            except Exception as e:
                print(f"⚠️ Internal linking failed: {e}")

        # --- Phase 5: Publishing (投稿) ---
        if "NO_CHANGE" not in draft_text and len(draft_text) > 50:
            # 変更がある場合のみ保存
            summary = ""
            if is_existing:
                summary = "Auto-update: Verified facts, added missing info, and corrected errors."
            else:
                summary = "Created new article via Auto-Wiki-Brain."
                
            final_text = draft_text.replace("```wikitext", "").replace("```", "")
            
            # 既存記事と全く同じなら保存しない（API負荷軽減）
            if is_existing and final_text.strip() == old_text.strip():
                print("⏹️  Content is identical. No update needed.")
                return

            page.save(final_text, summary=summary)
            print("✅ Article saved successfully.")
            
            # ベクトルDBも更新
            self.vector_db.upsert_article(topic, final_text)
        else:
            print("⏹️  No significant changes generated (Bot decided to keep current version).")

    def _generate_see_also(self, topic: str) -> str:
        """関連する既存記事へのリンク集を生成する"""
        try:
            results = self.vector_db.search(topic, n_results=5)
            if not results or not results['ids']: return ""

            related_topics = []
            ids = results['ids'][0]
            
            for related_id in ids:
                if related_id != topic:
                    related_topics.append(f"* [[{related_id}]]")
            
            if not related_topics: return ""
            related_topics = list(set(related_topics))

            header = "== 関連項目 ==" if self.lang == "ja" else "== See Also =="
            return f"{header}\n" + "\n".join(related_topics)
        except:
            return ""

    def _load_custom_policy(self):
        """外部ファイルから編集方針（システムプロンプト）を読み込む"""
        path = f"/app/config/edit_policy_{self.lang}.txt"
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except:
                pass
        return None

    def _build_creation_prompt(self, topic, old_text, info, image_inst):
        """新規作成用のプロンプト"""
        data_section = f"""
        # Target Topic
        {topic}
        # Trusted Sources
        {info}
        # Image Instructions
        {image_inst}
        """
        
        policy = self._load_custom_policy()
        base_inst = policy if policy else "You are a Wikipedia editor."

        if self.lang == "en":
            return f"""
            {base_inst}
            Create a comprehensive Wikipedia article for "{topic}".
            # Rules
            1. Use ONLY provided sources.
            2. Neutral Point of View.
            3. Output ONLY Wikitext.
            {data_section}
            Output the full article text.
            """
        else:
            return f"""
            {base_inst}
            トピック「{topic}」のWikipedia記事を新規作成してください。
            # ルール
            1. 提供された情報源のみを使用すること。
            2. 中立的な観点で記述すること。
            3. 出力はWiki構文のみにすること。
            {data_section}
            記事全文を出力してください。
            """

    def _build_audit_prompt(self, topic, old_text, info, image_inst):
        """既存記事の監査・修正用プロンプト"""
        data_section = f"""
        # Target Topic
        {topic}
        # Trusted Sources (Latest Info)
        {info}
        # Current Article Content
        {old_text}
        # Image Instructions
        {image_inst}
        """

        if self.lang == "en":
            return f"""
            You are a senior Wikipedia editor tasked with auditing and improving an existing article.
            Topic: "{topic}"

            # Your Task
            Compare the "Current Article Content" with the "Trusted Sources".
            1. **Verify**: Are there any factual errors in the current article? If so, correct them.
            2. **Update**: Is there new information in the sources that is missing? If so, add it.
            3. **Structure**: Improve the formatting if needed.
            4. **Images**: Add the image if instructed and not already present.

            # Output Rules
            - If the article is already perfect and accurate, output ONLY "NO_CHANGE".
            - If changes are needed, output the **Full Rewritten Article** in Wikitext.
            - Do NOT explain your changes, just output the code.
            
            {data_section}
            """
        else:
            return f"""
            あなたはWikipediaのシニア編集者です。既存の記事を監査し、改善する任務があります。
            トピック: 「{topic}」

            # あなたの仕事
            「現在の記事内容」と「信頼できる情報源（最新情報）」を比較してください。
            1. **検証**: 記事に誤った情報はありませんか？あれば訂正してください。
            2. **加筆**: 情報源にある重要な情報で、記事に欠けているものはありますか？あれば適切なセクションに追記してください。
            3. **構造**: フォーマットや見出しを整理してください。
            4. **画像**: 画像指示があり、記事にまだ画像がない場合は追加してください。

            # 出力ルール
            - 記事が既に正確で十分な場合、"NO_CHANGE" とだけ出力してください。
            - 修正が必要な場合、**修正後の記事全文**をWiki構文で出力してください。
            - 修正箇所の説明は不要です。コードのみを出力してください。

            {data_section}
            """

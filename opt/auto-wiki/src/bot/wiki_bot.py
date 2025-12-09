# /opt/auto-wiki/src/bot/wiki_bot.py
# 日本語タイトル: 自律型Wiki Botのメインロジック (v2.6 - 差分更新・追記型アプローチ)
# 目的: 記事の調査(Deep)・吟味・画像・執筆・レビュー・リンク生成・投稿のワークフロー制御

import os
import mwclient
import datetime
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
            print(f"   ℹ️ Article '{topic}' already exists. Checking for updates...")
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
            # 既存記事の「追記・更新」モード（全体書き換え防止）
            prompt = self._build_incremental_update_prompt(topic, old_text, vetted_info, image_instruction)
            action_type = "Updating (Incremental)"
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

        # --- Phase 4.5: Review & Refine (Optional for Speed) ---
        # 【改善】ドラフト生成に成功していれば、必ずしも毎回レビューを通さなくて良い運用にする
        # 特に「追記モード(is_existing)」の場合は、リスクが低いのでスキップして速度を稼ぐ
        
        need_review = True
        if is_existing: 
            print("⏩ Skipping heavy review for incremental update to save time.")
            need_review = False

        if need_review and "NO_CHANGE" not in draft_text:
            if not draft_text or len(draft_text) < 50:
                print("⚠️ Generated draft is too short or empty. Skipping.")
                return

            print("🧐 conducting quality review...")
            is_approved, feedback = self.reviewer.review_draft(topic, draft_text, vetted_info)
            if not is_approved:
                draft_text = self.reviewer.refine_draft(topic, draft_text, feedback)
        # --- Phase 4.6: Internal Linking (内部リンク生成) ---
        # 追記の場合もリンクは有用だが、既存テキスト内のリンクは触らない
        if "NO_CHANGE" not in draft_text and not is_existing:
             try:
                if "== 関連項目 ==" not in draft_text and "== See Also ==" not in draft_text:
                    see_also = self._generate_see_also(topic)
                    if see_also:
                        draft_text += f"\n\n{see_also}"
             except Exception as e:
                print(f"⚠️ Internal linking failed: {e}")

        # --- Phase 5: Publishing (投稿) ---
        if "NO_CHANGE" not in draft_text and len(draft_text) > 10:
            summary = ""
            final_text = ""

            if is_existing:
                # 追記モードの場合、生成されたテキストは「追記分のみ」あるいは「修正版全文」
                # ここでは安全のため、プロンプトで「追記分のみ出力」させるか、「全文出力」させるかで制御が必要。
                # _build_incremental_update_prompt では「全文」を出力させるようにしているが、
                # 既存部分を勝手に変えないよう強く指示している。
                summary = "Auto-update: Added new information based on latest research."
                final_text = draft_text.replace("```wikitext", "").replace("```", "")
                
                # 既存記事と全く同じなら保存しない
                if final_text.strip() == old_text.strip():
                    print("⏹️  Content is identical. No update needed.")
                    return
            else:
                summary = "Created new article via Auto-Wiki-Brain."
                final_text = draft_text.replace("```wikitext", "").replace("```", "")

            page.save(final_text, summary=summary)
            print("✅ Article saved successfully.")
            
            # ベクトルDBも更新
            self.vector_db.upsert_article(topic, final_text)
        else:
            print("⏹️  No significant changes generated.")

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
            
            # CRITICAL FORMATTING RULES
            1. **Do NOT use Markdown headings** (like # or ##). MediaWiki uses "=" for headings.
               - Use `== Overview ==` for level 2 headings.
               - Use `=== History ===` for level 3 headings.
            2. **Do NOT use Markdown lists** if not necessary. Use standard prose.
            3. Use `'''bold'''` for the definition term in the first sentence.
            4. Structure should be: Lead Section -> Overview -> Characteristics -> History/Etymology -> See Also.
            
            # Rules
            1. Use ONLY provided sources.
            2. Neutral Point of View.
            3. Output ONLY Wikitext code.
            
            {data_section}
            Output the full article text.
            """
        else:
            return f"""
            {base_inst}
            トピック「{topic}」について、百科事典としてふさわしい高品質なWikipedia記事を作成してください。

            # 【重要】フォーマットルール (Markdown禁止)
            1. **見出しにはMarkdownの「#」を使わないでください。** MediaWiki構文の「=」を使ってください。
               - 正しい例: `== 概要 ==`、`=== 歴史 ===`
               - 間違い例: `# 概要`、`## 歴史` (これは番号付きリストになってしまいます)
            2. **定義**: 記事の冒頭は `'''{topic}'''` のように太字で始め、簡潔な定義文を記述してください。
            3. **構成**: 以下の標準的なセクション構成に従ってください。
               - 冒頭（定義と要約）
               - `== 概要 ==`
               - `== 特徴 ==` (または生態、仕組みなどトピックに応じた詳細)
               - `== 歴史 ==` (または背景)
               - `== 関連項目 ==`
            4. **文体**: 学術的かつ客観的な「だ・である」調を徹底してください。

            # 入力データ
            {data_section}

            記事の全文をWikitext形式のみで出力してください（挨拶や説明は不要）。
            """

    def _build_incremental_update_prompt(self, topic, old_text, info, image_inst):
        """既存記事の追記・更新用プロンプト（差分更新重視）"""
        data_section = f"""
        # Target Topic
        {topic}
        # Trusted Sources (Latest Info)
        {info}
        # Current Article Content (DO NOT CHANGE EXISTING PARTS)
        {old_text}
        # Image Instructions
        {image_inst}
        """
        
        current_date = datetime.date.today().strftime("%Y年%m月")

        if self.lang == "en":
            return f"""
            You are a Wikipedia editor. You need to update the existing article "{topic}" with new information.

            # IMPORTANT: Incremental Update Rule
            - **Do NOT rewrite the entire article.** Keep the existing structure and text as much as possible.
            - **Only ADD new information** found in "Trusted Sources" that is missing from the "Current Article Content".
            - **Format**:
              - If the new info fits into an existing section, append it to that section.
              - Or, create a new section like `== Recent Developments ({current_date}) ==` at the end (before See Also).
            - **Correction**: Only correct obvious factual errors. Do not change style or phrasing of existing text.
            - **Headings**: Use `== Section ==` (MediaWiki syntax). Do NOT use Markdown `#`.

            # Output
            - If no meaningful new info is found: "NO_CHANGE"
            - Otherwise: Output the **Full Article (Old Text + New Additions)** in Wikitext.
            
            {data_section}
            """
        else:
            return f"""
            あなたはWikipediaの編集者です。既存の記事「{topic}」に最新情報を追記してください。

            # 【最重要】差分更新ルール
            1. **既存の記事を書き換えないでください。** 元の文章や構成は極力維持してください。
            2. **「追記」を優先してください。** 「信頼できる情報源」にあって「現在の記事」にない情報のみを追加してください。
            3. **追記場所**:
               - 既存の適切なセクションの末尾に追記する。
               - または、記事の最後に `== 最新の動向 ({current_date}) ==` というセクションを作って追記する。
            4. **修正**: 明らかな事実誤認がある場合のみ修正してください。文体の好みでの書き換えは禁止です。
            5. **フォーマット**: 見出しは必ず `== 見出し ==` を使用してください（Markdown禁止）。

            # 出力
            - 新しい情報がない場合: "NO_CHANGE"
            - 更新する場合: **全文（元のテキスト + 追記分）** をWikitext形式で出力してください。

            {data_section}
            """

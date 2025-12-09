# /opt/auto-wiki/src/bot/wiki_bot.py
# 日本語タイトル: 自律型Wiki Botのメインロジック (v2.3 - Deep Research搭載)
# 目的: 記事の調査(Deep)・吟味・画像・執筆・レビュー・リンク生成・投稿のワークフロー制御

import os
import mwclient
from openai import OpenAI
# from duckduckgo_search import DDGS  <-- 削除またはコメントアウト
from src.bot.commons import CommonsAgent
from src.bot.vetter import InformationVetter
from src.bot.reviewer import ArticleReviewer
from src.bot.researcher import DeepResearcher # 追加
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
        # self.ddgs = DDGS() <-- Researcherに移行するため削除
        self.researcher = DeepResearcher(self.client, model_name, lang=lang) # 追加
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

        # --- Phase 1: Deep Discovery & Research (深層調査) ---
        # 単純な検索ではなく、サブトピックを含めた調査を実行
        try:
            # Note: Researcher内で整形済みのテキストが返ってくる
            raw_research_text = self.researcher.conduct_deep_research(topic)
        except Exception as e:
            print(f"❌ Research phase failed: {e}")
            return

        if not raw_research_text:
            print("❌ No research results found.")
            return

        # --- Phase 2: Vetting (情報の吟味) ---
        # Note: Researcherの出力はテキスト形式なので、Vetterには少し加工して渡すか、
        # あるいはVetter自体を「テキストベースの要約」モードで使う。
        # ここでは既存のVetterロジック（リストを受け取る前提）を維持するため、簡易リスト化するか、
        # あるいはVetterをスキップしてResearcherの出力を信じる手もあるが、
        # ここでは「検索結果テキスト」をそのまま使う形にVetterを経由せず直接渡すフローに変更（Researcherが信頼性フィルタも兼ねているため）
        
        # ただし、元の設計思想「吟味」を残すなら、Researcherの結果をLLMに「Wikiに使える情報だけ抽出して」と頼むのがベスト。
        # 今回はResearcherが既にフィルタリングしているので、この情報を Trusted Sources とする。
        vetted_info = raw_research_text 
        
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
            draft_text = response.choices[0].message.content
        except Exception as e:
            print(f"❌ Generation failed: {e}")
            return

        # --- Phase 4.5: Review & Refine (レビューと修正) ---
        if "NO_CHANGE" not in draft_text:
            # vetted_info (raw_research_text) をソースとして渡してレビュー
            is_approved, feedback = self.reviewer.review_draft(topic, draft_text, vetted_info)
            if not is_approved:
                draft_text = self.reviewer.refine_draft(topic, draft_text, feedback)

        # --- Phase 4.6: Internal Linking (内部リンク生成) ---
        if "NO_CHANGE" not in draft_text:
            try:
                see_also = self._generate_see_also(topic)
                if see_also:
                    draft_text += f"\n\n{see_also}"
            except Exception as e:
                print(f"⚠️ Internal linking failed: {e}")

        # --- Phase 5: Publishing (投稿) ---
        if "NO_CHANGE" not in draft_text and len(draft_text) > 50:
            summary = "Auto-update via Local LLM (Deep Research & Reviewed)"
            final_text = draft_text.replace("```wikitext", "").replace("```", "")
            
            page.save(final_text, summary=summary)
            print("✅ Article saved successfully.")
            
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

    def _build_prompt(self, topic, old_text, info, image_inst):
        data_section = f"""
        # Target Topic
        {topic}
        # Trusted Sources (Based on Deep Research)
        {info}
        # Image Instructions
        {image_inst}
        # Existing Article Content
        {old_text[:3000]}...
        """

        policy = self._load_custom_policy()
        if policy:
            return f"{policy}\n\n{data_section}\n\nOutput the full updated article in Wikitext format."

        if self.lang == "en":
            return f"""
            You are an expert Wikipedia editor.
            Update the article for topic "{topic}" based on the latest information.
            # Rules
            1. No hallucinations. Use only provided information.
            2. Integrate new info into existing content.
            3. Maintain Neutral Point of View (NPOV).
            4. Output ONLY Wikitext format.
            {data_section}
            Output the full updated article. If no changes needed, output "NO_CHANGE".
            """
        else:
            return f"""
            あなたはWikipediaの熟練編集者です。
            トピック「{topic}」について、最新情報に基づき記事を更新してください。
            # ルール
            1. 嘘（ハルシネーション）は厳禁です。提供された情報のみを使用してください。
            2. 既存の記事を破壊せず、新しい情報を統合してください。
            3. 中立的な観点（NPOV）で記述してください。
            4. 出力はWiki構文（Wikitext）のみで行ってください。
            {data_section}
            更新された記事全文を出力してください。変更不要なら "NO_CHANGE" と出力してください。
            """

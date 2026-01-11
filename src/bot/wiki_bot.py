# /opt/auto-wiki/src/bot/wiki_bot.py
# 日本語タイトル: 自律型Wiki Bot (Deep Writer + Strict Mode)
# 目的: 記事を章ごとに分割執筆することで「深み」を出し、かつチャット化を厳格に防止する

import os
import mwclient
import datetime
import json
import re
from openai import OpenAI
from src.bot.commons import CommonsAgent
from src.bot.vetter import InformationVetter
from src.bot.reviewer import ArticleReviewer
from src.bot.researcher import DeepResearcher
from src.rag.vector_store import WikiVectorDB

class LocalWikiBotV2:
    def __init__(self, wiki_host, bot_user, bot_pass, model_name, base_url, lang="ja", google_api_key="", google_cx=""):
        print(f"🤖 Initializing WikiBot (Deep Writer & Strict Mode / Model: {model_name})...")
        self.lang = lang
        
        self.site = mwclient.Site(wiki_host, path='/', scheme='http')
        try:
            self.site.login(bot_user, bot_pass)
        except Exception as e:
            print(f"⚠️ Wiki Login Warning: {e}")
        
        self.client = OpenAI(base_url=base_url, api_key="ollama")
        self.model_name = model_name
        
        self.researcher = DeepResearcher(self.client, model_name, lang=lang, google_api_key=google_api_key, google_cx=google_cx)
        self.commons = CommonsAgent(self.client, model_name)
        self.vetter = InformationVetter(self.client, model_name, lang=lang)
        self.reviewer = ArticleReviewer(self.client, model_name, lang=lang)
        self.vector_db = WikiVectorDB()

    def update_article(self, topic: str):
        # Force Regeneration Logic
        is_force_regenerate = False
        if topic.startswith("REGENERATE:"):
            topic = topic.replace("REGENERATE:", "")
            is_force_regenerate = True
            print(f"♻️  Force Regeneration Mode activated for: {topic}")
        print(f"\n📘 Processing Topic ({self.lang}): {topic}")

        # --- Phase 0: 既存記事の確認 ---
        page = self.site.pages[topic]
        old_text = ""
        is_existing = False
        
        if page.exists and not is_force_regenerate:
            print(f"   ℹ️ Article '{topic}' already exists.")
            old_text = page.text()
            is_existing = True
        elif is_force_regenerate:
            print(f"   🗑️  Ignoring existing content due to forced regeneration.")
            old_text = ""
            is_existing = False
        else:
            print(f"   🆕 Creating NEW article: {topic}")

        # --- Phase 1: Deep Research ---
        try:
            # 調査フェーズ（ここが情報の「深さ」の源泉）
            raw_research_text = self.researcher.conduct_deep_research(topic)
        except Exception as e:
            print(f"❌ Research phase failed: {e}")
            return

        if not raw_research_text:
            print("❌ No research results found.")
            return

        # --- Phase 2: 画像選定 ---
        image_instruction = ""
        if not is_existing or ("[[File:" not in old_text and "[[ファイル:" not in old_text):
            try:
                images = self.commons.search_images(topic)
                best_image = self.commons.select_best_image(topic, images)
                if best_image:
                    clean_name = best_image.replace("File:", "")
                    image_instruction = f"[[File:{clean_name}|thumb|250px|{topic}]]"
            except Exception:
                pass

        # --- Phase 3: Writing (執筆) ---
        print(f"✍️  Starting Writing Process...")
        final_text = ""

        if is_existing:
            # 既存記事は構成を壊さないよう「差分追記モード」で一括処理
            final_text = self._write_incremental(topic, old_text, raw_research_text, image_instruction)
        else:
            # 【重要】新規記事は「分割執筆モード」で深さを出す
            final_text = self._write_deep_article(topic, raw_research_text, image_instruction)

        # --- Phase 4: Publishing (投稿) ---
        # 簡易チェック: 明らかにチャットっぽい応答が含まれていないか
        if final_text and len(final_text) > 50 and "Please provide" not in final_text:
            # チャット定型文の除去（念のため）
            final_text = self._clean_chat_artifacts(final_text)
            
            summary = "Created comprehensive article via Deep Writer." if not is_existing else "Updated with latest research."
            
            # 既存記事と完全に一致しない場合のみ保存
            if final_text.strip() != old_text.strip():
                page.save(final_text, summary=summary)
                print("✅ Article published successfully.")
                self.vector_db.upsert_article(topic, final_text)
            else:
                print("⏹️  No changes detected.")
        else:
            print("❌ Output was invalid or chatty. Aborted.")

    def _write_deep_article(self, topic: str, context: str, image_inst: str) -> str:
        """
        【分割執筆ロジック】
        1. 構成案（目次）を作成
        2. 各章を個別に執筆
        3. 結合して長文記事を生成
        """
        # Step 1: 構成案の作成
        print("   📑 Generating Outline...")
        outline = self._generate_outline(topic, context)
        print(f"   -> Sections: {outline}")
        
        full_article = ""
        
        # Step 2: 導入部（Lead Section）の執筆
        # 書き出しを強制してチャット化を防ぐ
        print("   🖊️  Writing Introduction...")
        intro = self._write_section_strict(topic, "Introduction", context, image_inst, is_intro=True)
        full_article += intro + "\n\n"
        
        # Step 3: 各セクションの執筆
        for section in outline:
            print(f"   🖊️  Writing Section: {section}...")
            section_content = self._write_section_strict(topic, section, context, "")
            full_article += section_content + "\n\n"
            
        # Step 4: 関連項目とカテゴリ
        full_article += self._generate_footer(topic)
        
        return full_article

    def _write_section_strict(self, topic: str, section_title: str, context: str, image_inst: str, is_intro: bool = False) -> str:
        print(f"✍️  Writing Section: {section_title}")
        """
        各セクションを執筆するメソッド（Strict Mode適用）
        """
        system_constraint = """
        [System Command]
        You are an expert Wikipedia editor and academic writer.
        - Write in a neutral, encyclopedic tone.
        - Provide comprehensive details and historical context.
        - Cite sources where possible using <ref> tags if URLs are provided in the input.
        - DO NOT talk to the user or output chat conversational fillers.
        - Output ONLY the requested Wikitext content.
        - Language: JAPANESE (日本語)
        """

        if is_intro:
            # 導入部：定義から強制的に始めさせる
            prompt = f"""
            {system_constraint}
            
            Task: Write the comprehensive lead section for "{topic}".
            Input Data: {context[:6000]}
            Image Code: {image_inst}
            
            Instruction:
            - Start strictly with: '''{topic}''' (bold the title).
            - Write 3-5 solid paragraphs summarizing the entire topic (Definition, History, Significance).
            - Insert the image code if provided.
            - NO headings here.
            """
        else:
            # 各セクション
            prompt = f"""
            {system_constraint}
            
            Task: Write the section "{section_title}" for the article "{topic}".
            Input Data: {context[:6000]}
            
            Instruction:
            - Start strictly with: == {section_title} ==
            - Write detailed paragraphs (at least 400 characters).
            - Use bullet points only for lists.
            """
        
        try:
            resp = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            content = resp.choices[0].message.content.strip()
            
            # Markdownコードブロックの除去
            content = content.replace("```wikitext", "").replace("```", "")
            
            return content
        except Exception as e:
            print(f"⚠️ Section write error: {e}")
            return f"== {section_title} ==\n(Content generation failed)"

    def _generate_outline(self, topic: str, context: str) -> list:
        """記事の構成案（セクションリスト）を作成"""
        prompt = f"""
        List 4-6 main section titles for a Wikipedia article about "{topic}".
        Exclude "Introduction" and "See Also".
        Output ONLY a JSON list of strings. e.g. ["History", "Mechanism", "Impact"]
        Context: {context[:3000]}
        """
        try:
            resp = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            content = resp.choices[0].message.content
            # JSON抽出
            if "[" in content and "]" in content:
                json_str = content[content.find("["):content.rfind("]")+1]
                return json.loads(json_str)
            return ["概要", "歴史", "特徴"]
        except:
            return ["概要", "歴史", "特徴"]

    def _write_incremental(self, topic, old_text, context, image_inst):
        """既存記事の追記用（一括生成）"""
        # 既存の_build_incremental_update_promptを使用
        prompt = self._build_incremental_update_prompt(topic, old_text, context, image_inst)
        try:
            resp = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            return resp.choices[0].message.content.replace("```wikitext", "").replace("```", "")
        except:
            return old_text

    def _build_incremental_update_prompt(self, topic, old_text, info, image_inst):
        # 既存のプロンプト構築ロジック（変更なし）
        current_date = datetime.date.today().strftime("%Y年%m月")
        return f"""
        あなたはWikipedia編集者です。既存記事「{topic}」に最新情報を追記してください。
        
        # ルール
        1. 既存の記事は書き換えず、維持してください。
        2. 新しい情報のみを適切な場所に追記してください。
        3. 全文（元のテキスト + 追記分）を出力してください。
        
        # 入力情報
        {info[:5000]}
        
        # 現在の記事
        {old_text}
        """

    def _generate_footer(self, topic):
        return f"== 関連項目 ==\n* [[Wikipedia]]"
    
    def _clean_chat_artifacts(self, text):
        """AIがつい出力してしまうチャットの残骸を除去"""
        lines = text.split('\n')
        clean_lines = []
        for line in lines:
            # "Here is the article" などを簡易的に除外
            if "Here is" in line or "Sure," in line:
                continue
            clean_lines.append(line)
        return '\n'.join(clean_lines)
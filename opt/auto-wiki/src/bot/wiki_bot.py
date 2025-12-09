# /opt/auto-wiki/src/bot/wiki_bot.py
# 日本語タイトル: 自律型Wiki Bot (Strict Writer Fix)
# 目的: AIの「チャット化」を防ぎ、強制的に記事本文のみを出力させる

import os
import mwclient
import datetime
import json
from openai import OpenAI
# ... 他のimportはそのまま ...
from src.bot.commons import CommonsAgent
from src.bot.vetter import InformationVetter
from src.bot.reviewer import ArticleReviewer
from src.bot.researcher import DeepResearcher
from src.rag.vector_store import WikiVectorDB

class LocalWikiBotV2:
    # __init__ などは変更なし (Deep Writer版またはオリジナル版を維持)
    def __init__(self, wiki_host, bot_user, bot_pass, model_name, base_url, lang="ja"):
        print(f"🤖 Initializing WikiBot (Strict Fix / Model: {model_name})...")
        self.lang = lang
        self.site = mwclient.Site(wiki_host, path='/', scheme='http')
        try:
            self.site.login(bot_user, bot_pass)
        except Exception:
            pass
        self.client = OpenAI(base_url=base_url, api_key="ollama")
        self.model_name = model_name
        self.researcher = DeepResearcher(self.client, model_name, lang=lang)
        self.commons = CommonsAgent(self.client, model_name)
        self.vetter = InformationVetter(self.client, model_name, lang=lang)
        self.reviewer = ArticleReviewer(self.client, model_name, lang=lang)
        self.vector_db = WikiVectorDB()

    # update_article メソッドなども変更なし...
    # (Deep Writer版の update_article を使用している前提で、重要なヘルパーメソッドのみ書き換えます)

    def update_article(self, topic: str):
        # ... (前略) ...
        # Phase 3: Writing Process 呼び出し部分
        print("✍️  Starting Writing Process (Strict Mode)...")
        
        # 既存記事があるかチェック
        page = self.site.pages[topic]
        old_text = page.text() if page.exists else ""
        is_existing = page.exists
        
        # リサーチ結果取得 (DeepResearcher経由)
        research_text = self.researcher.conduct_deep_research(topic)
        if not research_text: return

        image_instruction = ""
        # 画像検索ロジック (省略)

        if is_existing:
            final_text = self._write_incremental(topic, old_text, research_text, image_instruction)
        else:
            # 【修正】Deep Writerモードかどうかに関わらず、ここを厳格化
            # DeepWriter導入済みの場合は _write_deep_article を使用
            # 未導入の場合は _build_creation_prompt を使用
            # ここでは安全のため DeepWriterロジックに対応した修正版を提供
            final_text = self._write_deep_article_strict(topic, research_text, image_instruction)

        if final_text and len(final_text) > 50 and "Please provide" not in final_text:
            page.save(final_text, summary="Auto-generated article.")
            print("✅ Article published.")
        else:
            print("❌ Output was chatty or empty. Publishing aborted.")

    def _write_deep_article_strict(self, topic: str, context: str, image_inst: str) -> str:
        """
        DeepWriterのロジックに「Strict Mode」を適用
        """
        # Step 1: 構成案作成 (ここはLLMに任せてOK)
        outline = self._generate_outline(topic, context)
        
        full_article = ""
        
        # 冒頭（導入部）の作成
        # 【重要】AIに「書き出し」を考えさせず、こちらで指定する
        intro = self._write_section_strict(topic, "Introduction", context, image_inst, is_intro=True)
        full_article += intro + "\n\n"
        
        # Step 2: 各章の執筆
        for section in outline:
            print(f"   🖊️  Writing Section: {section}...")
            section_content = self._write_section_strict(topic, section, context, "")
            full_article += section_content + "\n\n"
            
        full_article += self._generate_footer(topic)
        return full_article

    def _write_section_strict(self, topic: str, section_title: str, context: str, image_inst: str, is_intro: bool = False) -> str:
        """
        AIがチャット化するのを防ぐ厳格な執筆メソッド
        """
        
        # プロンプト汚染を防ぐため、非常に強い制約を入れる
        system_constraint = """
        [System Command]
        You are a text generation engine, NOT a chat assistant.
        - DO NOT talk to the user.
        - DO NOT say "Here is the article" or "Sure!".
        - DO NOT ask questions.
        - Output ONLY the requested Wikitext content.
        - Language: JAPANESE (日本語)
        """

        if is_intro:
            # 導入部：定義から強制的に始めさせる
            prompt = f"""
            {system_constraint}
            
            Task: Write the lead section for "{topic}".
            Input Data: {context[:5000]}
            Image Code: {image_inst}
            
            Start the output strictly with: '''{topic}'''
            """
        else:
            # 各セクション
            prompt = f"""
            {system_constraint}
            
            Task: Write the section "{section_title}" for the article "{topic}".
            Input Data: {context[:5000]}
            
            Start the output strictly with: == {section_title} ==
            """
        
        try:
            resp = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3 # 創造性を少し下げて命令順守率を上げる
            )
            content = resp.choices[0].message.content.strip()
            
            # 安全装置：もしAIがまだチャットしてくる場合（"Sure, here is..."等）、強制削除
            if "\n" in content:
                first_line = content.split("\n")[0]
                if "Sure" in first_line or "Here is" in first_line or "context" in first_line:
                    print("⚠️ Detected chat filler, removing first line...")
                    content = "\n".join(content.split("\n")[1:])
            
            return content
        except Exception as e:
            print(f"⚠️ Section write error: {e}")
            return ""

    # 既存のヘルパーメソッドはそのまま維持
    def _generate_outline(self, topic, context):
        # 前回のコード(DeepWriter)と同じ
        return ["概要", "歴史", "特徴"] 

    def _generate_footer(self, topic):
        return f"== 関連項目 ==\n* [[Wikipedia]]"

    def _write_incremental(self, topic, old_text, context, image_inst):
        # 既存コードと同じ
        return "NO_CHANGE"

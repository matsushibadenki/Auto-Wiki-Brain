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

    def update_article(self, topic: str) -> bool:
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
            research_payload = self.researcher.conduct_deep_research(topic)
        except Exception as e:
            print(f"❌ Research phase failed: {e}")
            return False

        raw_research_text = research_payload.get("formatted_text", "")
        raw_results = research_payload.get("raw_results", [])

        if not raw_research_text:
            print("❌ No research results found.")
            return False

        vetted_research_text = self.vetter.vet_search_results(topic, raw_results)
        writing_context = self._build_writing_context(raw_research_text, vetted_research_text)

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
            final_text = self._write_incremental(topic, old_text, writing_context, image_instruction)
        else:
            # 【重要】新規記事は「分割執筆モード」で深さを出す
            final_text = self._write_deep_article(topic, writing_context, image_instruction)

        final_text, is_review_approved = self._review_and_refine_article(topic, final_text, writing_context)
        if not is_review_approved:
            print("❌ Review did not approve the article. Aborted before publishing.")
            return False

        # --- Phase 4: Publishing (投稿) ---
        final_text = self._clean_chat_artifacts(final_text)
        is_publishable, publish_errors = self._validate_publishable_article(
            topic,
            final_text,
            require_bold_title=not is_existing,
        )
        if is_publishable:
            
            summary = "Created comprehensive article via Deep Writer." if not is_existing else "Updated with latest research."
            
            # 既存記事と完全に一致しない場合のみ保存
            if final_text.strip() != old_text.strip():
                page.save(final_text, summary=summary)
                print("✅ Article published successfully.")
                self.vector_db.upsert_article(topic, final_text)
                return True
            else:
                print("⏹️  No changes detected.")
                return True
        else:
            print(f"❌ Output was invalid or chatty. Aborted. Reasons: {', '.join(publish_errors)}")
            return False

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
        intro_brief = self._build_section_brief(topic, "Introduction", context, is_intro=True)
        intro = self._write_section_strict(topic, "Introduction", intro_brief, image_inst, is_intro=True)
        full_article += intro + "\n\n"
        
        # Step 3: 各セクションの執筆
        for section in outline:
            print(f"   🖊️  Writing Section: {section}...")
            section_brief = self._build_section_brief(topic, section, context)
            section_content = self._write_section_strict(topic, section, section_brief, "")
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
        - Every concrete claim must be supported by the provided input notes.
        - If support is weak or contradictory, omit the claim instead of guessing.
        - Do not invent integrations, release dates, target users, benchmarks, or product names.
        - Language: JAPANESE (日本語)
        """

        if is_intro:
            # 導入部：定義から強制的に始めさせる
            prompt = f"""
            {system_constraint}
            
            Task: Write the comprehensive lead section for "{topic}".
            Input Data: {context[:5000]}
            Image Code: {image_inst}
            
            Instruction:
            - Start strictly with: '''{topic}''' (bold the title).
            - Write 3-5 solid paragraphs summarizing the entire topic (Definition, History, Significance).
            - Mention only facts grounded in the input data. Omit uncertain claims.
            - If a fact has a URL in the notes, preserve it with <ref>...</ref> where natural.
            - Insert the image code if provided.
            - NO headings here.
            """
        else:
            # 各セクション
            prompt = f"""
            {system_constraint}
            
            Task: Write the section "{section_title}" for the article "{topic}".
            Input Data: {context[:5000]}
            
            Instruction:
            - Start strictly with: == {section_title} ==
            - Write detailed paragraphs (at least 400 characters).
            - Use bullet points only for lists.
            - Prioritize concrete facts, dates, organizations, and cause/effect relationships that are supported by the input.
            - If a claim is not clearly supported, leave it out.
            - Add <ref>URL</ref> only when the source URL is available in the notes.
            - Do not repeat the lead verbatim.
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
        トピック「{topic}」について、日本語の百科事典記事に適した主要セクション見出しを4-5個だけ提案してください。
        条件:
        - 日本語のみを使う
        - 括弧書きのローマ字や英訳を付けない
        - 「導入」「関連項目」は含めない
        - 製品やソフトウェア記事なら「概要」「開発」「機能」「利用状況」「評価」「課題」のような百科事典的見出しを優先する
        - 「インストール」「使い方」「利用例」のようなマニュアル風見出しは避ける
        - 重複や言い換えの重なりを避ける
        Output ONLY a JSON list of strings.
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
                return self._normalize_outline(json.loads(json_str))
            return self._default_outline()
        except:
            return self._default_outline()

    def _build_writing_context(self, raw_research_text: str, vetted_research_text: str) -> str:
        """執筆に使う一次コンテキストを整理する"""
        sections = []
        if vetted_research_text.strip():
            sections.append("## Verified Notes\n" + vetted_research_text.strip())
        if raw_research_text.strip():
            sections.append("## Search Digest\n" + raw_research_text[:6000].strip())
        return "\n\n".join(sections)

    def _build_section_brief(self, topic: str, section_title: str, context: str, is_intro: bool = False) -> str:
        """章ごとに必要な観点だけを圧縮して渡す"""
        task_label = "lead section" if is_intro else f'section "{section_title}"'
        prompt = f"""
        You are preparing a factual writing brief for a Wikipedia editor.
        Topic: "{topic}"
        Target: {task_label}

        Source Notes:
        {context[:5000]}

        Instruction:
        - Extract only the facts most relevant to the target section.
        - Prefer dates, named entities, definitions, chronology, mechanisms, and impacts.
        - Omit speculation and unsupported claims.
        - Return concise bullet points only.
        """
        try:
            resp = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            content = resp.choices[0].message.content
            cleaned = content.strip() if content else ""
            return cleaned or context[:2500]
        except Exception as e:
            print(f"⚠️ Brief generation error: {e}")
            return context[:2500]

    def _review_and_refine_article(self, topic: str, draft: str, sources: str) -> tuple[str, bool]:
        """公開前レビューを通し、必要なら1回だけ自動修正する"""
        if not draft.strip():
            return draft, False

        approved, feedback = self.reviewer.review_draft(topic, draft, sources)
        if approved:
            return draft, True

        refined = self.reviewer.refine_draft(topic, draft, feedback, sources)
        if not refined.strip():
            return draft, False

        second_pass, _ = self.reviewer.review_draft(topic, refined, sources)
        if second_pass:
            return refined, True
        return refined, False

    def _default_outline(self) -> list:
        return ["概要", "沿革", "機能", "利用と反応", "評価と課題"]

    def _normalize_outline(self, sections: list) -> list:
        """不自然な見出しやマニュアル調の見出しを除外して正規化する"""
        banned_keywords = ["インストール", "使い方", "利用例", "チュートリアル", "features", "see also"]
        normalized = []

        for section in sections:
            if not isinstance(section, str):
                continue
            title = re.sub(r"\s*\([^)]*\)", "", section).strip()
            title = re.sub(r"\s+", "", title)
            if not title:
                continue
            lower_title = title.lower()
            if any(keyword in lower_title for keyword in banned_keywords):
                continue
            if title in normalized:
                continue
            normalized.append(title)

        return normalized[:5] if normalized else self._default_outline()

    def _validate_publishable_article(self, topic: str, text: str, require_bold_title: bool = True) -> tuple[bool, list[str]]:
        """公開可能な最低限の品質を満たすか確認する"""
        errors = []

        if not text or len(text.strip()) < 200:
            errors.append("too_short")

        chat_markers = ["Please provide", "Here is", "Certainly!", "もちろんです", "以下に"]
        if any(marker in text for marker in chat_markers):
            errors.append("chatty_phrase_detected")

        if require_bold_title and f"'''{topic}'''" not in text:
            errors.append("missing_bold_title")

        headings = re.findall(r"^==\s*.+?\s*==\s*$", text, flags=re.MULTILINE)
        if len(headings) < 2:
            errors.append("too_few_headings")

        if re.search(r"==\s*Introduction\s*==", text, flags=re.IGNORECASE):
            errors.append("english_introduction_heading")

        return len(errors) == 0, errors

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
            if "Here is" in line or "Sure," in line or "もちろんです" in line or "以下に" in line:
                continue
            clean_lines.append(line)
        return '\n'.join(clean_lines)

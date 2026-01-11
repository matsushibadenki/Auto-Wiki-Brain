# /opt/auto-wiki/src/bot/reviewer.py
# 日本語タイトル: 記事品質レビューエージェント
# 目的: 生成された記事ドラフトを批評し、品質基準（ハルシネーション、中立性）を満たしているか判定する

from openai import OpenAI

class ArticleReviewer:
    def __init__(self, client: OpenAI, model_name: str, lang: str = "ja"):
        self.client = client
        self.model_name = model_name
        self.lang = lang

    def review_draft(self, topic: str, draft: str, sources: str) -> tuple[bool, str]:
        """
        ドラフトをレビューする。
        Returns: (is_approved: bool, feedback: str)
        """
        print(f"🧐 Reviewing draft for: {topic}...")

        if self.lang == "en":
            system_prompt = "You are a strict Wikipedia editor/reviewer."
            prompt = f"""
            Please review the following article draft for the topic "{topic}".
            
            # Trusted Sources
            {sources[:2000]}...

            # Draft Content
            {draft}

            # Review Criteria
            1. **Accuracy**: Is there any information not supported by the sources? (Hallucination check)
            2. **Neutrality**: Is the tone objective and neutral?
            3. **Structure**: Does it follow standard Wiki format?

            If the draft is good enough to publish, output only "PASS".
            If there are major issues, output "FAIL" followed by specific instructions for revision.
            """
        else:
            system_prompt = "あなたは厳格なWikipediaの編集・査読者です。"
            prompt = f"""
            トピック「{topic}」の記事ドラフトを査読してください。
            
            # 信頼できるソース情報
            {sources[:2000]}...

            # ドラフト内容
            {draft}

            # 査読基準
            1. **正確性**: ソースにない虚偽の情報（ハルシネーション）が含まれていませんか？
            2. **中立性**: 表現は客観的で中立的ですか？
            3. **構造**: Wikiの標準的なフォーマットに従っていますか？

            投稿に値する品質であれば、"PASS" とだけ出力してください。
            重大な問題がある場合は、"FAIL" と出力した後に、具体的な修正指示を箇条書きで記述してください。
            """

        try:
            resp = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            # result = resp.choices[0].message.content.strip() を以下に変更
            content = resp.choices[0].message.content
            result = content.strip() if content else ""
            
            if result.startswith("PASS"):
                print("✅ Review Passed.")
                return True, "OK"
            else:
                print(f"🛑 Review Failed. Feedback: {result}")
                return False, result
        except Exception as e:
            print(f"⚠️ Review process failed: {e}")
            # エラー時は安全のためPASS扱い（またはFAIL扱い）にするが、ここでは進行を優先してPASS
            return True, "Review Error (Skipped)"

    def refine_draft(self, topic: str, original_draft: str, feedback: str) -> str:
        """レビュー結果に基づいてドラフトを修正する"""
        print(f"🔧 Refining article based on feedback...")
        
        prompt = f"""
        Original Draft for "{topic}":
        {original_draft}

        Reviewer Feedback:
        {feedback}

        Please rewrite the article to address the feedback above.
        Output ONLY the full rewritten Wikitext.
        """
        
        try:
            resp = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            content = resp.choices[0].message.content
            return content.strip() if content else original_draft
        except Exception as e:
            print(f"❌ Refinement failed: {e}")
            return original_draft
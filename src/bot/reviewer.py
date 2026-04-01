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
        print(f"🧐 Reviewing draft for: {topic}...")

        if self.lang == "en":
            system_prompt = "You are a strict Wikipedia editor and reviewer."
            prompt = f'''Review the following encyclopedia draft for "{topic}".

Trusted Sources:
{sources[:3500]}

Draft:
{draft}

Criteria:
1. Reject claims not grounded in the trusted sources.
2. Reject promotional, speculative, or tutorial-like writing.
3. Reject made-up products, integrations, dates, or organizations.
4. Check whether section titles are encyclopedic.

If publishable, output only PASS.
Otherwise output FAIL followed by short bullet-point revision instructions.'''
        else:
            system_prompt = "あなたは厳格なWikipediaの編集・査読者です。"
            prompt = f'''トピック「{topic}」の記事ドラフトを査読してください。

信頼できるソース情報:
{sources[:3500]}

ドラフト内容:
{draft}

査読基準:
1. 信頼できるソースで裏付けられない主張は不合格です。
2. 宣伝調、断定しすぎ、推測、マニュアル調は不合格です。
3. 実在が確認できない製品名、統合機能、日付、組織名は不合格です。
4. 見出しが百科事典向けかを確認してください。

投稿に値するなら PASS のみを返してください。
問題があるなら FAIL の後に、短い箇条書きで修正指示を返してください。'''

        try:
            resp = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0
            )
            content = resp.choices[0].message.content
            result = content.strip() if content else ""
            if result.startswith("PASS"):
                print("✅ Review Passed.")
                return True, "OK"
            print(f"🛑 Review Failed. Feedback: {result}")
            return False, result
        except Exception as e:
            print(f"⚠️ Review process failed: {e}")
            return False, "FAIL\n- レビュー工程でエラーが発生したため安全側で再生成が必要です。"

    def refine_draft(self, topic: str, original_draft: str, feedback: str, sources: str = "") -> str:
        print("🔧 Refining article based on feedback...")
        prompt = f'''Topic: "{topic}"

Original Draft:
{original_draft}

Reviewer Feedback:
{feedback}

Trusted Sources:
{sources[:3500]}

Rewrite Instructions:
- Keep only claims that are clearly grounded in the trusted sources.
- Remove unsupported integrations, target-user claims, and release-date claims unless explicitly supported.
- Keep a neutral encyclopedic tone.
- Output only full Wikitext.'''
        try:
            resp = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "Rewrite conservatively. If evidence is weak, omit the claim."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1
            )
            content = resp.choices[0].message.content
            return content.strip() if content else original_draft
        except Exception as e:
            print(f"❌ Refinement failed: {e}")
            return original_draft

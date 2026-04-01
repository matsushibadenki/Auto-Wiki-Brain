# /opt/auto-wiki/src/bot/vetter.py
# 情報吟味エージェント
# 目的: 検索結果がWikipediaの出典として適切か判定・要約する

from openai import OpenAI


class InformationVetter:
    def __init__(self, client: OpenAI, model_name: str, lang: str = "ja"):
        self.client = client
        self.model_name = model_name
        self.lang = lang

    def vet_search_results(self, topic: str, raw_results: list) -> str:
        if not raw_results:
            return ""

        print(f"🧐 Vetting {len(raw_results)} search results for '{topic}'...")

        combined_text = ""
        for r in raw_results[:20]:
            body = r.get("body", "") or r.get("snippet", "")
            title = r.get("title", "")
            href = r.get("href", "")
            combined_text += f"Title: {title}\nURL: {href}\nContent: {body}\n---\n"

        if self.lang == "en":
            prompt = f'''You are a Wikipedia reliability assessor.
From the search results for "{topic}", extract only reliable facts that are explicitly supported.

Search Results:
{combined_text}

Instructions:
- Prefer official docs, major publishers, academic or institutional sources.
- Exclude blogs, forums, affiliate pages, unsourced opinions, and promotional claims.
- Output bullet points only.
- Each bullet must include: fact | source title | source URL
- If nothing reliable exists, output NO_INFO.'''
        else:
            prompt = f'''あなたはWikipedia向けの出典精査担当です。
以下の検索結果から、トピック「{topic}」について明示的に裏付けられる信頼性の高い事実だけを抽出してください。

検索結果:
{combined_text}

指示:
- 公式文書、大手報道、学術機関、公的機関を優先してください。
- 個人ブログ、掲示板、宣伝文、根拠のない評価は除外してください。
- 箇条書きのみで出力してください。
- 各項目は「事実 | 出典タイトル | 出典URL」の形式にしてください。
- 信頼できる情報がなければ NO_INFO と返してください。'''

        try:
            resp = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "Output only concise factual bullet points. Do not invent citations."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1
            )
            content = resp.choices[0].message.content
            vetted_text = content.strip() if content else ""
            if "NO_INFO" in vetted_text:
                return ""
            return vetted_text
        except Exception as e:
            print(f"⚠️ Vetting error: {e}")
            return ""

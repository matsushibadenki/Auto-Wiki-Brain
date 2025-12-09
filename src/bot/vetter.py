# /opt/auto-wiki/src/bot/vetter.py
# 情報吟味エージェント
# 目的: 検索結果がWikipediaの出典として適切か判定・要約する

from openai import OpenAI

class InformationVetter:
    def __init__(self, client: OpenAI, model_name: str):
        self.client = client
        self.model_name = model_name

    def vet_search_results(self, topic: str, raw_results: list) -> str:
        """検索結果を吟味し、有用な情報のみを抽出・要約して返す"""
        if not raw_results:
            return ""

        print(f"🧐 Vetting {len(raw_results)} search results for '{topic}'...")

        # 検索結果をテキスト化
        combined_text = ""
        for r in raw_results:
            body = r.get('body', '') or r.get('snippet', '')
            title = r.get('title', '')
            href = r.get('href', '')
            combined_text += f"Title: {title}\nURL: {href}\nContent: {body}\n---\n"

        prompt = f"""
        あなたはWikipediaの信頼性評価担当者です。
        以下のWeb検索結果から、トピック「{topic}」のWikipedia記事執筆に使用できる「信頼できる客観的事実」のみを抽出してください。
        
        # 検索結果
        {combined_text}
        
        # 指示
        1. 広告、個人的なブログ、掲示板、信頼性の低い情報は無視してください。
        2. 事実関係（日付、数値、出来事）を中心に箇条書きで抽出してください。
        3. 該当する情報がない場合は "NO_INFO" と返してください。
        """

        try:
            resp = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            vetted_text = resp.choices[0].message.content.strip()
            
            if "NO_INFO" in vetted_text:
                return ""
            
            return vetted_text

        except Exception as e:
            print(f"⚠️ Vetting error: {e}")
            return ""
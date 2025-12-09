# /opt/auto-wiki/src/bot/researcher.py
# 日本語タイトル: 深層リサーチエージェント
# 目的: 単一の検索ではなく、多角的な視点（サブトピック）で検索を行い、深く網羅的な情報を収集する

from duckduckgo_search import DDGS
from openai import OpenAI
import json

class DeepResearcher:
    def __init__(self, client: OpenAI, model_name: str, lang: str = "ja"):
        self.client = client
        self.model_name = model_name
        self.lang = lang
        self.ddgs = DDGS()

    def conduct_deep_research(self, topic: str, max_sub_topics: int = 3) -> str:
        """
        トピックについて深層調査を行うメインメソッド
        1. 調査計画の立案（サブトピック生成）
        2. 各サブトピックの検索実行
        3. 情報の統合
        """
        print(f"🕵️ Deep Researching for: {topic}")
        
        # Step 1: 調査計画の立案
        plan = self._create_research_plan(topic, max_sub_topics)
        print(f"   📋 Research Plan: {plan}")

        combined_results = []
        
        # Step 2: メイントピックの検索（基本情報の確保）
        print(f"   🔎 Searching Main Topic: {topic}")
        main_results = self._search(topic)
        combined_results.extend(main_results)

        # Step 3: サブトピックの検索（詳細情報の確保）
        for sub_query in plan:
            print(f"   🔎 Searching Sub-topic: {sub_query}")
            # サブトピックはより具体的な情報を狙う
            sub_results = self._search(f"{topic} {sub_query}")
            combined_results.extend(sub_results)

        # Step 4: 結果の重複排除とテキスト化
        final_context = self._process_results(combined_results)
        return final_context

    def _create_research_plan(self, topic: str, count: int) -> list:
        """LLMを使って調査すべき「サブトピック（観点）」をリストアップする"""
        if self.lang == "en":
            prompt = f"""
            To write a comprehensive Wikipedia article about "{topic}", what are the {count} most important sub-topics or aspects to research?
            Return ONLY a JSON list of short strings. Example: ["History", "Mechanism", "Criticism"]
            """
        else:
            prompt = f"""
            「{topic}」に関する包括的なWikipedia記事を書くために、調査すべき重要な「サブトピック（観点）」を{count}つ挙げてください。
            例: 歴史、仕組み、メリット・デメリット、社会的影響
            余計な説明は不要です。JSON形式のリストのみを返してください。
            例: ["歴史", "技術的仕組み", "課題"]
            """

        try:
            resp = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            raw_content = resp.choices[0].message.content
            content = raw_content.strip() if raw_content else "[]"
            
            # JSON部分だけ抽出（Markdownタグ対策）
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            plan = json.loads(content)
            return plan[:count] # 指定数に制限
        except Exception as e:
            print(f"⚠️ Plan generation failed: {e}")
            # フォールバック: 一般的な観点を返す
            return ["概要", "歴史", "特徴"] if self.lang == "ja" else ["Overview", "History", "Features"]

    def _search(self, query: str, limit: int = 5) -> list:
        """検索を実行するヘルパー"""
        results = []
        try:
            # 言語設定（日米クロスサーチの簡易実装：英語圏の情報が必要ならここで分岐可能）
            region = "jp-jp" if self.lang == "ja" else "us-en"
            
            # DDG検索実行
            raw_res = self.ddgs.text(query, region=region, max_results=limit)
            if raw_res:
                results.extend(raw_res)
                
        except Exception as e:
            print(f"⚠️ Search error for '{query}': {e}")
        return results

    def _process_results(self, raw_results: list) -> str:
        """検索結果を整形・重複排除してテキスト化する"""
        seen_urls = set()
        formatted_text = ""
        
        # 信頼性の低いドメイン除外（簡易ブラックリスト）
        blocked_domains = ["spam.com", "example.com"] 

        idx = 1
        for res in raw_results:
            url = res.get('href', '')
            if url in seen_urls or any(d in url for d in blocked_domains):
                continue
            
            seen_urls.add(url)
            title = res.get('title', 'No Title')
            body = res.get('body', '')
            
            formatted_text += f"[Source {idx}]\nTitle: {title}\nURL: {url}\nContent: {body}\n\n"
            idx += 1
            
            if idx > 15: # コンテキストあふれ防止のため件数制限
                break
                
        return formatted_text

# /opt/auto-wiki/src/bot/researcher.py
# 日本語タイトル: 深層リサーチエージェント (Parallelized)
# 目的: マルチスレッド化により検索速度を大幅に向上させたリサーチエージェント

from duckduckgo_search import DDGS
from openai import OpenAI
import json
import concurrent.futures

class DeepResearcher:
    def __init__(self, client: OpenAI, model_name: str, lang: str = "ja"):
        self.client = client
        self.model_name = model_name
        self.lang = lang
        # DDGSインスタンスはスレッドセーフでない場合があるため、メソッド内で生成推奨

    def conduct_deep_research(self, topic: str, max_sub_topics: int = 3) -> str:
        """
        トピックについて深層調査を行うメインメソッド (並列処理版)
        """
        print(f"🕵️ Deep Researching for: {topic}")
        
        # Step 1: 調査計画の立案
        plan = self._create_research_plan(topic, max_sub_topics)
        print(f"   📋 Research Plan: {plan}")

        combined_results = []
        
        # 検索クエリのリスト作成（メイントピック + サブトピック）
        queries = [topic] + [f"{topic} {sub}" for sub in plan]

        # Step 2 & 3: 並列検索実行
        print(f"   🚀 Executing {len(queries)} searches in parallel...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            # 各クエリに対して _search メソッドを並列実行
            future_to_query = {executor.submit(self._search, q): q for q in queries}
            
            for future in concurrent.futures.as_completed(future_to_query):
                query = future_to_query[future]
                try:
                    data = future.result()
                    combined_results.extend(data)
                    print(f"      ✔ Finished search for: {query}")
                except Exception as exc:
                    print(f"      ❌ Search failed for {query}: {exc}")

        # Step 4: 結果の重複排除とテキスト化
        final_context = self._process_results(combined_results)
        return final_context

    def _create_research_plan(self, topic: str, count: int) -> list:
        """LLMを使って調査すべき「サブトピック（観点）」をリストアップする"""
        # (ここは変更なし)
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
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            plan = json.loads(content)
            return plan[:count]
        except Exception as e:
            print(f"⚠️ Plan generation failed: {e}")
            return ["概要", "歴史", "特徴"] if self.lang == "ja" else ["Overview", "History", "Features"]

    def _search(self, query: str, limit: int = 5) -> list:
        """検索を実行するヘルパー (スレッドセーフにするため都度DDGS生成)"""
        results = []
        try:
            region = "jp-jp" if self.lang == "ja" else "us-en"
            # インスタンスをここで生成してスレッド競合を防ぐ
            with DDGS() as ddgs:
                raw_res = ddgs.text(query, region=region, max_results=limit)
                if raw_res:
                    results.extend(raw_res)
        except Exception as e:
            print(f"⚠️ Search error for '{query}': {e}")
        return results

    def _process_results(self, raw_results: list) -> str:
        """検索結果を整形・重複排除してテキスト化する"""
        seen_urls = set()
        formatted_text = ""
        blocked_domains = ["spam.com", "example.com"] 

        idx = 1
        for res in raw_results:
            url = res.get('href', '')
            # 重複URLおよびブラックリスト判定
            if url in seen_urls or any(d in url for d in blocked_domains):
                continue
            
            seen_urls.add(url)
            title = res.get('title', 'No Title')
            body = res.get('body', '')
            
            formatted_text += f"[Source {idx}]\nTitle: {title}\nURL: {url}\nContent: {body}\n\n"
            idx += 1
            
            if idx > 20: # 収集効率が上がったので上限を少し緩和
                break
                
        return formatted_text

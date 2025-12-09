# /opt/auto-wiki/src/bot/researcher.py
# 日本語タイトル: 反復型深層リサーチエージェント (Iterative Deep Research)
# 目的: 検索→分析→不足情報の再検索というサイクルを回し、網羅的な情報を収集する

from duckduckgo_search import DDGS
from openai import OpenAI
import json
import concurrent.futures

class DeepResearcher:
    def __init__(self, client: OpenAI, model_name: str, lang: str = "ja"):
        self.client = client
        self.model_name = model_name
        self.lang = lang

    def conduct_deep_research(self, topic: str, max_iterations: int = 2) -> str:
        """
        反復型の深層調査を行う
        1. 初期調査（広範囲）
        2. 不足情報の分析と追加調査（反復）
        """
        print(f"🕵️ Deep Researching for: {topic} (Iterative Mode)")
        
        # Phase 1: 初期調査 (Initial Breadth Search)
        # 基本的な観点（歴史、概要、仕組みなど）を網羅する
        initial_plan = self._create_initial_plan(topic)
        print(f"   📋 Initial Plan: {initial_plan}")
        
        current_context = []
        queries = [topic] + [f"{topic} {sub}" for sub in initial_plan]
        current_context.extend(self._execute_parallel_search(queries))
        
        # Phase 2: 反復調査 (Iterative Depth Search)
        formatted_text = self._process_results(current_context)
        
        for i in range(max_iterations):
            print(f"   🔄 Iteration {i+1}/{max_iterations}: Analyzing missing information...")
            
            # 現在の情報で足りないものを分析
            missing_queries = self._identify_missing_info(topic, formatted_text)
            
            if not missing_queries:
                print("   ✅ Sufficient information gathered.")
                break
                
            print(f"   🔍 Digging deeper into: {missing_queries}")
            new_results = self._execute_parallel_search(missing_queries)
            
            if not new_results:
                print("   ⚠️ No new info found.")
                break
                
            current_context.extend(new_results)
            # コンテキストを更新して次のループへ
            formatted_text = self._process_results(current_context)

        return formatted_text

    def _execute_parallel_search(self, queries: list) -> list:
        """クエリリストを並列実行して結果を返す"""
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_query = {executor.submit(self._search, q): q for q in queries}
            for future in concurrent.futures.as_completed(future_to_query):
                try:
                    data = future.result()
                    if data:
                        results.extend(data)
                except Exception as e:
                    print(f"      ❌ Search error: {e}")
        return results

    def _create_initial_plan(self, topic: str) -> list:
        """初期調査計画の立案"""
        if self.lang == "en":
            prompt = f'List 4 essential sub-topics to understand "{topic}" as a JSON list. e.g. ["History", "Impact"]'
        else:
            prompt = f'「{topic}」をWikipediaレベルで解説するために必須となる4つの観点をJSONリストで挙げてください。例: ["歴史", "仕組み", "問題点", "社会的影響"]'

        return self._get_json_list(prompt)

    def _identify_missing_info(self, topic: str, current_text: str) -> list:
        """現在の調査結果を評価し、追加で調べるべき具体的な検索クエリを生成する"""
        # コンテキストが長すぎる場合は要約してから渡すなどの工夫が必要だが、ここでは先頭4000文字で判断させる
        short_context = current_text[:4000]
        
        if self.lang == "en":
            prompt = f"""
            You are a rigorous researcher. Based on the "Current Notes", what critical information is missing to write a PERFECT Wikipedia article about "{topic}"?
            
            Current Notes:
            {short_context}...

            Output ONLY a JSON list of 3 specific search queries to find the missing details.
            If no more info is needed, output [].
            """
        else:
            prompt = f"""
            あなたは厳格なリサーチャーです。「現在の調査メモ」を確認し、トピック「{topic}」について完璧な解説記事を書くために『欠けている重要な情報』は何ですか？
            
            現在の調査メモ:
            {short_context}...

            その欠けている情報を探すための「具体的な検索クエリ」を3つ、JSONリスト形式で出力してください。
            これ以上調査が不要な場合は [] を出力してください。
            """
            
        return self._get_json_list(prompt)

    def _get_json_list(self, prompt: str) -> list:
        """LLMからJSONリストを堅牢に取得するヘルパー"""
        try:
            resp = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            content = resp.choices[0].message.content.strip()
            # Markdownタグの除去
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            elif "[" not in content:
                return []
                
            return json.loads(content)
        except Exception:
            return []

    def _search(self, query: str, limit: int = 5) -> list:
        """DuckDuckGo検索実行"""
        results = []
        try:
            region = "jp-jp" if self.lang == "ja" else "us-en"
            with DDGS() as ddgs:
                raw_res = ddgs.text(query, region=region, max_results=limit)
                if raw_res:
                    results.extend(raw_res)
        except Exception as e:
            print(f"⚠️ Search failed for '{query}': {e}")
        return results

    def _process_results(self, raw_results: list) -> str:
        """結果の整形（重複排除・ブラックリスト適用）"""
        seen_urls = set()
        formatted_text = ""
        blocked = ["spam.com", "example.com"] 

        idx = 1
        for res in raw_results:
            url = res.get('href', '')
            if url in seen_urls or any(d in url for d in blocked):
                continue
            
            seen_urls.add(url)
            title = res.get('title', 'No Title')
            body = res.get('body', '')
            
            formatted_text += f"[Source {idx}] Title: {title}\nURL: {url}\nContent: {body}\n\n"
            idx += 1
            if idx > 30: break # Deepモードなので少し多めに許容
                
        return formatted_text

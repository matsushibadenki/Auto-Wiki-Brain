# /opt/auto-wiki/src/bot/researcher.py
# 日本語タイトル: 反復型深層リサーチエージェント (Iterative Deep Research)
# 目的: 検索→分析→不足情報の再検索というサイクルを回し、網羅的な情報を収集する

from ddgs import DDGS
from openai import OpenAI
import concurrent.futures
import json
import re
import requests
from urllib.parse import urlparse

PREFERRED_DOMAINS = [
    "anthropic.com",
    "docs.anthropic.com",
    "wikipedia.org",
    "wikimedia.org",
    "github.com",
    "developer.mozilla.org",
    "arxiv.org",
]

BLOCKED_DOMAINS = [
    "spam.com",
    "example.com",
    "pinterest.",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "reddit.com",
    "quora.com",
]


class DeepResearcher:
    def __init__(self, client: OpenAI, model_name: str, lang: str = "ja", google_api_key="", google_cx=""):
        self.client = client
        self.model_name = model_name
        self.lang = lang
        self.google_api_key = google_api_key
        self.google_cx = google_cx

    def conduct_deep_research(self, topic: str, max_iterations: int = 2) -> dict:
        print(f"🕵️ Deep Researching for: {topic} (Iterative Mode)")
        print(f"🚀  Starting Deep Research for: {topic}")

        initial_plan = self._create_initial_plan(topic)
        print(f"   📋 Initial Plan: {initial_plan}")

        queries = self._build_initial_queries(topic, initial_plan)
        current_context = self._execute_parallel_search(queries)
        formatted_text = self._process_results(current_context)

        for i in range(max_iterations):
            print(f"   🔄 Iteration {i+1}/{max_iterations}: Analyzing missing information...")
            raw_missing_queries = self._identify_missing_info(topic, formatted_text)
            missing_queries = self._normalize_query_list(raw_missing_queries)

            if not missing_queries:
                print("   ✅ Sufficient information gathered.")
                break

            print(f"   🔍 Digging deeper into: {missing_queries}")
            new_results = self._execute_parallel_search(missing_queries)
            if not new_results:
                print("   ⚠️ No new info found.")
                break

            current_context.extend(new_results)
            formatted_text = self._process_results(current_context)

        return {
            "formatted_text": formatted_text,
            "raw_results": current_context,
        }

    def _build_initial_queries(self, topic: str, plan: list) -> list[str]:
        cleaned_subs = self._normalize_query_list(plan)
        queries = [topic]
        queries.extend(f"{topic} {sub}" for sub in cleaned_subs[:6])

        if self.lang == "ja":
            queries.extend([
                f"{topic} 公式",
                f"{topic} Anthropic",
                f"{topic} documentation",
                f"site:anthropic.com {topic}",
                f"site:docs.anthropic.com {topic}",
            ])
        else:
            queries.extend([
                f"{topic} official",
                f"site:anthropic.com {topic}",
                f"site:docs.anthropic.com {topic}",
                f"{topic} documentation",
            ])

        deduped = []
        for query in queries:
            normalized = re.sub(r"\s+", " ", str(query)).strip()
            if normalized and normalized not in deduped:
                deduped.append(normalized)
        return deduped[:10]

    def _normalize_query_list(self, values: list) -> list[str]:
        normalized = []
        for value in values:
            if isinstance(value, dict):
                candidate = value.get("観点", value.get("sub_topic", next(iter(value.values()), "")))
            else:
                candidate = value
            candidate_text = re.sub(r"\s+", " ", str(candidate)).strip()
            if candidate_text and candidate_text not in normalized:
                normalized.append(candidate_text)
        return normalized

    def _execute_parallel_search(self, queries: list) -> list:
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

        if not results:
            fallback_queries = self._build_fallback_queries(queries)
            if fallback_queries:
                print(f"      ♻️ Retrying with broader queries: {fallback_queries}")
                with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                    future_to_query = {executor.submit(self._search, q): q for q in fallback_queries}
                    for future in concurrent.futures.as_completed(future_to_query):
                        try:
                            data = future.result()
                            if data:
                                results.extend(data)
                        except Exception as e:
                            print(f"      ❌ Fallback search error: {e}")
        return results

    def _build_fallback_queries(self, queries: list) -> list:
        fallback_queries = []
        for query in queries[:5]:
            simplified = re.sub(r"\s*\([^)]*\)", "", str(query)).strip()
            simplified = re.sub(r"\s+", " ", simplified)
            base = simplified.split(" ")[0] if simplified else ""
            for candidate in [simplified, base]:
                if candidate and candidate not in fallback_queries:
                    fallback_queries.append(candidate)
        return fallback_queries[:4]

    def _create_initial_plan(self, topic: str) -> list:
        if self.lang == "en":
            prompt = f'List 6 essential and specific research angles needed to write a factual encyclopedia article about "{topic}" as a JSON list of short strings. Include definition, history, mechanism, real-world use, criticism, and impact. Avoid tutorial-style headings.'
        else:
            prompt = f'「{topic}」について、百科事典レベルの記事を書くために必要な調査観点を6個、短い日本語のJSONリストで返してください。定義、歴史、仕組み、利用実態、評価、批判や課題を含め、マニュアル風の観点は避けてください。'
        return self._get_json_list(prompt)

    def _identify_missing_info(self, topic: str, current_text: str) -> list:
        short_context = current_text[:5000]
        if self.lang == "en":
            prompt = f'''You are a rigorous encyclopedia researcher. Based on the current notes about "{topic}", identify missing facts that are still required.

Current Notes:
{short_context}

Return ONLY a JSON list of up to 4 concrete web search queries. Prioritize official documentation, release notes, named people or organizations, dates, and disputed claims that still need evidence. Return [] if enough evidence already exists.'''
        else:
            prompt = f'''あなたは百科事典記事のための厳格な調査担当です。トピック「{topic}」に関する現在の調査メモを読み、まだ裏付けが足りない重要事項を特定してください。

現在の調査メモ:
{short_context}

出力は、追加で調べるべき具体的な検索クエリを最大4件、JSONリストのみで返してください。公式文書、発表資料、固有名詞、日付、論争点の裏付けを優先してください。十分なら [] を返してください。'''
        return self._get_json_list(prompt)

    def _get_json_list(self, prompt: str) -> list:
        try:
            resp = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "Return strictly valid JSON. Do not add commentary or markdown fences."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1
            )
            raw_content = resp.choices[0].message.content
            if not raw_content:
                return []
            content = raw_content.strip()
            if "```json" in content:
                content = content.split("```json", 1)[1].split("```", 1)[0].strip()
            elif "```" in content:
                content = content.split("```", 1)[1].split("```", 1)[0].strip()
            match = re.search(r"\[[\s\S]*\]", content)
            if not match:
                return []
            data = json.loads(match.group(0))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _log_search_results(self, source: str, query: str, results: list):
        print(f"      🔎 [{source}] Query: '{query}' | Found: {len(results)} results")
        for i, res in enumerate(results[:3]):
            title = res.get("title", "No Title")
            url = res.get("href", "No URL")
            print(f"         {i+1}. {title} ({url})")

    def _search(self, query: str, limit: int = 5) -> list:
        if self.google_api_key and self.google_cx:
            print(f"      🔎 Google Search: {query}")
            return self._search_google(query, limit)
        return self._search_ddg(query, limit)

    def _search_google(self, query: str, limit: int = 5) -> list:
        results = []
        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": self.google_api_key,
                "cx": self.google_cx,
                "q": query,
                "num": limit,
                "lr": "lang_ja" if self.lang == "ja" else "lang_en",
            }
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            if "items" in data:
                for item in data["items"]:
                    results.append({
                        "title": item.get("title", ""),
                        "href": item.get("link", ""),
                        "body": item.get("snippet", ""),
                    })
        except Exception as e:
            print(f"⚠️ Google Search failed for '{query}': {e}")
            return self._search_ddg(query, limit)

        ranked = self._rank_results(results)
        self._log_search_results("Google", query, ranked)
        return ranked

    def _search_ddg(self, query: str, limit: int = 5) -> list:
        results = []
        try:
            region = "jp-jp" if self.lang == "ja" else "us-en"
            with DDGS() as ddgs:
                raw_res = ddgs.text(query, region=region, max_results=limit * 2)
                if raw_res:
                    for item in raw_res:
                        results.append({
                            "title": item.get("title", ""),
                            "href": item.get("href", item.get("url", "")),
                            "body": item.get("body", item.get("snippet", "")),
                        })
        except Exception as e:
            print(f"⚠️ DDG Search failed for '{query}': {e}")

        ranked = self._rank_results(results)[:limit]
        self._log_search_results("DuckDuckGo", query, ranked)
        return ranked

    def _domain_score(self, url: str) -> int:
        host = urlparse(url).netloc.lower()
        if not host:
            return -10
        if any(blocked in host for blocked in BLOCKED_DOMAINS):
            return -100
        score = 0
        for idx, domain in enumerate(PREFERRED_DOMAINS):
            if domain in host:
                score += 30 - idx
        if host.endswith(".gov") or ".gov." in host:
            score += 20
        if host.endswith(".edu") or ".edu." in host:
            score += 15
        if host.endswith(".ac.jp"):
            score += 15
        if host.endswith(".org"):
            score += 6
        return score

    def _rank_results(self, results: list) -> list:
        unique = []
        seen = set()
        for result in results:
            url = result.get("href", "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            if self._domain_score(url) <= -100:
                continue
            unique.append(result)
        unique.sort(
            key=lambda item: (self._domain_score(item.get("href", "")), len(item.get("body", ""))),
            reverse=True,
        )
        return unique

    def _process_results(self, raw_results: list) -> str:
        seen_urls = set()
        formatted_chunks = []
        idx = 1
        for res in self._rank_results(raw_results):
            url = res.get("href", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)
            title = res.get("title", "No Title")
            body = res.get("body", "")
            score = self._domain_score(url)
            formatted_chunks.append(
                f"[Source {idx}]\nTitle: {title}\nURL: {url}\nReliabilityScore: {score}\nContent: {body}\n"
            )
            idx += 1
            if idx > 25:
                break
        return "\n".join(formatted_chunks)

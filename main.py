# main.py
import os
import asyncio
import requests
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP, Context
from dotenv import load_dotenv

load_dotenv()

# 환경변수 읽기
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

mcp = FastMCP("news_summarizer")
print("NAVER_CLIENT_ID:", NAVER_CLIENT_ID)
print("NAVER_CLIENT_SECRET:", NAVER_CLIENT_SECRET)

# 콘솔에 환경변수 출력이 None으로 나온다면 .env 파일을 생성해 환경변수 등록하기
async def fetch_article_links(keyword: str) -> list[str]:
    """네이버 뉴스 검색 API로 5개 링크를 가져옴."""
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {"query": keyword, "display": 5, "sort": "date"}
    # requests 는 동기이므로 스레드에서 실행
    resp = await asyncio.to_thread(requests.get, url, headers=headers, params=params)
    items = resp.json().get("items", [])
    return [item["link"] for item in items]

async def extract_article_text(url: str) -> str:
    """기사 URL에서 id=newsct_article 본문 텍스트만 뽑아옴."""
    resp = await asyncio.to_thread(requests.get, url)
    soup = BeautifulSoup(resp.text, "html.parser")
    body = soup.find("div", id="newsct_article")
    return body.get_text("\n", strip=True) if body else ""

def simple_summary(text: str, num_sentences: int) -> str:
    """마침표 기준으로 앞 num_sentences문장 반환."""
    # 너무 길면 줄바꿈 추가
    sents = [s.strip() for s in text.split("।")]  # 한국어 마침표 대체
    if len(sents) < num_sentences:
        sents = [s for s in text.split(".") if s]
    return ". ".join(sents[:num_sentences]).strip() + "."

def extract_keywords(text: str, top_n: int = 5) -> list[str]:
    """단어 빈도 기반 상위 top_n 키워드 추출 (영/한 혼합 간단 처리)."""
    words = [
        w.lower()
        for w in text.replace("\n", " ").split()
        if len(w) > 1 and w.isalpha()
    ]
    freq: dict[str,int] = {}
    stopwords = {"그리고","하지만","그러나","이는","있다","하다","수","것","등"}
    for w in words:
        if w in stopwords:
            continue
        freq[w] = freq.get(w, 0) + 1
    # 빈도 내림차순 상위 추출
    return sorted(freq, key=lambda w: freq[w], reverse=True)[:top_n]

@mcp.tool()
async def summarize_news(keyword: str, ctx: Context) -> dict:
    """
    1) 키워드로 뉴스 5건 링크 수집
    2) 본문(id=newsct_article)만 추출
    3) 각 기사별 3~4문장 요약
    4) 전체 종합 5~6문장 요약 + 주요 키워드 3~5개
    """
    await ctx.info(f"Searching articles for '{keyword}'")
    links = await fetch_article_links(keyword)
    texts = []
    for url in links:
        txt = await extract_article_text(url)
        if txt:
            texts.append(txt)
    if not texts:
        return {"error": "본문을 찾을 수 없습니다."}

    # 각 기사별 요약 (3문장)
    per_article = [simple_summary(t, 3) for t in texts]

    # 전체 종합 요약 (5문장)
    combined = "\n".join(texts)
    overall = simple_summary(combined, 5)

    # 키워드 추출
    keywords = extract_keywords(combined, top_n=5)

    return {
        "per_article_summaries": per_article,
        "overall_summary": overall,
        "keywords": keywords,
    }

if __name__ == "__main__":
    mcp.run()

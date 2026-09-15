import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed


# ============================================================
# Google News 감시 대상
# ============================================================

NEWS_QUERIES = {
    "Donald Trump": '"Donald Trump" AI semiconductor',
    "Elon Musk": '"Elon Musk" AI semiconductor',
    "Jensen Huang": '"Jensen Huang" NVIDIA AI',
    "Sam Altman": '"Sam Altman" OpenAI AI',
    "Jerome Powell": '"Jerome Powell" interest rate',
    "Federal Reserve": '"Federal Reserve" interest rate AI',
    "US Treasury": '"US Treasury" semiconductor AI',
    "NVIDIA": 'NVIDIA AI GPU',
    "AMD": 'AMD AI semiconductor',
    "TSMC": 'TSMC AI semiconductor',
    "SK hynix": '"SK hynix" AI semiconductor',
    "Samsung Electronics": '"Samsung Electronics" AI semiconductor',
    "Micron": 'Micron AI semiconductor',
}


GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"


# ============================================================
# Google News RSS 조회
# ============================================================

def get_google_news(query, limit=10):
    url = GOOGLE_NEWS_RSS.format(query=quote(query))

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=12,
        )

        if response.status_code != 200:
            print(f"❌ Google News 조회 실패: HTTP {response.status_code}")
            return []

        root = ET.fromstring(response.content)

        articles = []

        for item in root.findall("./channel/item")[:limit]:
            title = item.findtext("title", default="")
            link = item.findtext("link", default="")
            pub_date = item.findtext("pubDate", default="")
            source = item.findtext("source", default="")

            published_at = pub_date

            if pub_date:
                try:
                    dt = parsedate_to_datetime(pub_date)
                    # Google News RSS의 원본 timezone을 한국시간(KST, UTC+9)으로 통일
                    dt = dt.astimezone(ZoneInfo("Asia/Seoul"))
                    published_at = dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    pass

            articles.append(
                {
                    "title": title,
                    "source": source,
                    "published_at": published_at,
                    "link": link,
                    "query": query,
                }
            )

        return articles

    except Exception as e:
        print("❌ Google News 조회 오류:", e)
        return []


# ============================================================
# 전체 감시 대상 뉴스 조회
# ============================================================

STOCK_KEYWORDS = {
    "NVDA": [
        "NVIDIA",
        "Nvidia",
        "엔비디아",
    ],
    "AMD": [
        "AMD",
        "Advanced Micro Devices",
    ],
    "INTC": [
        "Intel",
        "인텔",
    ],
    "SNDK": [
        "SanDisk",
        "샌디스크",
    ],
    "MU": [
        "Micron",
        "Micron Technology",
        "마이크론",
    ],
    "000660": [
        "SK hynix",
        "SK Hynix",
        "SK하이닉스",
    ],
    "005930": [
        "Samsung Electronics",
        "Samsung",
        "삼성전자",
    ],
}


# ============================================================
# 뉴스 중복 제거
# ============================================================

def remove_duplicate_news(news_list):
    unique_news = []
    seen = set()

    for article in news_list:
        title = article.get("title", "").strip()

        if not title:
            continue

        # 제목을 기준으로 중복 제거
        key = title.lower()

        if key in seen:
            continue

        seen.add(key)
        unique_news.append(article)

    return unique_news


# ============================================================
# 뉴스 관련 종목 찾기
# ============================================================

def find_related_symbols(article):
    title = article.get("title", "")
    query = article.get("query", "")

    text = f"{title} {query}".lower()

    related_symbols = []

    for symbol, keywords in STOCK_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in text:
                related_symbols.append(symbol)
                break

    return related_symbols


# ============================================================
# 전체 감시 대상 뉴스 조회
# ============================================================

def _collect_one_news_query(speaker, query, limit_per_query):
    try:
        articles = get_google_news(query=query, limit=limit_per_query)
        for article in articles:
            article["speaker"] = speaker
            article["related_symbols"] = find_related_symbols(article)
        return articles
    except Exception:
        return []


def collect_news(limit_per_query=5):
    """Google News RSS 병렬 수집 + 전체 실패 시 간단 검색 재시도."""
    all_news = []
    with ThreadPoolExecutor(max_workers=min(8, len(NEWS_QUERIES))) as pool:
        futures = {pool.submit(_collect_one_news_query, speaker, query, limit_per_query): speaker for speaker, query in NEWS_QUERIES.items()}
        for future in as_completed(futures):
            try:
                all_news.extend(future.result() or [])
            except Exception:
                pass

    if not all_news:
        fallback_queries = {"NVIDIA": "NVIDIA AI GPU", "AMD": "AMD AI semiconductor", "TSMC": "TSMC AI semiconductor"}
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(_collect_one_news_query, speaker, query, limit_per_query): speaker for speaker, query in fallback_queries.items()}
            for future in as_completed(futures):
                try:
                    all_news.extend(future.result() or [])
                except Exception:
                    pass

    unique_news = remove_duplicate_news(all_news)
    unique_news.sort(key=lambda x: str(x.get("published_at", "")), reverse=True)
    return unique_news


# ============================================================
# 테스트
# ============================================================

if __name__ == "__main__":
    print("📰 AlphaMindStock News Collector")
    print("=" * 80)

    news = collect_news(limit_per_query=3)

    print()
    print(f"수집 후 뉴스: {len(news)}건")
    print("=" * 80)

    for i, article in enumerate(news, start=1):
        print()
        print(f"[{i}] {article['speaker']}")
        print(f"원천       : {article['source']}")
        print(f"시간       : {article['published_at']}")
        print(f"관련종목   : {', '.join(article['related_symbols']) or '없음'}")
        print(f"제목       : {article['title']}")
        print(f"링크       : {article['link']}")
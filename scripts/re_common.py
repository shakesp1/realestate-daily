"""
여러 수집 스크립트가 공유하는 유틸리티 함수 모음.
네이버 뉴스 검색 API + 구글 뉴스 검색 RSS + 스타트업/부동산 매체 RSS를 통해
뉴스 후보를 모으는 공통 로직을 담당한다.
"""

import os
import re
import html
import time
import datetime
import urllib.parse
import requests
import feedparser

NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET")


def clean_text(raw: str) -> str:
    text = re.sub(r"<[^>]+>", "", raw or "")
    return html.unescape(text).strip()


def search_naver_news(query: str) -> list:
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {"query": query, "display": 100, "sort": "date"}
    resp = requests.get(url, headers=headers, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json().get("items", [])


def parse_naver_pubdate(pubdate_str: str) -> datetime.datetime:
    return datetime.datetime.strptime(pubdate_str, "%a, %d %b %Y %H:%M:%S %z")


def _within_cutoff(pub: datetime.datetime, cutoff: datetime.datetime) -> bool:
    if pub.tzinfo is None:
        pub = pub.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=9)))
    return pub >= cutoff


def collect_from_naver(keywords: list, cutoff: datetime.datetime) -> list:
    collected = []
    for kw in keywords:
        try:
            items = search_naver_news(kw)
        except requests.HTTPError as e:
            print(f"[경고] 네이버 '{kw}' 검색 실패: {e}")
            continue
        for item in items:
            link = item.get("originallink") or item.get("link")
            if not link:
                continue
            try:
                pub = parse_naver_pubdate(item.get("pubDate", ""))
            except ValueError:
                continue
            if not _within_cutoff(pub, cutoff):
                continue
            collected.append(
                {
                    "title": clean_text(item.get("title", "")),
                    "description": clean_text(item.get("description", "")),
                    "link": link,
                    "pub_date": pub.strftime("%Y-%m-%d"),
                }
            )
        time.sleep(0.2)
    print(f"[정보] 네이버 뉴스에서 후보 {len(collected)}건")
    return collected


def _collect_from_feed_entries(entries, cutoff) -> list:
    collected = []
    for entry in entries:
        link = entry.get("link")
        if not link or not entry.get("published_parsed"):
            continue
        pub = datetime.datetime(*entry.published_parsed[:6], tzinfo=datetime.timezone.utc).astimezone(
            datetime.timezone(datetime.timedelta(hours=9))
        )
        if not _within_cutoff(pub, cutoff):
            continue
        collected.append(
            {
                "title": clean_text(entry.get("title", "")),
                "description": clean_text(entry.get("summary", "")),
                "link": link,
                "pub_date": pub.strftime("%Y-%m-%d"),
            }
        )
    return collected


def collect_from_rss_feeds(feed_urls: list, cutoff: datetime.datetime) -> list:
    collected = []
    for url in feed_urls:
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"[경고] RSS 수집 실패 ({url}): {e}")
            continue
        collected += _collect_from_feed_entries(feed.entries, cutoff)
    print(f"[정보] RSS 피드에서 후보 {len(collected)}건")
    return collected


def collect_from_google_news(queries: list, cutoff: datetime.datetime) -> list:
    collected = []
    for query in queries:
        encoded = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"[경고] 구글 뉴스 검색 실패 ('{query}'): {e}")
            continue
        collected += _collect_from_feed_entries(feed.entries, cutoff)
        time.sleep(0.2)
    print(f"[정보] 구글 뉴스 검색에서 후보 {len(collected)}건")
    return collected


def collect_raw_news(naver_keywords, google_queries, rss_feeds, lookback_days) -> list:
    cutoff = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))) - datetime.timedelta(
        days=lookback_days
    )
    all_items = []
    if naver_keywords:
        all_items += collect_from_naver(naver_keywords, cutoff)
    if rss_feeds:
        all_items += collect_from_rss_feeds(rss_feeds, cutoff)
    if google_queries:
        all_items += collect_from_google_news(google_queries, cutoff)

    seen_links = set()
    deduped = []
    for item in all_items:
        if item["link"] in seen_links:
            continue
        seen_links.add(item["link"])
        deduped.append(item)

    print(f"[정보] 전체 소스 합산 후 중복 제거된 후보 뉴스: {len(deduped)}건")
    return deduped


def build_summary(title: str, description: str) -> str:
    text = description if description else title
    if len(text) > 140:
        text = text[:140].rsplit(" ", 1)[0] + "…"
    return text


REGION_PATTERN = re.compile(
    r"([가-힣]{2,10}(?:특별자치시|특별자치도|광역시|특별시|도|시|군|구|동|읍|면))(?![가-힣])"
)

# 지명이 아닌데 지역 접미사로 끝나서 오탐되기 쉬운 일반 명사들
REGION_BLOCKLIST = {"신도시", "구도심", "신시가지", "도시", "광역시", "관리처분구역", "정비구역"}

# "서울"처럼 접미사(시/도) 없이 단독으로 쓰이는 광역시 이름
STANDALONE_CITY_NAMES = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종"]


def extract_region(text: str):
    for m in REGION_PATTERN.finditer(text):
        candidate = m.group(1)
        if candidate in REGION_BLOCKLIST:
            continue
        return candidate

    for city in STANDALONE_CITY_NAMES:
        pattern = r"(?<![가-힣])" + city + r"(?![가-힣])"
        if re.search(pattern, text):
            return city

    return None


def check_required_env():
    missing = [
        name
        for name, val in [
            ("NAVER_CLIENT_ID", NAVER_CLIENT_ID),
            ("NAVER_CLIENT_SECRET", NAVER_CLIENT_SECRET),
        ]
        if not val
    ]
    if missing:
        raise SystemExit(f"환경변수가 설정되지 않았습니다: {', '.join(missing)}")

"""
부동산 정책 동향 수집 스크립트

"정책 동향 요약" 탭과 "정책(대출규제·법개정 등)" 탭은 같은 데이터를 공유한다.
각 기사에 카테고리를 붙여서, 프론트엔드에서
- 전체 보기 = 정책 동향 요약
- 대출규제/법개정/세제만 필터링 = 특정 정책 탭
으로 나눠서 보여준다.

필요한 환경변수: NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
"""

import os
import json
import datetime
import re_common as common

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "data", "policy.json")
LOOKBACK_DAYS = 2  # 매일 실행되므로 짧게, 실행이 하루 밀려도 놓치지 않도록 약간 여유

NAVER_KEYWORDS = [
    "부동산 정책",
    "부동산 대책",
    "주택 공급대책",
    "대출규제 부동산",
    "종부세 개정",
    "양도세 개정",
    "분양가상한제",
    "재건축초과이익환수",
]

GOOGLE_QUERIES = [
    "부동산 정책 발표",
    "부동산 대출규제",
    "부동산 법 개정",
    "주택 공급대책",
]

RSS_FEEDS = []  # 부동산 전문 매체 RSS를 찾으면 여기에 추가 가능

CATEGORY_KEYWORDS = [
    ("대출규제", ["대출규제", "LTV", "DSR", "DTI", "대출한도", "주택담보대출", "특례보금자리론", "디딤돌대출", "정책모기지"]),
    ("법개정", ["법개정", "시행령", "개정안", "국회 통과", "입법예고", "법안", "국토계획법"]),
    ("세제", ["종부세", "양도세", "취득세", "보유세", "세제개편", "공시가격"]),
    ("공급대책", ["공급대책", "공급확대", "분양가상한제", "재건축초과이익", "3기 신도시", "공공주택"]),
]


def extract_category(text: str) -> str:
    for label, keywords in CATEGORY_KEYWORDS:
        for kw in keywords:
            if kw in text:
                return label
    return "기타정책"


def process_news(raw_news: list) -> list:
    results = []
    for item in raw_news:
        combined = f"{item['title']} {item['description']}"
        results.append(
            {
                "category": extract_category(combined),
                "title": item["title"],
                "summary": common.build_summary(item["title"], item["description"]),
                "source_url": item["link"],
                "pub_date": item["pub_date"],
            }
        )
    return results


def load_existing() -> list:
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def dedup_key(entry: dict) -> str:
    return entry["source_url"]


def main():
    common.check_required_env()

    raw_news = common.collect_raw_news(NAVER_KEYWORDS, GOOGLE_QUERIES, RSS_FEEDS, LOOKBACK_DAYS)
    extracted = process_news(raw_news)
    print(f"[정보] 정책 뉴스 추출: {len(extracted)}건")

    existing = load_existing()
    existing_keys = {dedup_key(e) for e in existing}

    new_entries = [e for e in extracted if dedup_key(e) not in existing_keys]
    print(f"[정보] 신규 항목 (중복 제외): {len(new_entries)}")

    combined = existing + new_entries
    combined.sort(key=lambda e: e["pub_date"], reverse=True)

    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)

    print(f"[완료] 총 {len(combined)}건 저장 -> {DATA_PATH}")


if __name__ == "__main__":
    main()

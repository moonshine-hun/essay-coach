import html
import re
import requests
import xml.etree.ElementTree as ET

_HEADERS = {"User-Agent": "Mozilla/5.0"}

_QUERIES = {
    "it": "IT OR 인공지능 OR 반도체 OR 빅데이터",
    "sisa": "시사 OR 정책 OR 경제",
}


def _strip_html(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", text or "")).strip()


def fetch_news(category: str = "it", count: int = 8) -> list[dict]:
    """Google 뉴스 RSS 검색 결과에서 IT/시사 헤드라인을 가져온다."""
    query = _QUERIES.get(category, _QUERIES["it"])
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        r = requests.get(url, headers=_HEADERS, timeout=10)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception:
        return []

    items = []
    for item in root.findall(".//item")[: count * 2]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        desc = _strip_html(item.findtext("description") or "")
        source_el = item.find("source")
        source = source_el.text.strip() if source_el is not None and source_el.text else ""
        if not title:
            continue
        items.append({
            "title": title,
            "link": link,
            "pub_date": pub_date,
            "description": desc,
            "source": source,
        })
        if len(items) >= count:
            break
    return items

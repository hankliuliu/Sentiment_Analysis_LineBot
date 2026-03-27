import requests
import time
from bs4 import BeautifulSoup
from config import SOURCES, MAX_ITEMS_PER_SOURCE
from database import get_cached_content


def _strip_html(text: str) -> str:
    """移除 HTML 標籤，只留純文字。"""
    return BeautifulSoup(text, "html.parser").get_text(strip=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

def fetch_yahoo_news():
    print("  [Yahoo] 正在抓取...")
    url = "https://tw.news.yahoo.com/rss"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.content, "xml")
        articles = []
        for item in soup.find_all("item")[:MAX_ITEMS_PER_SOURCE]:
            title = item.find("title")
            link  = item.find("link")
            pub   = item.find("pubDate")
            desc  = item.find("description")
            if title and link:
                articles.append({
                    "source":      "Yahoo新聞",
                    "title":       title.text.strip(),
                    "url":         link.text.strip() if link.text else "",
                    "time":        pub.text.strip() if pub else "",
                    "description": desc.text.strip() if desc else "",
                    "content":     ""
                })
        print(f"  [Yahoo] 抓到 {len(articles)} 筆")
        return articles
    except Exception as e:
        print(f"  [Yahoo] 失敗：{e}")
        return []


def fetch_udn_news():
    print("  [聯合新聞] 正在抓取...")
    url = "https://udn.com/rssfeed/news/2/6638?ch=news"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.content, "xml")
        articles = []
        for item in soup.find_all("item")[:MAX_ITEMS_PER_SOURCE]:
            title = item.find("title")
            link  = item.find("link")
            pub   = item.find("pubDate")
            if title and link:
                articles.append({
                    "source":      "聯合新聞網",
                    "title":       title.text.strip(),
                    "url":         link.text.strip() if link.text else "",
                    "time":        pub.text.strip() if pub else "",
                    "description": "",   # UDN RSS 無提供摘要
                    "content":     ""
                })
        print(f"  [聯合新聞] 抓到 {len(articles)} 筆")
        return articles
    except Exception as e:
        print(f"  [聯合新聞] 失敗：{e}")
        return []


def fetch_ltn_news():
    print("  [自由時報] 正在抓取...")
    url = "https://news.ltn.com.tw/rss/all.xml"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.content, "xml")
        articles = []
        for item in soup.find_all("item")[:MAX_ITEMS_PER_SOURCE]:
            title = item.find("title")
            link  = item.find("link")
            pub   = item.find("pubDate")
            desc  = item.find("description")
            if title and link:
                articles.append({
                    "source":      "自由時報",
                    "title":       title.text.strip(),
                    "url":         link.text.strip() if link.text else "",
                    "time":        pub.text.strip() if pub else "",
                    "description": desc.text.strip() if desc else "",
                    "content":     ""
                })
        print(f"  [自由時報] 抓到 {len(articles)} 筆")
        return articles
    except Exception as e:
        print(f"  [自由時報] 失敗：{e}")
        return []


def fetch_google_news_tw():
    print("  [Google新聞] 正在抓取...")
    url = "https://news.google.com/rss?hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.content, "xml")
        articles = []
        for item in soup.find_all("item")[:MAX_ITEMS_PER_SOURCE]:
            title = item.find("title")
            link  = item.find("link")
            pub   = item.find("pubDate")
            if title and link:
                articles.append({
                    "source":      "Google新聞",
                    "title":       title.text.strip(),
                    "url":         link.text.strip() if link.text else "",
                    "time":        pub.text.strip() if pub else "",
                    "description": "",   # Google RSS description 為 HTML 連結，無摘要文字
                    "content":     ""
                })
        print(f"  [Google新聞] 抓到 {len(articles)} 筆")
        return articles
    except Exception as e:
        print(f"  [Google新聞] 失敗：{e}")
        return []


def fetch_ettoday_news():
    print("  [ETtoday] 正在抓取...")
    url = "https://feeds.feedburner.com/ettoday/realtime"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.content, "xml")
        articles = []
        for item in soup.find_all("item")[:MAX_ITEMS_PER_SOURCE]:
            title = item.find("title")
            link  = item.find("link")
            pub   = item.find("pubDate")
            desc  = item.find("description")
            if title and link:
                articles.append({
                    "source":      "ETtoday",
                    "title":       title.text.strip(),
                    "url":         link.text.strip() if link.text else "",
                    "time":        pub.text.strip() if pub else "",
                    "description": _strip_html(desc.text) if desc else "",  # 含 HTML，需清理
                    "content":     ""
                })
        print(f"  [ETtoday] 抓到 {len(articles)} 筆")
        return articles
    except Exception as e:
        print(f"  [ETtoday] 失敗：{e}")
        return []


def fetch_pts_news():
    print("  [公視] 正在抓取...")
    url = "https://news.pts.org.tw/xml/newsfeed.xml"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.content, "xml")
        articles = []
        # 公視使用 Atom 格式：<entry> 而非 <item>，<link href="..."> 而非 <link>文字
        for entry in soup.find_all("entry")[:MAX_ITEMS_PER_SOURCE]:
            title   = entry.find("title")
            link    = entry.find("link")
            updated = entry.find("updated")
            summary = entry.find("summary")
            if title and link:
                articles.append({
                    "source":      "公視新聞",
                    "title":       title.text.strip(),
                    "url":         link.get("href", ""),
                    "time":        updated.text.strip() if updated else "",
                    "description": summary.text.strip() if summary else "",
                    "content":     ""
                })
        print(f"  [公視] 抓到 {len(articles)} 筆")
        return articles
    except Exception as e:
        print(f"  [公視] 失敗：{e}")
        return []


def fetch_article_content(url):
    """
    進入單篇文章頁面，抓取內文純文字。
    策略：找頁面裡最長的 <p> 段落集合，通常就是內文。
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        # 移除導覽列、廣告、頁尾等雜訊
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        # 收集所有 <p> 段落，過濾太短的（通常是按鈕文字或說明）
        paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]
        paragraphs = [p for p in paragraphs if len(p) > 20]

        content = "\n".join(paragraphs)

        # 限制長度，避免單篇文章 token 過多（約 1000 字）
        return content[:3000] if content else ""

    except Exception as e:
        print(f"    [內文] 抓取失敗 {url[:50]}... ：{e}")
        return ""


def fetch_contents_for_selected(articles):
    """
    針對 Gemini 第一次篩選出的重要文章，逐一抓取內文。
    每篇之間間隔 1 秒，避免請求太頻繁被封鎖。
    """
    print(f"\n[Fetcher] 開始抓取 {len(articles)} 篇重要文章的內文...")
    for i, article in enumerate(articles):
        cached = get_cached_content(article["url"])
        if cached:
            article["content"] = cached
            print(f"  [{i+1}/{len(articles)}] {article['title'][:30]}... (快取)")
            continue
        print(f"  [{i+1}/{len(articles)}] {article['title'][:30]}...")
        article["content"] = fetch_article_content(article["url"])
        time.sleep(1)   # 禮貌性間隔，避免被封鎖
    print("[Fetcher] 內文抓取完成")
    return articles


def fetch_all():
    print("[Fetcher] 開始抓取新聞標題...")
    all_articles = []
    if SOURCES.get("yahoo"):    all_articles += fetch_yahoo_news()
    if SOURCES.get("udn"):      all_articles += fetch_udn_news()
    if SOURCES.get("ltn"):      all_articles += fetch_ltn_news()
    if SOURCES.get("google"):   all_articles += fetch_google_news_tw()
    if SOURCES.get("ettoday"):  all_articles += fetch_ettoday_news()
    if SOURCES.get("pts"):      all_articles += fetch_pts_news()
    print(f"[Fetcher] 共抓到 {len(all_articles)} 筆原始資料")
    return all_articles
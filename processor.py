from datetime import datetime, timezone, timedelta
from config import DATE_FILTER
import email.utils

def is_within_date_range(time_str):
    """
    根據 config 的 DATE_FILTER 決定是否保留這篇文章：
      "today" → 只保留今天
      "2days" → 保留今天和昨天
      "all"   → 全部保留
    """
    if DATE_FILTER == "all":
        return True

    if not time_str:
        return True  # 沒有時間欄位就保留，寧可多不要少

    try:
        parsed  = email.utils.parsedate_to_datetime(time_str)
        now     = datetime.now(timezone.utc).astimezone()
        article_date = parsed.astimezone().date()

        # 日期不合理（早於 2020）→ 來源未正確填寫時間，直接保留
        if article_date.year < 2020:
            return True
        # 聯合新聞都用假的預設值代替 OuO

        if DATE_FILTER == "today":
            return article_date == now.date()

        if DATE_FILTER == "2days":
            yesterday = (now - timedelta(days=1)).date()
            return article_date >= yesterday

    except Exception:
        return True  # 解析失敗就保留

    return True


def deduplicate(articles):
    seen   = set()
    unique = []
    for article in articles:
        fingerprint = article["title"][:10]
        if fingerprint not in seen:
            seen.add(fingerprint)
            unique.append(article)
    return unique


def process(articles):
    print("\n[Processor] 開始整理資料...")

    # 步驟1：日期過濾
    before   = len(articles)
    articles = [a for a in articles if is_within_date_range(a["time"])]
    print(f"  日期過濾（{DATE_FILTER}）：{before} 筆 → {len(articles)} 筆")

    # 步驟2：去重
    before   = len(articles)
    articles = deduplicate(articles)
    print(f"  去重：{before} 筆 → {len(articles)} 筆")

    # 步驟3：過濾太短的標題
    before   = len(articles)
    articles = [a for a in articles if len(a["title"]) > 5]
    print(f"  過濾短標題：{before} 筆 → {len(articles)} 筆")
    print(f"[Processor] 整理後剩下 {len(articles)} 筆資料")

    return articles
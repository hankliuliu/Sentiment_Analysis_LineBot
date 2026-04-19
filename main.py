import os
import openai
import schedule
import time as time_module
from config    import (API_KEY, MODEL, MAX_ARTICLES_TO_ANALYZE, TEST_FETCH,
                       SCHEDULER_ENABLED, SCHEDULER_TIMES, IMPORTANT_COUNT, BASE_URL)
from fetcher   import fetch_all, fetch_contents_for_selected
from processor import process
from database  import init_db, save_articles, save_report, save_article_embeddings, save_report_embedding
from embedder  import embed_passages
from line_push import push_message, format_report_for_line
from datetime  import datetime
import json

client = openai.OpenAI(api_key=API_KEY, base_url=BASE_URL)

def select_important(articles):
    """
    Gemini 第一次：從標題中挑出 5-8 篇最重要的文章。
    要求 Gemini 回傳 JSON，方便程式解析。
    """
    print("\n[Gemini] 篩選重要文章...")

    news_list = ""
    for i, a in enumerate(articles[:]): # :MAX_ARTICLES_TO_ANALYZE
        desc = a.get("description", "").strip()
        news_list += f"{i}. 【{a['source']}】{a['title']}\n"
        if desc:
            news_list += f"   摘要：{desc[:100]}\n"

    prompt = f"""
以下是今日台灣各大媒體的新聞標題清單（含編號）：

{news_list}

請站在政府高層幕僚的角度，從中挑選出 {IMPORTANT_COUNT} 篇最值得關注的新聞。
判斷標準：涉及政策制定或執行、可能形成輿論壓力、影響政府施政形象、具跨部會或跨層級影響、或可能引發後續政治效應。
來源多元性：盡量涵蓋不同媒體來源，避免選出的文章集中在同一家媒體。

請只回傳一個 JSON 陣列，內容是你選出的文章編號，不要有其他文字。
範例格式：[0, 3, 7, 12, 15]
"""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    # 解析 Gemini 回傳的 JSON 編號清單
    try:
        text    = response.choices[0].message.content.strip()
        # 去除可能多餘的 markdown 標記
        text    = text.replace("```json", "").replace("```", "").strip()
        indices = json.loads(text)
        selected = [articles[i] for i in indices if i < len(articles)]
        print(f"[Gemini] 選出 {len(selected)} 篇重要文章")
        return selected
    except Exception as e:
        print(f"[Gemini] 解析失敗：{e}，改用前5篇")
        return articles[:5]   # 解析失敗就直接取前5篇當備案


def analyze_in_depth(articles):
    """
    Gemini 第二次：根據完整內文做深度分析，產出最終報告。
    """
    print("\n[Gemini] 深度分析，產出報告...")

    news_text = ""
    for a in articles:
        news_text += f"""
【{a['source']}】{a['title']}
{a['content'] if a['content'] else '（內文無法取得）'}
---
"""

    today_str = datetime.now().strftime("%m/%d")
    prompt = f"""
你是一位服務於政府高層的資深輿情幕僚，每日為長官提供新聞情勢簡報。
以下是今日（{today_str}）最重要的幾篇新聞，包含標題與內文：

{news_text}

請完成以下任務，用繁體中文回答：

1. 今日重點情勢：挑出三則最重要的新聞，每則用 3-4 句話說明：事件內容、對政府施政或社會穩定的潛在影響、以及需注意的風險或機會。

2. 民意與輿論動向：這些新聞反映了哪些民心趨勢或社會壓力？政府應如何解讀與因應？

3. 一句話情勢研判：用一句話總結今日整體情勢對執政環境的意義。

4. 其他需掌握的動態：列出五則其他新聞，每則一句話說明其政策或治理上的關聯性。

開場白：「您好，以下是今日（{today_str}）情勢簡報：」。
語氣專業、客觀、精準，著重政策影響與治理視角，不需要口語化。
格式不用 Markdown，一般訊息格式。
問題以 1.2.3.4. 標示，新聞項目符號使用「🔸 」，第 4 點使用「🔹 」。
"""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )
    return response.choices[0].message.content


def save_txt_report(report_text):
    reports_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    today    = datetime.now().strftime("%Y-%m-%d_%H%M")
    filename = os.path.join(reports_dir, f"{today}.txt")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"\n[Output] 報告已儲存為：{today}.txt")


def agent():
    print("=" * 50)
    print(f"  輿情監控系統啟動")
    print(f"  時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    # Step 1：抓標題
    raw_articles   = fetch_all()

    # Step 2：整理去重
    clean_articles = process(raw_articles)
    if not clean_articles:
        print("\n[ ! Warning ! ] 沒有抓到任何新聞。")
        return

    # 測試抓資料
    if TEST_FETCH:
        return

    # Step 3：Gemini 第一次篩選重要標題
    important_articles = select_important(clean_articles)

    # Step 4：抓重要文章的內文
    important_articles = fetch_contents_for_selected(important_articles)

    # Step 5：存入資料庫（含內文）+ 向量化
    save_articles(important_articles)
    texts = [f"{a['title']}\n{a['content']}" for a in important_articles]
    save_article_embeddings(important_articles, embed_passages(texts))

    # Step 6：Gemini 第二次深度分析
    report = analyze_in_depth(important_articles)

    # Step 7：輸出
    print("\n" + "=" * 50)
    print("【今日輿情摘要】")
    print("=" * 50)
    print(report)

    save_txt_report(report)
    save_report(report, report_type="daily")
    save_report_embedding(datetime.now().strftime("%Y-%m-%d"), report, embed_passages([report])[0])

    formatted = format_report_for_line(report)
    push_message(formatted)


if __name__ == "__main__":
    init_db()

    if not SCHEDULER_ENABLED:
        print("[排程器] 已關閉，直接執行一次")
        agent()
    else:
        print(f"[排程器] 已開啟，排定執行時間：{SCHEDULER_TIMES}")
        print("[排程器] 程式持續運行中，按 Ctrl+C 可停止\n")
        for t in SCHEDULER_TIMES:
            schedule.every().day.at(t).do(agent)
        # print("[排程器] 啟動時先執行一次...")
        # agent()
        while True:
            schedule.run_pending()
            time_module.sleep(30)
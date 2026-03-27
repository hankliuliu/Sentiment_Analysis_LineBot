"""
weekly.py — 每週輿情週報產生器

用法：
  python weekly.py

Windows 排程器設定：
  每週固定時間執行此檔案即可，與 main.py 完全獨立。
"""

import openai
from datetime import datetime

from config    import API_KEY, MODEL, BASE_URL
from database  import (init_db, save_report, save_report_embedding,
                       get_recent_daily_reports)
from embedder  import embed_passages
from line_push import push_message, format_report_for_line

client = openai.OpenAI(api_key=API_KEY, base_url=BASE_URL)


def analyze_weekly(daily_reports: list[dict]) -> str:
    """
    根據最近 7 份每日報告，請 Gemini 產出一份週度綜合分析。
    daily_reports: list of {"created_at": str, "content": str}
    """
    # 由舊到新排列，讓 AI 感受時序
    reports_text = ""
    for r in reversed(daily_reports):
        reports_text += f"\n【{r['created_at'][:10]}】\n{r['content']}\n---\n"

    prompt = f"""
你是一位專業的台灣媒體輿情分析師。
以下是本週共 {len(daily_reports)} 份每日新聞摘要報告（資料不足 7 天時請根據現有資料分析即可）：

{reports_text}

請根據以上資料完成本週週報，用繁體中文回答：

1. 本週最重要的三大議題：各用 3-4 句話說明事件發展脈絡與重要性。

2. 本週輿論趨勢：這一週的新聞整體反映了什麼社會氛圍或政治走向？

3. 一句話總結本週：用一句話概括本週台灣新聞的核心主軸。

4. 值得持續追蹤：列出 3 個下週應持續關注的議題，各用一句話說明原因。

開場白範例：「您好，以下是本週（{datetime.now().strftime('%m/%d')} 週）的輿情週報：」
格式同每日報告：不用 Markdown，一般訊息格式。
問題以 1.2.3.4. 標示，議題項目符號使用「🔸 」，第 4 點使用「🔹 」。
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


def weekly_agent():
    """
    週報主流程：
      1. 從 DB 讀取最近 7 份 daily 報告
      2. 呼叫 AI 產出週報
      3. 存入 DB（type='weekly'）+ 向量化
      4. 推播到 LINE
    """
    print("=" * 50)
    print(f"  週報產生器啟動")
    print(f"  時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    # Step 1：讀取最近 7 份 daily 報告
    daily_reports = get_recent_daily_reports(days=7)
    print(f"[Weekly] 讀取到 {len(daily_reports)} 份每日報告")

    if not daily_reports:
        print("[Weekly] 沒有每日報告可供彙整，結束。")
        return

    # Step 2：AI 產出週報
    print("\n[Gemini] 產生週報中...")
    report = analyze_weekly(daily_reports)

    print("\n" + "=" * 50)
    print("【本週輿情週報】")
    print("=" * 50)
    print(report)

    # Step 3：存入 DB（type='weekly'）
    save_report(report, report_type="weekly")

    # Step 4：向量化，用 "weekly-YYYY-WXX" 作為 ID 避免與日報衝突
    week_label = f"weekly-{datetime.now().strftime('%Y-W%U')}"
    save_report_embedding(week_label, report, embed_passages([report])[0])

    # Step 5：推播
    push_message(format_report_for_line(report))
    print("[Weekly] 週報已推播完成")


if __name__ == "__main__":
    init_db()
    weekly_agent()

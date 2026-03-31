"""
webhook.py — LINE Bot 多輪問答伺服器

使用方式：
  1. pip install flask
  2. 啟動 ngrok: ngrok http 5000
  3. 到 LINE Developers Console 設定 Webhook URL:
     https://<your-id>.ngrok-free.app/callback
  4. 開啟「Use webhook」，關閉「Auto-reply messages」
  5. python webhook.py
"""

from flask import Flask, request, abort
from linebot.v3.webhook import WebhookHandler
from linebot.v3.messaging import (
    ApiClient, MessagingApi, Configuration,
    ReplyMessageRequest, TextMessage,
    QuickReply, QuickReplyItem, MessageAction,
    MarkMessagesAsReadRequest,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError
import openai
import threading

from config import (LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN,
                    API_KEY, MODEL, BASE_URL)
from database import get_connection, init_db, search_similar_articles, search_similar_reports, save_user_id
from embedder import embed_query
from line_push import push_message

# ──────────────────────────────────────────
app     = Flask(__name__)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

ai_client = openai.OpenAI(api_key=API_KEY, base_url=BASE_URL)

# 每位使用者的對話歷史：{ user_id: [ {role, content}, ... ] }
conversation_histories: dict[str, list] = {}
# 等待確認重置的使用者集合
pending_reset: set[str] = set()
# ──────────────────────────────────────────


def get_latest_report(report_type: str = "daily") -> str:
    """從 DB 取得指定類型的最新一份報告。
    report_type: 'daily'（預設）或 'weekly'
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT content FROM reports WHERE type = ? ORDER BY id DESC LIMIT 1",
        (report_type,)
    )
    row = cursor.fetchone()
    conn.close()
    if report_type == "daily":
        return row[0] if row else "（今日報告尚未產生，請先執行 main.py）"
    return row[0] if row else "（本週報告尚未產生，請先執行 weekly.py）"


def build_system_prompt(user_query: str) -> str:
    """
    RAG 版 system prompt：
    根據使用者的問題，同時從向量 DB 搜尋最相關的報告與文章，
    組成完整背景後才交給 AI 回答。
    """
    # 向量化一次，同時用於搜尋報告與文章
    query_vec = embed_query(user_query)

    # RAG：搜尋最相關的歷史報告（含分析觀點與脈絡）
    relevant_reports = search_similar_reports(query_vec, n_results=2)
    reports_text = ""
    for r in relevant_reports:
        reports_text += f"\n【{r['date']} 報告】\n{r['content']}\n---"
    if not reports_text:
        reports_text = "（報告向量資料庫尚無資料，請先執行 main.py）"

    # RAG：搜尋最相關的原始文章（含事實細節與來源）
    relevant_articles = search_similar_articles(query_vec, n_results=5)
    articles_text = ""
    for a in relevant_articles:
        articles_text += (
            f"\n【{a['source']}】{a['title']}\n"
            f"來源網址：{a['url']}\n"
            f"發布時間：{a['time']}\n"
            f"{a['content']}\n---"
        )
    if not articles_text:
        articles_text = "（文章向量資料庫尚無資料，請先執行 main.py）"

    return f"""你是一位專業的台灣政治與媒體輿情分析師，正在與使用者進行深度對話。

你的任務：
- 根據使用者的「具體問題」給出有深度的分析與見解
- 不要把報告原文直接貼給使用者，那是你的背景資料
- 針對問題深挖：事件背後的原因、各方立場、可能的後續發展、歷史脈絡
- 多輪對話中要記住前面討論的內容，讓對話有連貫性
- 可以主動提出延伸觀點，引導使用者進一步思考

引用來源規則：
- 回答中若引用特定文章，請附上「來源：[標題]（來源網址）」
- 若資訊來自你的背景知識而非以下文章，請說明「這是一般背景知識」

回覆風格：
- 繁體中文，口語化但有深度
- 適合 LINE 閱讀：分點說明，每點不超過 2 句
- 格式不用 Markdown，一般訊息格式。
- 列點以 1.2.3.4. 標示，項目符號使用「🔹 」。

=== 背景資料（僅供你參考）===

【與問題最相關的歷史報告（RAG 檢索）】
{reports_text}

【與問題最相關的原始文章（RAG 檢索）】
{articles_text}
"""


def mark_as_read(user_id: str):
    """標記訊息為已讀。"""
    configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).mark_messages_as_read(
            MarkMessagesAsReadRequest(chat_id=user_id)
        )


def line_reply(reply_token: str, text: str):
    """用 Reply API 回覆使用者（比 Push 省費用）。"""
    if len(text) > 4900:
        text = text[:4900] + "\n⋯（回覆過長，已截斷）"
    configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text)]
            )
        )


def _process_qa(user_id: str, user_text: str):
    """已讀後在背景執行：向量查詢 → AI 回覆 → push_message。"""
    history = conversation_histories.get(user_id, [])
    try:
        messages = [{"role": "system", "content": build_system_prompt(user_text)}] + history
        response = ai_client.chat.completions.create(model=MODEL, messages=messages)
        reply_text = response.choices[0].message.content

        history.append({"role": "assistant", "content": reply_text})
        push_message(reply_text, to=user_id)

    except Exception as e:
        print(f"[錯誤] {e}")
        push_message(f"抱歉，發生錯誤，請稍後再試。\n（{str(e)[:80]}）", to=user_id)


# ──────────────────────────────────────────
#  Webhook 端點
# ──────────────────────────────────────────

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body      = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event: MessageEvent):
    user_id     = event.source.user_id
    user_text   = event.message.text.strip()
    reply_token = event.reply_token

    # ── 記錄 user_id ──────────────────────
    save_user_id(user_id)

    # ── 已讀 ──────────────────────────────
    try:
        mark_as_read(user_id)
    except Exception:
        pass  # 已讀失敗不影響主流程

    # ── 清空紀錄（第一步：詢問確認）────────
    if user_text in ["清除", "重置", "reset", "/reset"]:
        pending_reset.add(user_id)
        configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(
                        text="確定要清空對話紀錄嗎？",
                        quick_reply=QuickReply(items=[
                            QuickReplyItem(action=MessageAction(label="✅ 確認清除", text="確認")),
                            QuickReplyItem(action=MessageAction(label="❌ 取消", text="取消")),
                        ])
                    )]
                )
            )
        return

    # ── 清空紀錄（第二步：執行或取消）──────
    if user_id in pending_reset:
        pending_reset.discard(user_id)
        if user_text == "確認":
            conversation_histories.pop(user_id, None)
            line_reply(reply_token, "對話紀錄已清空，可以重新開始提問。")
        elif user_text == "取消":
            line_reply(reply_token, "已取消。")
        else:
            line_reply(reply_token, "已取消，繼續目前的對話。")
        return

    # ── 今日摘要 ──────────────────────────
    if user_text == "今日摘要":
        report = get_latest_report(report_type="daily")
        line_reply(reply_token, report)
        return

    # ── 本週摘要 ──────────────────────────
    if user_text == "本週摘要":
        report = get_latest_report(report_type="weekly")
        line_reply(reply_token, report)
        return

    # ── 初始化該使用者的對話歷史 ──────────
    if user_id not in conversation_histories:
        conversation_histories[user_id] = []

    history = conversation_histories[user_id]
    history.append({"role": "user", "content": user_text})

    # 只保留最近 10 輪（20 則訊息），避免 context 太長
    if len(history) > 20:
        conversation_histories[user_id] = history[-20:]

    # ── 已讀完成，背景執行向量查詢與 AI ────
    # handle_message 立即返回，LINE 馬上顯示已讀；
    # 耗時的向量搜尋與 AI 呼叫在背景 thread 完成後以 push_message 回覆。
    threading.Thread(
        target=_process_qa,
        args=(user_id, user_text),
        daemon=True
    ).start()


# ──────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    # (Local Version)
    # print("[Webhook] 伺服器啟動於 http://localhost:5000")
    # print("[Webhook] 請確認 ngrok 已啟動並設定好 LINE Webhook URL")
    # app.run(port=5000, debug=False)

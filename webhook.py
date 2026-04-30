"""
webhook.py — LINE Bot 多頻道問答伺服器

每個頻道對應一個獨立的 Webhook URL：
  /callback/channel_1
  /callback/channel_2

新增頻道：在 config.py 的 CHANNELS 加一組 key 即可，不需改此檔。
"""

from flask import Flask, request, abort, g
from linebot.v3.webhook import WebhookHandler
from linebot.v3.messaging import (
    ApiClient, MessagingApi, Configuration,
    ReplyMessageRequest, TextMessage,
    QuickReply, QuickReplyItem, MessageAction,
    MarkMessagesAsReadByTokenRequest,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent, UnfollowEvent
from linebot.v3.exceptions import InvalidSignatureError
import openai
import requests

from config import CHANNELS, API_KEY, MODEL, BASE_URL
from database import get_connection, init_db, search_similar_articles, search_similar_reports, save_user_id, remove_user_id
from embedder import embed_query

# ──────────────────────────────────────────
app = Flask(__name__)

# 每個頻道一個 WebhookHandler，用各自的 secret 驗簽
handlers: dict[str, WebhookHandler] = {
    name: WebhookHandler(ch["secret"])
    for name, ch in CHANNELS.items()
}

ai_client = openai.OpenAI(api_key=API_KEY, base_url=BASE_URL)

# 對話歷史與重置確認：key = "{channel_name}:{user_id}"
conversation_histories: dict[str, list] = {}
pending_reset: set[str] = set()
# ──────────────────────────────────────────


def get_latest_report(report_type: str = "daily") -> str:
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
    """RAG 版 system prompt：向量搜尋相關報告與文章，組成背景後交給 AI。"""
    query_vec = embed_query(user_query)

    relevant_reports = search_similar_reports(query_vec, n_results=2)
    reports_text = ""
    for r in relevant_reports:
        reports_text += f"\n【{r['date']} 報告】\n{r['content']}\n---"
    if not reports_text:
        reports_text = "（報告向量資料庫尚無資料，請先執行 main.py）"

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
- 嚴格禁止使用 Markdown 符號，如：**標題**，用一般訊息格式就好
- 列點以 1.2.3.4. 標示，列點之下的項目符號使用「🔹 」

=== 背景資料（僅供你參考）===

【與問題最相關的歷史報告（RAG 檢索）】
{reports_text}

【與問題最相關的原始文章（RAG 檢索）】
{articles_text}
"""


def mark_as_read(token: str, access_token: str):
    configuration = Configuration(access_token=access_token)
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).mark_messages_as_read_by_token(
            MarkMessagesAsReadByTokenRequest(mark_as_read_token=token)
        )


def show_loading_animation(user_id: str, access_token: str):
    try:
        requests.post(
            "https://api.line.me/v2/bot/chat/loading/start",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"chatId": user_id, "loadingSeconds": 30},
            timeout=5,
        )
    except Exception:
        pass


def line_reply(reply_token: str, text: str, access_token: str):
    if len(text) > 4900:
        text = text[:4900] + "\n⋯（回覆過長，已截斷）"
    configuration = Configuration(access_token=access_token)
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text)]
            )
        )


# ──────────────────────────────────────────
#  Webhook 端點
# ──────────────────────────────────────────

@app.route("/callback/<channel_name>", methods=["POST"])
def callback(channel_name):
    if channel_name not in handlers:
        abort(404)
    g.channel_name = channel_name
    g.channel = CHANNELS[channel_name]

    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handlers[channel_name].handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"


def handle_message(event: MessageEvent):
    channel_name = g.channel_name
    access_token = g.channel["access_token"]
    channel_id   = g.channel["channel_id"]
    user_id      = event.source.user_id
    user_text    = event.message.text.strip()
    reply_token  = event.reply_token
    hist_key     = f"{channel_name}:{user_id}"

    save_user_id(user_id, channel_id)

    mark_as_read_token = event.message.mark_as_read_token
    if mark_as_read_token:
        try:
            mark_as_read(mark_as_read_token, access_token)
        except Exception:
            pass

    # ── 清空紀錄（第一步：詢問確認）
    if user_text in ["清除", "重置", "reset", "/reset"]:
        pending_reset.add(hist_key)
        configuration = Configuration(access_token=access_token)
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

    # ── 清空紀錄（第二步：執行或取消）
    if hist_key in pending_reset:
        pending_reset.discard(hist_key)
        if user_text == "確認":
            conversation_histories.pop(hist_key, None)
            line_reply(reply_token, "對話紀錄已清空，可以重新開始提問。", access_token)
        elif user_text == "取消":
            line_reply(reply_token, "已取消。", access_token)
        else:
            line_reply(reply_token, "已取消，繼續目前的對話。", access_token)
        return

    # ── 今日摘要
    if user_text == "今日摘要":
        line_reply(reply_token, get_latest_report("daily"), access_token)
        return

    # ── 本週摘要
    if user_text == "本週摘要":
        line_reply(reply_token, get_latest_report("weekly"), access_token)
        return

    # ── Q&A：Loading Animation → 同步 AI → line_reply
    show_loading_animation(user_id, access_token)

    if hist_key not in conversation_histories:
        conversation_histories[hist_key] = []

    conversation_histories[hist_key].append({"role": "user", "content": user_text})
    if len(conversation_histories[hist_key]) > 20:
        conversation_histories[hist_key] = conversation_histories[hist_key][-20:]
    history = conversation_histories[hist_key]

    try:
        messages = [{"role": "system", "content": build_system_prompt(user_text)}] + history
        response = ai_client.chat.completions.create(model=MODEL, messages=messages, timeout=25)
        reply_text = response.choices[0].message.content
        history.append({"role": "assistant", "content": reply_text})
        line_reply(reply_token, reply_text, access_token)
    except Exception as e:
        print(f"[錯誤] {e}")
        line_reply(reply_token, "抱歉，回應時間過長或發生錯誤，請再試一次。", access_token)


def handle_follow(event: FollowEvent):
    save_user_id(event.source.user_id, g.channel["channel_id"])


def handle_unfollow(event: UnfollowEvent):
    remove_user_id(event.source.user_id, g.channel["channel_id"])


# 把三個事件處理函數註冊到每個頻道的 handler
for _h in handlers.values():
    _h.add(MessageEvent, message=TextMessageContent)(handle_message)
    _h.add(FollowEvent)(handle_follow)
    _h.add(UnfollowEvent)(handle_unfollow)

# ──────────────────────────────────────────
init_db()

# if __name__ == "__main__":
    # (Local Version)
    # print("[Webhook] 伺服器啟動於 http://localhost:5000")
    # print("[Webhook] 請確認 ngrok 已啟動並設定好 LINE Webhook URL")
    # app.run(port=5000, debug=False)

from linebot.v3.messaging import (
    ApiClient, MessagingApi, Configuration,
    PushMessageRequest, TextMessage
)
from config import LINE_CHANNEL_ACCESS_TOKEN, LINE_USER_IDS
from database import get_all_user_ids


def get_messaging_api():
    """建立 Line Messaging API 連線"""
    configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
    api_client    = ApiClient(configuration)
    return MessagingApi(api_client)


def push_message(text, to=None):
    """
    推播文字訊息給指定使用者。
    to: 指定單一 LINE user_id；省略時推播給 config 的所有 LINE_USER_IDS。
    """
    if len(text) > 4900:
        text = text[:4900] + "\n⋯（訊息過長，已截斷）"

    targets = [to] if to else (get_all_user_ids() or LINE_USER_IDS)
    if not targets:
        print("[Line Bot] 警告：LINE_USER_IDS 未設定，跳過推播")
        return

    api = get_messaging_api()
    for uid in targets:
        try:
            api.push_message(
                PushMessageRequest(
                    to=uid,
                    messages=[TextMessage(text=text)]
                )
            )
            print(f"[Line Bot] 推播成功 → {uid}")
        except Exception as e:
            print(f"[Line Bot] 推播失敗 → {uid}：{e}")


def format_report_for_line(report_text):
    """
    Line 訊息有字數上限（5000字）
    如果報告太長就截斷，並加上提示。
    """
    limit = 4900
    if len(report_text) <= limit:
        return report_text
    return report_text[:limit] + "\n\n⋯（報告過長，已截斷）"

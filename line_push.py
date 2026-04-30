from linebot.v3.messaging import (
    ApiClient, MessagingApi, Configuration,
    PushMessageRequest, TextMessage
)
from config import CHANNELS
from database import get_all_user_ids


def _send(text: str, uid: str, access_token: str):
    configuration = Configuration(access_token=access_token)
    with ApiClient(configuration) as api_client:
        try:
            MessagingApi(api_client).push_message(
                PushMessageRequest(to=uid, messages=[TextMessage(text=text)])
            )
            print(f"[Line Bot] 推播成功 → {uid}")
        except Exception as e:
            print(f"[Line Bot] 推播失敗 → {uid}：{e}")


def push_message(text: str, to: str = None, access_token: str = None):
    """
    推播文字訊息。
    to + access_token: 指定單一使用者（webhook 回覆用）。
    省略 to: 廣播到所有頻道的所有已登錄使用者。
    """
    if len(text) > 4900:
        text = text[:4900] + "\n⋯（訊息過長，已截斷）"

    if to:
        _send(text, to, access_token)
        return

    for name, ch in CHANNELS.items():
        users = get_all_user_ids(ch["channel_id"])
        if not users:
            print(f"[Line Bot] 警告：{name} 無已登錄使用者，跳過推播")
            continue
        for uid in users:
            _send(text, uid, ch["access_token"])


def format_report_for_line(report_text: str) -> str:
    limit = 4900
    if len(report_text) <= limit:
        return report_text
    return report_text[:limit] + "\n\n⋯（報告過長，已截斷）"

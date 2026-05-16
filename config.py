import os
from dotenv import load_dotenv

load_dotenv()  # 讀取同目錄的 .env 檔案

# 專案根目錄（絕對路徑，確保 cron / systemd 從任何目錄執行都正確）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ════════════════════════════════════════
#  Gemini 設定（從 .env 讀取）
# ════════════════════════════════════════
API_KEY         = os.environ["GEMINI_API_KEY"]
MODEL           = "gemini-3-flash"
BASE_URL        = os.environ["LITELLM_BASE_URL"]
IMPORTANT_COUNT = 10  # 第一次篩選幾篇

# ════════════════════════════════════════
#  爬蟲來源
# ════════════════════════════════════════
TEST_FETCH = False
# TEST_FETCH = True  # -> 爬完過濾完資料就停
SOURCES = {
    "yahoo":   True,
    # "udn":   True,  # RSS 爬不到正常的東西
    "ltn":     True,
    "google":  True,
    "ettoday": True,
    "pts":     True,
}

# ════════════════════════════════════════
#  時間過濾
# ════════════════════════════════════════
DATE_FILTER = "today"
#  "today" → 只抓今天
#  "2days" → 最近兩天（測試用）
#  "all"   → 不過濾（測試用）

# ════════════════════════════════════════
#  抓取與分析數量
# ════════════════════════════════════════
MAX_ITEMS_PER_SOURCE    = 200  # 每個來源最多抓幾筆
MAX_ARTICLES_TO_ANALYZE = 10   # 送給 Gemini 最多幾筆 (未使用)

# ════════════════════════════════════════
#  資料庫（絕對路徑）
# ════════════════════════════════════════
DB_PATH    = os.path.join(BASE_DIR, "sentiment.db")
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")

# ════════════════════════════════════════
#  LINE Bot 設定（從 .env 讀取）
#  新增頻道：在 CHANNELS 加一組 key，並在 .env 補三個對應變數即可。
# ════════════════════════════════════════
CHANNELS = {
    "channel_1": {
        "channel_id":   os.environ["LINE_1_CHANNEL_ID"],
        "secret":       os.environ["LINE_1_CHANNEL_SECRET"],
        "access_token": os.environ["LINE_1_CHANNEL_ACCESS_TOKEN"],
    },
    "channel_2": {
        "channel_id":   os.environ["LINE_2_CHANNEL_ID"],
        "secret":       os.environ["LINE_2_CHANNEL_SECRET"],
        "access_token": os.environ["LINE_2_CHANNEL_ACCESS_TOKEN"],
    },
}

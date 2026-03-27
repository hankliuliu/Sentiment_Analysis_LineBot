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
BASE_URL        = "https://litellm.netdb.csie.ncku.edu.tw"
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
#  排程器設定
# ════════════════════════════════════════
SCHEDULER_ENABLED = False   # 跑一次就結束 / 交給 cron
# SCHEDULER_ENABLED = True  # 定時自動執行
SCHEDULER_TIMES   = ["08:00"]  # 每天幾點執行

# ════════════════════════════════════════
#  LINE Bot 設定（從 .env 讀取）
# ════════════════════════════════════════
LINE_CHANNEL_ID           = os.environ["LINE_CHANNEL_ID"]
LINE_CHANNEL_SECRET       = os.environ["LINE_CHANNEL_SECRET"]
LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]

# 推播目標：支援多位使用者，以逗號分隔
# 範例：LINE_USER_IDS=Uabc123,Udef456
LINE_USER_IDS = [uid.strip() for uid in os.environ.get("LINE_USER_IDS", "").split(",") if uid.strip()]

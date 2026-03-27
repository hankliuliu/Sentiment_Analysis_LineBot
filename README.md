# 台灣政治新聞輿情監控系統

自動化從台灣主流媒體抓取政治新聞，透過 AI 分析產生每日情勢簡報，並透過 LINE Bot 推播與互動問答。

---

## 功能特色

- **多來源新聞聚合**：同步抓取 Yahoo、自由時報、Google News、ETtoday、公視等 RSS 來源
- **AI 雙輪分析**：Gemini 第一輪篩選重要標題，第二輪對全文進行深度情勢分析
- **每日 / 每週報告**：自動產生四段式政策簡報（重要事件、輿情趨勢、一句摘要、追蹤清單）
- **LINE Bot 推播**：自動推播每日與每週報告至指定帳號
- **互動問答（RAG）**：透過 LINE 傳訊問問題，系統以歷史文章與報告為背景，由 AI 深度回覆
- **語意搜尋**：multilingual-e5-large 向量嵌入 + ChromaDB，支援中文語意檢索

---

## 系統架構

```
RSS 新聞來源
    │
    ▼
fetcher.py       ← 爬取 RSS + 全文抓取
    │
processor.py     ← 清洗、去重、日期過濾
    │
main.py          ← Gemini ① 篩選重要標題
    │                Gemini ② 深度分析全文
    │
embedder.py      ← multilingual-e5-large 向量化
    │
database.py      ← SQLite (文章/報告) + ChromaDB (向量索引)
    │
line_push.py     ← LINE Bot 推播
    │
webhook.py       ← LINE Bot 互動問答伺服器 (Flask + RAG)
```

---

## 目錄結構

```
Sentiment_Analysis/
├── config.py          # 系統組態（API Key、LINE Token、來源開關等）
├── main.py            # 每日批次流程入口
├── weekly.py          # 每週報告產生器
├── fetcher.py         # RSS 爬蟲 + 全文爬取
├── processor.py       # 資料清洗與過濾
├── embedder.py        # 文字向量化
├── database.py        # SQLite + ChromaDB 介面
├── db_utils.py        # 資料庫管理工具
├── line_push.py       # LINE 推播模組
├── webhook.py         # LINE Bot Webhook 伺服器
├── run_daily.bat      # Windows 每日執行腳本
├── run_weekly.bat     # Windows 每週執行腳本
├── sentiment.db       # SQLite 資料庫（自動建立）
└── chroma_db/         # ChromaDB 向量資料庫（自動建立）
```

---

## 安裝與環境設定

### 系統需求

- Python 3.10+
- Windows 10（batch 腳本）或 macOS / Linux（手動執行）
- 網際網路連線

### 安裝相依套件

```bash
pip install requests beautifulsoup4 sentence-transformers chromadb \
            openai flask line-bot-sdk schedule
```

> 首次執行 `embedder.py` 時會自動下載 `intfloat/multilingual-e5-large` 模型（約 1.3 GB）。

### 設定組態

開啟 `config.py`，填入以下資訊：

```python
# Gemini / LiteLLM
API_KEY = "你的 API Key"
MODEL   = "gemini-3-flash"
BASE_URL = "https://litellm.netdb.csie.ncku.edu.tw"

# LINE Bot
LINE_CHANNEL_ID           = "你的 Channel ID"
LINE_CHANNEL_SECRET       = "你的 Channel Secret"
LINE_CHANNEL_ACCESS_TOKEN = "你的 Access Token"
LINE_USER_ID              = "推播目標的 LINE User ID"
```

> **安全提醒**：建議將上述敏感資訊移至 `.env` 檔案，並將 `.env` 加入 `.gitignore`，避免憑證洩漏至版本控制。

---

## 使用方式

### 每日批次（手動執行）

```bash
python main.py
```

執行流程：
1. 從各 RSS 來源抓取新聞（100–200 篇）
2. 清洗、去重（保留 20–50 篇）
3. Gemini 篩選 10 篇最重要文章
4. 抓取全文並儲存至資料庫
5. Gemini 深度分析產生情勢簡報
6. 儲存報告 + 推播至 LINE

### 每週報告（手動執行）

```bash
python weekly.py
```

從資料庫讀取最近 7 份日報，合成週度情勢分析並推播。

### 排程執行（Windows 工作排程器）

開啟 `config.py` 設定：

```python
SCHEDULER_ENABLED = True
SCHEDULER_TIMES   = ["08:00"]   # 每日執行時間
```

或直接在 Windows 工作排程器中設定 `run_daily.bat` / `run_weekly.bat`。

### 啟動 LINE Bot 互動問答

```bash
# 終端機 1：啟動 Flask 伺服器
python webhook.py

# 終端機 2：建立 ngrok 公開隧道
ngrok http 5000
```

複製 ngrok 輸出的 HTTPS URL，至 LINE Developer Console 設定：
```
Webhook URL: https://<ngrok-url>/callback
Use Webhook: ON
```

---

## LINE Bot 互動指令

| 指令 | 功能 |
|------|------|
| `今日摘要` | 回傳最新每日情勢簡報 |
| `本週摘要` | 回傳最新每週情勢綜整 |
| `清除` / `重置` / `/reset` | 清除對話歷史記錄 |
| 任意問題 | 以 RAG 方式搜尋歷史文章與報告後回覆 |

---

## 資料庫管理

```bash
# 查看資料庫狀態（文章數、報告數、向量數等）
python db_utils.py status

# 清除所有文章（SQLite + ChromaDB）
python db_utils.py clear-articles

# 清除所有報告（SQLite + ChromaDB）
python db_utils.py clear-reports

# 清除全部資料
python db_utils.py clear-all
```

---

## 新聞來源設定

在 `config.py` 中的 `SOURCES` 字典控制各來源的啟用狀態：

```python
SOURCES = {
    "yahoo":   True,   # Yahoo 新聞
    "ltn":     True,   # 自由時報
    "google":  True,   # Google News TW
    "ettoday": True,   # ETtoday 新聞雲
    "pts":     True,   # 公共電視
    "udn":     False,  # 聯合新聞網（停用）
}
```

---

## 時間過濾設定

```python
DATE_FILTER = "today"   # 只抓今日新聞
DATE_FILTER = "2days"   # 抓今日與昨日
DATE_FILTER = "all"     # 不過濾時間
```

---

## 技術棧

| 類別 | 技術 |
|------|------|
| LLM | Google Gemini 3 Flash（透過 LiteLLM 代理）|
| 嵌入模型 | `intfloat/multilingual-e5-large`（1024 維）|
| 向量資料庫 | ChromaDB（cosine 相似度）|
| 關聯式資料庫 | SQLite |
| Web 框架 | Flask |
| 訊息平台 | LINE Messaging API |
| HTML 解析 | BeautifulSoup4 |
| 嵌入框架 | sentence-transformers |

---

## 報告格式範例

```
【2026-03-27 每日情勢簡報】

一、今日前三大重要事件
1. ...
2. ...
3. ...

二、公眾輿情趨勢
...

三、今日情勢一句話摘要
...

四、其他值得追蹤的新聞
• ...
• ...
```

---

## 詳細設計文件

請參閱 [SDD.md](SDD.md)，內含完整的軟體設計文件，包括：
- 所有模組的函式規格
- 資料庫欄位設計
- 資料流程圖
- AI Prompt 設計
- 安全性考量與未來改善建議

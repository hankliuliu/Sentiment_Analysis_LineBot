# 軟體設計文件 (Software Design Document)

**專案名稱**：台灣政治新聞情感分析與輿情監控系統
**版本**：1.0
**日期**：2026-03-27
**作者**：劉彥誠
**狀態**：現行版本

---

## 目錄

1. [系統概述](#1-系統概述)
2. [需求摘要](#2-需求摘要)
3. [系統架構設計](#3-系統架構設計)
4. [模組設計規格](#4-模組設計規格)
   - 4.1 [config.py — 系統組態](#41-configpy--系統組態)
   - 4.2 [fetcher.py — 新聞爬蟲](#42-fetcherpy--新聞爬蟲)
   - 4.3 [processor.py — 資料清洗](#43-processorpy--資料清洗)
   - 4.4 [embedder.py — 文字向量化](#44-embedderpy--文字向量化)
   - 4.5 [database.py — 資料庫介面](#45-databasepy--資料庫介面)
   - 4.6 [db_utils.py — 資料庫管理工具](#46-db_utilspy--資料庫管理工具)
   - 4.7 [main.py — 每日處理流程](#47-mainpy--每日處理流程)
   - 4.8 [weekly.py — 每週報告產生器](#48-weeklypy--每週報告產生器)
   - 4.9 [line_push.py — LINE 推播模組](#49-line_pushpy--line-推播模組)
   - 4.10 [webhook.py — LINE Bot 互動問答伺服器](#410-webhookpy--line-bot-互動問答伺服器)
5. [資料庫設計](#5-資料庫設計)
6. [資料流程圖](#6-資料流程圖)
7. [AI / ML 元件設計](#7-ai--ml-元件設計)
8. [外部整合設計](#8-外部整合設計)
9. [錯誤處理策略](#9-錯誤處理策略)
10. [部署架構](#10-部署架構)
11. [安全性考量](#11-安全性考量)
12. [已知限制與未來改善方向](#12-已知限制與未來改善方向)

---

## 1. 系統概述

### 1.1 目的

本系統為一套 **自動化台灣政治輿情監控平台**，設計目的是每日從主流台灣新聞媒體抓取政治相關報導，透過大型語言模型 (LLM) 篩選重要新聞、分析公眾情感傾向，產出結構化情勢簡報，並透過 LINE Bot 推播給政府相關人員，同時提供互動問答功能以支援即時情資查詢。

### 1.2 系統定位

| 項目 | 說明 |
|------|------|
| 系統類型 | 批次處理 + 即時問答混合架構 |
| 部署環境 | Windows 10 個人電腦（可擴充至雲端） |
| 主要使用者 | 政府相關人員、政策研究人員 |
| 語言環境 | 繁體中文（台灣） |
| 運行頻率 | 每日一次（批次）+ 隨時問答（即時） |

### 1.3 核心功能摘要

1. **多來源新聞聚合**：從六個主流台灣媒體 RSS 來源同步抓取
2. **AI 重要性篩選**：透過 Gemini LLM 從政府視角篩選最重要的 10 篇報導
3. **深度輿情分析**：對精選文章進行全文深度分析，產出政策簡報
4. **向量語意搜尋**：利用 multilingual-e5-large 模型建立知識庫
5. **每週情勢綜整**：彙整七日簡報，輸出週度趨勢分析
6. **LINE Bot 互動問答**：RAG 架構支援情境感知問答
7. **歷史資料管理**：SQLite + ChromaDB 雙資料庫持久化儲存

---

## 2. 需求摘要

### 2.1 功能性需求

| 編號 | 需求描述 | 優先級 |
|------|---------|-------|
| FR-01 | 系統每日自動從六個 RSS 來源抓取新聞 | 高 |
| FR-02 | 對原始新聞執行去重、日期過濾、長度過濾 | 高 |
| FR-03 | 透過 LLM 第一輪分析標題，篩選 10 篇重要文章 | 高 |
| FR-04 | 抓取重要文章全文，快取於 SQLite 避免重複請求 | 高 |
| FR-05 | 對全文執行 LLM 深度分析，產生四段式情勢簡報 | 高 |
| FR-06 | 將文章與報告的向量儲存至 ChromaDB | 高 |
| FR-07 | 透過 LINE Bot 推播每日報告 | 高 |
| FR-08 | 提供 LINE Bot 互動問答（含對話歷史管理） | 高 |
| FR-09 | 每週從七份日報合成週報 | 中 |
| FR-10 | 問答時以 RAG 方式檢索相關歷史資料作為背景 | 中 |
| FR-11 | 提供資料庫狀態查詢與清理工具 | 低 |

### 2.2 非功能性需求

| 編號 | 需求描述 | 指標 |
|------|---------|------|
| NFR-01 | 每日批次流程在 5 分鐘內完成 | 效能 |
| NFR-02 | 同一 URL 不重複爬取 | 效率 |
| NFR-03 | 爬蟲請求間隔 1 秒，避免觸發反爬機制 | 合規 |
| NFR-04 | LINE 訊息長度不超過 5000 字元上限 | 相容性 |
| NFR-05 | 問答回應在 10 秒內完成 | 使用者體驗 |
| NFR-06 | 系統可在無人操作下自動執行 | 可用性 |
| NFR-07 | API 金鑰及 LINE Token 不直接暴露於版本控制 | 安全性（目前未達成） |

---

## 3. 系統架構設計

### 3.1 整體架構圖

```
┌──────────────────────────────────────────────────────────────────┐
│                  外部資料來源 (Internet)                          │
│  Yahoo RSS  |  LTN RSS  |  Google News  |  ETtoday  |  PTS RSS  │
└─────────────────────────┬────────────────────────────────────────┘
                          │ HTTP / RSS / Atom
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│                    資料擷取層 (fetcher.py)                        │
│         BeautifulSoup4 解析  |  HTMLParser 清洗  |  throttle     │
└─────────────────────────┬────────────────────────────────────────┘
                          │ 原始文章列表
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│                    資料處理層 (processor.py)                      │
│          日期過濾  |  標題去重  |  短標題過濾                      │
└─────────────────────────┬────────────────────────────────────────┘
                          │ 乾淨文章列表
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│                    AI 分析層 (main.py / weekly.py)               │
│   Gemini 第一輪：標題篩選  |  Gemini 第二輪：深度情勢分析         │
│              |  LiteLLM 代理  |  OpenAI 相容 API                 │
└──────────┬──────────────────────────────────────────────────────┘
           │                         │
           ▼                         ▼
┌─────────────────────┐   ┌──────────────────────────────────────┐
│  嵌入層(embedder.py)│   │        儲存層 (database.py)           │
│  multilingual-e5   │   │   SQLite (articles, reports 表)      │
│  1024 維向量        │   │   ChromaDB (news_articles 集合)      │
│  passage: / query: │   │   ChromaDB (news_reports 集合)       │
└─────────┬───────────┘   └──────────────────────────────────────┘
          │ 向量                      │
          └──────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│                    推播層 (line_push.py)                          │
│              LINE Messaging API  |  4900 字元截斷                 │
└─────────────────────────┬────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│                  LINE 使用者介面                                   │
│              LINE App (iOS / Android)                            │
└──────────────────────────────────────────────────────────────────┘
                          │ 使用者傳訊息
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│               互動問答層 (webhook.py)                             │
│   Flask 伺服器  |  ngrok 隧道  |  對話歷史管理  |  RAG 搜尋       │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 元件職責分工

| 元件 | 職責 | 依賴 |
|------|------|------|
| `config.py` | 全域組態管理 | 無 |
| `fetcher.py` | RSS 爬蟲 + 全文爬取 | `requests`, `bs4`, `config`, `database` |
| `processor.py` | 資料清洗與過濾 | `config`, `email.utils`, `datetime` |
| `embedder.py` | 文字向量化 | `sentence_transformers` |
| `database.py` | SQLite + ChromaDB 操作 | `sqlite3`, `chromadb`, `config` |
| `db_utils.py` | 資料庫管理 CLI | `database`, `chromadb` |
| `main.py` | 每日批次流程協調者 | 所有模組 |
| `weekly.py` | 每週批次流程協調者 | `database`, `embedder`, `line_push`, `config` |
| `line_push.py` | LINE 訊息推播 | `linebot`, `config` |
| `webhook.py` | LINE Bot 問答伺服器 | `flask`, `linebot`, `database`, `embedder`, `config` |

### 3.3 兩大流程的時序關係

```
每日流程 (main.py)                每週流程 (weekly.py)
─────────────────                 ─────────────────────
每日執行                           每週執行
    │                                     │
    ├─ 爬取新聞                    從 SQLite 讀取
    ├─ AI 篩選與分析                最近 7 份日報
    ├─ 儲存報告至 DB                       │
    └─ 推播至 LINE ──────────────→ AI 合成週報
                                          │
                                   儲存 + 推播
```

---

## 4. 模組設計規格

### 4.1 `config.py` — 系統組態

#### 職責
集中管理所有系統參數，確保各模組共享一致的設定。

#### 組態項目規格

```python
# ── Gemini LLM 設定 ──
API_KEY: str          # LiteLLM 代理 API Key
MODEL: str            # 模型名稱，目前為 "gemini-3-flash"
BASE_URL: str         # LiteLLM 代理端點：https://litellm.netdb.csie.ncku.edu.tw
IMPORTANT_COUNT: int  # AI 篩選保留的文章數量，預設 10

# ── 資料來源開關 ──
SOURCES: dict[str, bool]  # 各 RSS 來源的啟用/停用開關
# {
#   "yahoo": True,    # Yahoo News Taiwan
#   "ltn":   True,    # 自由時報
#   "google": True,   # Google News TW
#   "ettoday": True,  # ETtoday 新聞雲
#   "pts":   True,    # 公共電視新聞
#   "udn":   False    # 聯合新聞網（目前停用）
# }

# ── 時間過濾 ──
DATE_FILTER: str  # "today" | "2days" | "all"

# ── 抓取限制 ──
MAX_ITEMS_PER_SOURCE: int   # 每個來源最多抓取筆數，預設 200
MAX_ARTICLES_TO_ANALYZE: int # 最終送入深度分析的文章數，預設 10

# ── 資料庫 ──
DB_PATH: str  # SQLite 檔案路徑，預設 "sentiment.db"

# ── 排程器（Windows Task Scheduler）──
SCHEDULER_ENABLED: bool    # True/False
SCHEDULER_TIMES: list[str] # 執行時間列表，例如 ["08:00", "20:00"]

# ── LINE Bot 憑證 ──
LINE_CHANNEL_ID: str
LINE_CHANNEL_SECRET: str
LINE_CHANNEL_ACCESS_TOKEN: str
LINE_USER_ID: str  # 推播目標使用者的 LINE User ID
```

#### 設計決策
- **所有常數集中於此檔案**，其他模組 `from config import XXX` 取得，不直接讀取環境變數或設定檔。
- 敏感憑證目前直接寫入此檔案（開發便利），**生產環境應改用 `.env` 搭配 `python-dotenv`**。

---

### 4.2 `fetcher.py` — 新聞爬蟲

#### 職責
從各台灣新聞媒體 RSS / Atom 來源抓取文章清單，以及針對特定文章進行全文爬取。

#### 函式規格

##### `_strip_html(text: str) -> str`
| 項目 | 說明 |
|------|------|
| 輸入 | 含 HTML 標籤的字串 |
| 輸出 | 純文字字串 |
| 實作 | 使用 `html.parser` 的 `HTMLParser` 清除所有 HTML 標籤 |

---

##### `fetch_yahoo_news() -> list[dict]`
##### `fetch_udn_news() -> list[dict]`
##### `fetch_ltn_news() -> list[dict]`
##### `fetch_google_news_tw() -> list[dict]`
##### `fetch_ettoday_news() -> list[dict]`
##### `fetch_pts_news() -> list[dict]`

| 項目 | 說明 |
|------|------|
| 輸入 | 無 |
| 輸出 | `list[dict]`，每個 dict 包含下列欄位 |
| 欄位 | `source`, `title`, `url`, `time` (RFC 2822), `description`, `content` (空字串) |
| 解析格式 | RSS 2.0 (`<item>`) 或 Atom 1.0 (`<entry>`，PTS 使用） |
| 錯誤處理 | `try/except` 捕獲所有例外，記錄錯誤後回傳空列表 |

**RSS URL 對照表：**

| 來源 | URL |
|------|-----|
| Yahoo News | `https://tw.news.yahoo.com/rss` |
| UDN | `https://udn.com/rssfeed/news/2/6638?ch=news` |
| 自由時報 | `https://news.ltn.com.tw/rss/all.xml` |
| Google News TW | `https://news.google.com/rss?hl=zh-TW&gl=TW&ceid=TW:zh-Hant` |
| ETtoday | `https://feeds.feedburner.com/ettoday/realtime` |
| PTS | `https://news.pts.org.tw/xml/newsfeed.xml` |

---

##### `fetch_article_content(url: str) -> str`

| 項目 | 說明 |
|------|------|
| 輸入 | 文章 URL |
| 輸出 | 純文字全文（最多 3000 字元） |
| 實作步驟 | 1. `requests.get(url, timeout=10)` |
|          | 2. BeautifulSoup 解析 HTML |
|          | 3. 移除 `<script>`, `<style>`, `<nav>`, `<footer>`, `<header>`, `<aside>` |
|          | 4. 提取所有長度 > 20 字元的 `<p>` 標籤文字 |
|          | 5. `"\n".join(paragraphs)[:3000]` |
| 失敗回傳 | `""` (空字串) |

---

##### `fetch_contents_for_selected(articles: list[dict]) -> list[dict]`

| 項目 | 說明 |
|------|------|
| 輸入 | 已篩選重要文章列表 |
| 輸出 | 同列表，`content` 欄位填入全文 |
| 快取機制 | 先查 SQLite `get_cached_content(url)`，有則直接使用 |
| 速率限制 | 每次 HTTP 請求後 `time.sleep(1)` |

---

##### `fetch_all() -> list[dict]`

| 項目 | 說明 |
|------|------|
| 輸入 | 無（讀取 `SOURCES` 組態） |
| 輸出 | 所有啟用來源的文章合併列表（100–200 篇） |
| 行為 | 依 `SOURCES[name] == True` 決定是否呼叫對應的 `fetch_XXX_news()` |

---

### 4.3 `processor.py` — 資料清洗

#### 職責
對爬取的原始文章進行三階段清洗：時間過濾、去重、長度過濾。

#### 函式規格

##### `is_within_date_range(time_str: str) -> bool`

| 項目 | 說明 |
|------|------|
| 輸入 | RFC 2822 格式的時間字串 |
| 輸出 | `True` 表示文章在允許的時間範圍內 |

**過濾邏輯：**

| `DATE_FILTER` 值 | 行為 |
|-----------------|------|
| `"today"` | 只保留今日文章 |
| `"2days"` | 保留今日與昨日 |
| `"all"` | 不過濾（全部通過） |
| 解析失敗 | 通過（不丟棄未知時間的文章） |
| 時間早於 2020 | 通過（避免過濾沒有時間的舊文） |

---

##### `deduplicate(articles: list[dict]) -> list[dict]`

| 項目 | 說明 |
|------|------|
| 輸入 | 文章列表 |
| 輸出 | 去重後的文章列表 |
| 去重鍵值 | 標題前 10 個字元（`title[:10]`）|
| 演算法 | `seen: set[str]`，有序集合去重，保留第一次出現 |

---

##### `process(articles: list[dict]) -> list[dict]`

完整清洗流程：

```
輸入 (100–200 篇)
    │
    ▼ is_within_date_range()
(保留今日文章)
    │
    ▼ deduplicate()
(移除重複標題)
    │
    ▼ len(title) >= 5
(移除過短標題)
    │
    ▼
輸出 (20–50 篇)
```

每步驟輸出統計數字至 stdout。

---

### 4.4 `embedder.py` — 文字向量化

#### 職責
使用 `intfloat/multilingual-e5-large` 模型將文字轉換為 1024 維向量，供 ChromaDB 語意搜尋使用。

#### 模型資訊

| 項目 | 說明 |
|------|------|
| 模型名稱 | `intfloat/multilingual-e5-large` |
| 向量維度 | 1024 |
| 支援語言 | 多語言（含繁體中文） |
| 模型大小 | ~1.3 GB（首次使用自動下載） |
| 相似度量 | 餘弦相似度（Cosine Similarity） |

#### 函式規格

##### `get_model() -> SentenceTransformer`

| 項目 | 說明 |
|------|------|
| 輸入 | 無 |
| 輸出 | `SentenceTransformer` 模型實例 |
| 快取 | 全域變數 `_model`，僅載入一次（Singleton 模式）|

---

##### `embed_passages(texts: list[str]) -> list[list[float]]`

| 項目 | 說明 |
|------|------|
| 輸入 | 文章或報告文字列表 |
| 輸出 | 對應的 1024 維向量列表 |
| 前綴格式 | `"passage: {text}"` |
| 正規化 | 向量正規化（`normalize_embeddings=True`）|

---

##### `embed_query(text: str) -> list[float]`

| 項目 | 說明 |
|------|------|
| 輸入 | 使用者查詢字串 |
| 輸出 | 單一 1024 維向量 |
| 前綴格式 | `"query: {text}"` |

**E5 模型的 passage/query 設計：**
multilingual-e5-large 使用非對稱嵌入設計。文件端加 `"passage: "` 前綴，查詢端加 `"query: "` 前綴，可提升語意匹配精準度。

---

### 4.5 `database.py` — 資料庫介面

#### 職責
統一管理 SQLite（結構化資料）與 ChromaDB（向量資料）的所有讀寫操作。

#### ChromaDB 函式規格

##### `get_chroma_client() -> chromadb.PersistentClient`

| 項目 | 說明 |
|------|------|
| 儲存路徑 | `./chroma_db/`（專案根目錄） |
| 快取 | 全域 `_chroma_client`，延遲初始化 |

---

##### `get_vector_collection() -> chromadb.Collection`

| 項目 | 說明 |
|------|------|
| 集合名稱 | `news_articles` |
| 相似度量 | `cosine` |

---

##### `get_report_collection() -> chromadb.Collection`

| 項目 | 說明 |
|------|------|
| 集合名稱 | `news_reports` |
| 相似度量 | `cosine` |

---

##### `save_article_embeddings(articles: list[dict], embeddings: list[list[float]]) -> None`

| 項目 | 說明 |
|------|------|
| 操作 | Upsert（存在則覆蓋，不存在則新增）|
| ID 計算 | `str(hash(article['url']))` |
| Metadata 欄位 | `source`, `title`, `url`, `time`, `fetched_at` (YYYY-MM-DD) |
| Documents 欄位 | 文章標題 + 全文 |

---

##### `save_report_embedding(date_str: str, content: str, embedding: list[float]) -> None`

| 項目 | 說明 |
|------|------|
| 操作 | Upsert |
| ID 計算 | `str(hash(date_str))` |
| Metadata 欄位 | `date` |

---

##### `search_similar_reports(query_embedding: list[float], n_results: int = 2) -> list[dict]`

| 項目 | 說明 |
|------|------|
| 輸入 | 使用者查詢向量 |
| 輸出 | `[{"date": str, "content": str}]`，最多 n_results 筆 |
| 搜尋集合 | `news_reports` |

---

##### `search_similar_articles(query_embedding: list[float], n_results: int = 5) -> list[dict]`

| 項目 | 說明 |
|------|------|
| 輸入 | 使用者查詢向量 |
| 輸出 | `[{"source": str, "title": str, "url": str, "time": str, "content": str}]` |
| 搜尋集合 | `news_articles` |

---

#### SQLite 函式規格

##### `init_db() -> None`

建立資料庫結構（若不存在）：

```sql
CREATE TABLE IF NOT EXISTS articles (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    source     TEXT,
    title      TEXT,
    url        TEXT,
    time       TEXT,
    content    TEXT,
    fetched_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_url ON articles(url);
CREATE INDEX IF NOT EXISTS idx_articles_fetched_at ON articles(fetched_at);

CREATE TABLE IF NOT EXISTS reports (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT,
    content    TEXT,
    type       TEXT DEFAULT 'daily'
);
```

---

##### `save_articles(articles: list[dict]) -> None`

```sql
INSERT OR IGNORE INTO articles (source, title, url, time, content, fetched_at)
VALUES (?, ?, ?, ?, ?, ?)
```
- `fetched_at` = 當前時間戳 (YYYY-MM-DD HH:MM:SS)
- `INSERT OR IGNORE`：相同 URL 不覆蓋

---

##### `get_cached_content(url: str) -> str | None`

```sql
SELECT content FROM articles WHERE url = ? AND content != ''
```
- 回傳第一筆 `content`，或 `None`

---

##### `get_today_context() -> tuple[str, list[tuple]]`

```sql
-- 最新報告
SELECT content FROM reports ORDER BY id DESC LIMIT 1

-- 今日文章
SELECT source, title, content FROM articles
WHERE fetched_at LIKE '今日日期%'
```
- 回傳 `(latest_report_text, [(source, title, content), ...])`

---

##### `save_report(content: str, report_type: str = "daily") -> None`

```sql
INSERT INTO reports (created_at, content, type) VALUES (?, ?, ?)
```

---

##### `get_recent_daily_reports(days: int = 7) -> list[dict]`

```sql
SELECT created_at, content FROM reports
WHERE type = 'daily'
ORDER BY id DESC
LIMIT ?
```
- 回傳 `[{"created_at": str, "content": str}]`

---

### 4.6 `db_utils.py` — 資料庫管理工具

#### 職責
提供命令列介面 (CLI) 以查看和清理資料庫內容。

#### 子命令規格

| 命令 | 函式 | 行為 |
|------|------|------|
| `python db_utils.py status` | `status()` | 顯示 SQLite 文章數、報告數、日期範圍；ChromaDB 向量數 |
| `python db_utils.py clear-articles` | `clear_articles()` | 清空 SQLite `articles` 表 + ChromaDB `news_articles` 集合 |
| `python db_utils.py clear-reports` | `clear_reports()` | 清空 SQLite `reports` 表 + ChromaDB `news_reports` 集合 |
| `python db_utils.py clear-all` | `clear_all()` | 清空所有 SQLite 表 + 刪除整個 `chroma_db/` 目錄 |

---

### 4.7 `main.py` — 每日處理流程

#### 職責
作為每日批次流程的協調者 (Orchestrator)，按順序呼叫各模組完成從爬取到推播的完整流程。

#### 函式規格

##### `select_important(articles: list[dict]) -> list[dict]`

**Gemini 第一輪呼叫**

| 項目 | 說明 |
|------|------|
| 輸入 | 20–50 篇已清洗文章（含標題與摘要）|
| 輸出 | 5–10 篇最重要文章 |

**Prompt 設計：**
```
你是一位政府新聞助理。以下是今日的新聞標題清單（JSON 格式），
每篇都有 source（媒體來源）、title（標題）和 description（摘要）。
請從政府的角度，選出最重要、最需要關注的 {IMPORTANT_COUNT} 篇新聞，
回傳包含所選文章索引（0-based）的 JSON 陣列，格式為：
{"selected": [0, 3, 5, ...]}
```

**解析策略：**
1. 解析回應中的 JSON
2. 依索引從原始列表取出文章
3. 解析失敗時 fallback：返回前 5 篇

---

##### `analyze_in_depth(articles: list[dict]) -> str`

**Gemini 第二輪呼叫**

| 項目 | 說明 |
|------|------|
| 輸入 | 5–10 篇含全文的重要文章 |
| 輸出 | 四段式政策情勢簡報（文字格式）|

**Prompt 設計：**
```
你是政府的新聞分析助理，請根據以下今日重要新聞，撰寫政府用的情勢簡報，
包含以下四個部分：
1. 今日前三大重要事件（各 3–4 句說明，包含對政府的潛在影響）
2. 公眾輿情趨勢（整體民意動向）
3. 今日情勢一句話摘要
4. 其他五則值得持續追蹤的新聞（條列）

每篇文章包含 source（媒體）、title（標題）和 content（全文）。
```

---

##### `save_txt_report(report_text: str) -> None`

| 項目 | 說明 |
|------|------|
| 檔案命名 | `report_YYYY-MM-DD_HHMM.txt` |
| 儲存位置 | 專案根目錄 |
| 編碼 | UTF-8 |

---

##### `agent() -> None`

每日完整流程：

```
步驟 1:  fetch_all()                   → 100–200 原始文章
步驟 2:  process()                     → 20–50 乾淨文章
步驟 3:  select_important()            → 5–10 重要文章（標題篩選）
步驟 4:  fetch_contents_for_selected() → 取得全文（含 SQLite 快取）
步驟 5:  save_articles()               → 儲存至 SQLite
步驟 6:  embed_passages()              → 產生 1024 維向量
步驟 7:  save_article_embeddings()     → 儲存至 ChromaDB
步驟 8:  analyze_in_depth()            → 產生情勢簡報
步驟 9:  save_txt_report()             → 儲存為 .txt 檔案
步驟 10: save_report()                 → 儲存至 SQLite reports 表
步驟 11: embed_passages([report])      → 報告向量化
步驟 12: save_report_embedding()       → 儲存至 ChromaDB
步驟 13: push_message()                → 推播至 LINE
```

---

### 4.8 `weekly.py` — 每週報告產生器

#### 職責
從過去七份每日報告合成週度情勢綜整報告。

#### 函式規格

##### `analyze_weekly(daily_reports: list[dict]) -> str`

**Gemini 週報呼叫**

| 項目 | 說明 |
|------|------|
| 輸入 | 7 份日報 `[{"created_at": str, "content": str}]` |
| 輸出 | 四段式週度情勢分析（文字格式）|

**資料前處理：**
- 反轉排序（最舊 → 最新，呈現時間流）
- 格式化：`【YYYY-MM-DD】\n{report}\n---`

**Prompt 設計：**
```
以下是本週每日新聞情勢簡報，請綜整成週報，包含：
1. 三大週度主題及其走向（各 3–4 句）
2. 本週公眾輿情整體趨勢
3. 本週情勢一句話摘要
4. 下週應持續追蹤的三個議題
```

---

##### `weekly_agent() -> None`

每週完整流程：

```
步驟 1: get_recent_daily_reports(days=7) → 最近 7 份日報
步驟 2: analyze_weekly()                 → Gemini 週報生成
步驟 3: save_report(type='weekly')       → 儲存至 SQLite
步驟 4: embed_passages([report])         → 向量化
步驟 5: save_report_embedding(           → 儲存至 ChromaDB
          id="weekly-YYYY-WXX")
步驟 6: push_message()                   → 推播至 LINE
```

---

### 4.9 `line_push.py` — LINE 推播模組

#### 職責
封裝 LINE Messaging API 的訊息推播操作。

#### 函式規格

##### `get_messaging_api() -> MessagingApi`

| 項目 | 說明 |
|------|------|
| 初始化 | 使用 `LINE_CHANNEL_ACCESS_TOKEN` 建立 API 客戶端 |

---

##### `push_message(text: str, to: str = None) -> None`

| 項目 | 說明 |
|------|------|
| 輸入 | `text`: 訊息內容；`to`: 目標 User ID（預設 `LINE_USER_ID`）|
| 長度限制 | LINE API 單則訊息上限 5000 字元 |
| 截斷機制 | 超過 4900 字元時截斷並加入 `"⋯（訊息過長，已截斷）"` |
| 訊息類型 | `TextMessage` |

---

##### `format_report_for_line(report_text: str) -> str`

| 項目 | 說明 |
|------|------|
| 功能 | 格式化報告供 LINE 顯示（含截斷處理）|
| 等同 | `push_message` 的截斷邏輯，但僅返回字串不推播 |

---

### 4.10 `webhook.py` — LINE Bot 互動問答伺服器

#### 職責
提供 Flask HTTP 伺服器接收 LINE Webhook，處理使用者互動問答，並以 RAG 架構生成情境感知回覆。

#### 全域狀態

```python
conversation_histories: dict[str, list]
# {
#   "U62f3f4191424ba8044b1e003235cfd6a": [
#     {"role": "user", "content": "..."},
#     {"role": "assistant", "content": "..."},
#     ...  # 最多保留 20 筆（10 輪）
#   ]
# }

pending_reset: set[str]
# 等待確認清除歷史的使用者 ID 集合
```

#### 函式規格

##### `build_system_prompt(user_query: str) -> str`

RAG 核心邏輯：

```
使用者問題
    │
    ▼ embed_query(user_query)
查詢向量 (1024 維)
    │
    ├─► search_similar_reports(n=2)  → 最相關的 2 份歷史報告
    └─► search_similar_articles(n=5) → 最相關的 5 篇歷史文章
    │
    ▼
建構 System Prompt：
    ├─ 角色定義：「你是政府新聞分析顧問」
    ├─ 檢索到的相關報告（含日期）
    ├─ 檢索到的相關文章（含來源）
    └─ 行為指引：
       - 不逐字貼上報告，需深度分析
       - 引用來源時標明媒體名稱
       - LINE 格式（不使用 Markdown）
       - 結尾建議延伸觀察視角
```

---

##### `handle_message(event: MessageEvent)` — 訊息處理邏輯

**指令對照表：**

| 使用者輸入 | 回應行為 |
|-----------|---------|
| `清除` / `重置` / `/reset` | 詢問是否確認清除對話歷史 |
| `確認`（在 pending_reset 中）| 清除 `conversation_histories[user_id]` |
| `取消`（在 pending_reset 中）| 取消清除，回復正常問答 |
| `今日摘要` | 回傳最新一份日報（截斷至 4900 字元）|
| `本週摘要` | 回傳最新一份週報（截斷至 4900 字元）|
| 其他文字 | 觸發 RAG 問答流程（背景執行緒）|

**問答流程（背景執行緒 `_process_qa`）：**

```
1. 加入 user 訊息至 conversation_histories
2. 保留最後 20 筆記錄（10 輪）
3. build_system_prompt(user_text) → RAG System Prompt
4. Gemini API 呼叫：
   - system: RAG System Prompt
   - messages: conversation_histories[user_id]
5. 加入 assistant 回覆至 conversation_histories
6. push_message(reply)
```

**API 規格：**

| 項目 | 說明 |
|------|------|
| 框架 | Flask |
| 端點 | `POST /callback` |
| 驗證 | LINE Signature Validation (`X-Line-Signature` header) |
| 執行埠 | 5000 |
| 並行 | `threading.Thread` 處理每個問答請求 |
| 即時讀取 | 收到訊息後立即呼叫 `mark_as_read()` |

---

## 5. 資料庫設計

### 5.1 SQLite 資料庫 (`sentiment.db`)

#### `articles` 表

| 欄位 | 型態 | 說明 |
|------|------|------|
| `id` | INTEGER PK | 自動遞增主鍵 |
| `source` | TEXT | 新聞來源（yahoo, ltn, google, ettoday, pts）|
| `title` | TEXT | 文章標題 |
| `url` | TEXT | 文章 URL（UNIQUE INDEX）|
| `time` | TEXT | RSS 發布時間（RFC 2822 格式）|
| `content` | TEXT | 全文文字（最多 3000 字元，空表示未抓取）|
| `fetched_at` | TEXT | 爬取時間戳（YYYY-MM-DD HH:MM:SS，有 INDEX）|

#### `reports` 表

| 欄位 | 型態 | 說明 |
|------|------|------|
| `id` | INTEGER PK | 自動遞增主鍵 |
| `created_at` | TEXT | 產生時間戳 |
| `content` | TEXT | 報告全文 |
| `type` | TEXT | 報告類型：`daily` 或 `weekly`，預設 `daily` |

#### 索引設計

```sql
CREATE UNIQUE INDEX idx_articles_url ON articles(url);
-- 防止同一 URL 重複插入；INSERT OR IGNORE 依此運作

CREATE INDEX idx_articles_fetched_at ON articles(fetched_at);
-- 加速 get_today_context() 的日期範圍查詢
```

---

### 5.2 ChromaDB 向量資料庫 (`./chroma_db/`)

#### `news_articles` 集合

| 項目 | 說明 |
|------|------|
| ID | `str(hash(url))` |
| Documents | `title + "\n" + content` |
| Embeddings | 1024 維 `embed_passages()` 輸出 |
| Metadata | `source`, `title`, `url`, `time`, `fetched_at` |
| 相似度量 | cosine |

#### `news_reports` 集合

| 項目 | 說明 |
|------|------|
| ID | `str(hash(date_str))` / `"weekly-YYYY-WXX"` |
| Documents | 報告全文 |
| Embeddings | 1024 維 `embed_passages()` 輸出 |
| Metadata | `date` |
| 相似度量 | cosine |

---

## 6. 資料流程圖

### 6.1 每日批次流程

```
[RSS 來源] ──→ fetch_all() ──→ [原始: 100–200 篇]
                                       │
                                 process()
                                       │
                               [乾淨: 20–50 篇]
                                       │
                            select_important() [Gemini ①]
                                       │
                               [重要: 5–10 篇]
                                       │
                         fetch_contents_for_selected()
                         (SQLite 快取 or HTTP 爬取)
                                       │
                             [含全文: 5–10 篇]
                              │         │
                        save_articles()  embed_passages()
                              │               │
                          [SQLite]     save_article_embeddings()
                                               │
                                         [ChromaDB]
                                               │
                              analyze_in_depth() [Gemini ②]
                                               │
                                      [情勢簡報]
                              ┌────────┬───────┬────────┐
                         save_txt  save_report  embed → ChromaDB
                                               │
                                        push_message()
                                               │
                                         [LINE Bot]
```

### 6.2 LINE Bot 問答流程

```
[LINE 使用者]
     │ 傳送訊息
     ▼
[LINE Platform] ── Webhook POST /callback ──→ [Flask webhook.py]
                                                      │
                                            特殊指令判斷
                                                      │
                                              ┌───────┴──────┐
                                           快速回應       背景問答
                                         (今日摘要等)         │
                                                      build_system_prompt()
                                                          │
                                                    embed_query()
                                                          │
                                              ┌───────────┴──────────────┐
                                     search_similar_reports()  search_similar_articles()
                                         (ChromaDB, n=2)           (ChromaDB, n=5)
                                              └───────────┬──────────────┘
                                                   System Prompt 建構
                                                          │
                                                   Gemini API 呼叫
                                                   (含對話歷史)
                                                          │
                                              push_message(reply)
                                                          │
                                               [LINE 使用者收到回覆]
```

---

## 7. AI / ML 元件設計

### 7.1 LLM 整合設計

#### API 架構

```
main.py / weekly.py / webhook.py
         │
         │  openai.OpenAI(
         │      api_key=API_KEY,
         │      base_url=BASE_URL
         │  )
         ▼
    LiteLLM 代理伺服器
    (https://litellm.netdb.csie.ncku.edu.tw)
         │
         ▼
    Google Gemini 3 Flash
```

使用 OpenAI 相容 SDK 呼叫 LiteLLM 代理，使系統可輕易切換底層 LLM（只需更改 `config.py` 的 `MODEL` 和 `BASE_URL`）。

#### LLM 呼叫矩陣

| 呼叫點 | 模型 | 輸入 | 輸出 | 最大 Token |
|--------|------|------|------|-----------|
| `select_important()` | gemini-3-flash | 20–50 篇標題 JSON | JSON `{"selected": [...]}` | ~500 |
| `analyze_in_depth()` | gemini-3-flash | 5–10 篇全文 | 四段式簡報文字 | ~2000 |
| `analyze_weekly()` | gemini-3-flash | 7 份日報 | 四段式週報文字 | ~2000 |
| 問答 `_process_qa()` | gemini-3-flash | System + 對話歷史 + 查詢 | 問答回覆 | ~1500 |

### 7.2 向量嵌入設計

#### E5 模型的非對稱嵌入策略

```
儲存時（文章/報告）:     "passage: {text}" ──→ embed_passages()
查詢時（使用者問題）:    "query: {text}"   ──→ embed_query()
```

此設計來自 E5 模型的訓練方式，使用不同前綴可提升檢索精準度。

#### 向量搜尋規格

| 搜尋類型 | 集合 | n_results | 用途 |
|---------|------|-----------|------|
| `search_similar_reports` | `news_reports` | 2 | 找相似歷史報告作為 RAG 背景 |
| `search_similar_articles` | `news_articles` | 5 | 找相關文章作為 RAG 背景 |

---

## 8. 外部整合設計

### 8.1 LINE Messaging API 整合

#### 推播 vs. 回覆 API

| API | 使用場景 | 費用 |
|-----|---------|------|
| Push API (`push_message`) | 主動推送日報、週報、問答回覆 | 依訊息數計費 |
| Reply API (`line_reply`) | Webhook 直接回覆（較省成本）| 免費（24 小時內）|

目前設計均使用 Push API（`push_message`），未使用 Reply API，可優化成本。

#### Webhook 設定需求

```
1. 啟動 Flask 伺服器：python webhook.py (port 5000)
2. 啟動 ngrok 隧道：ngrok http 5000
3. 複製 ngrok HTTPS URL
4. LINE Developer Console 設定：
   Webhook URL = https://<ngrok-url>/callback
   Use Webhook: ON
```

### 8.2 新聞媒體 RSS 整合

#### 各來源解析差異

| 來源 | 格式 | 特殊處理 |
|------|------|---------|
| Yahoo / UDN / LTN / Google / ETtoday | RSS 2.0 `<item>` | 標準解析 |
| PTS | Atom 1.0 `<entry>` | 使用 `<id>` 作為 URL，`<updated>` 作為時間 |

### 8.3 LiteLLM 代理整合

系統透過 LiteLLM 代理存取 Gemini，使用 OpenAI 相容格式：

```python
client = openai.OpenAI(
    api_key=config.API_KEY,
    base_url=config.BASE_URL
)
response = client.chat.completions.create(
    model=config.MODEL,
    messages=[{"role": "user", "content": prompt}]
)
```

---

## 9. 錯誤處理策略

### 9.1 各模組錯誤處理

| 模組 | 錯誤情境 | 處理方式 |
|------|---------|---------|
| `fetcher.py` | RSS 來源無法連線 | `try/except`，回傳空列表，繼續其他來源 |
| `fetcher.py` | 全文爬取失敗 | 回傳空字串，文章仍進入分析 |
| `main.py` | JSON 解析失敗（`select_important`）| Fallback：使用前 5 篇文章 |
| `line_push.py` | 訊息過長 | 截斷至 4900 字元並加入截斷提示 |
| `webhook.py` | AI 呼叫失敗 | 推播錯誤訊息含例外類型與說明 |
| `processor.py` | 日期解析失敗 | 保留文章（不因日期格式問題丟棄）|
| `database.py` | 重複 URL 插入 | `INSERT OR IGNORE`（靜默忽略）|

### 9.2 對話歷史管理

| 情境 | 行為 |
|------|------|
| 對話歷史超過 20 筆 | 自動保留最新 20 筆（10 輪）|
| 使用者輸入清除指令 | 二步驟確認（防止誤刪）|
| 新使用者第一次傳訊 | 自動建立空歷史記錄 |

---

## 10. 部署架構

### 10.1 目前部署（Windows 本地端）

```
Windows 10 電腦
├── Python 環境
│   ├── sentence_transformers (含 multilingual-e5-large 模型)
│   ├── chromadb
│   ├── flask
│   ├── linebot
│   └── requests, beautifulsoup4, openai, ...
│
├── 批次執行
│   ├── run_daily.bat  ← Windows 工作排程器觸發
│   └── run_weekly.bat ← Windows 工作排程器觸發
│
├── 持久化儲存
│   ├── sentiment.db   (SQLite, ~1.2 MB)
│   └── chroma_db/     (ChromaDB, 向量索引)
│
└── LINE Bot 伺服器
    ├── python webhook.py (port 5000)
    └── ngrok http 5000 (公開 HTTPS 隧道)
```

### 10.2 排程執行設定

```
Windows 工作排程器:
  任務: "每日新聞分析"
  觸發: 每日 01:25
  動作: 執行 run_daily.bat

  任務: "每週情勢綜整"
  觸發: 每週一 08:00
  動作: 執行 run_weekly.bat
```

### 10.3 執行方式

| 執行情境 | 命令 |
|---------|------|
| 手動執行每日流程 | `python main.py` |
| 手動執行每週報告 | `python weekly.py` |
| 啟動 LINE Bot 伺服器 | `python webhook.py` |
| 查看資料庫狀態 | `python db_utils.py status` |
| 清除所有資料 | `python db_utils.py clear-all` |

---

## 11. 安全性考量

### 11.1 目前已知安全問題

| 問題 | 風險等級 | 說明 |
|------|---------|------|
| 憑證硬編碼於 `config.py` | 高 | API Key、LINE Token 等敏感資訊不應提交至版本控制 |
| LINE User ID 硬編碼 | 中 | 若洩漏可能被用於垃圾訊息攻擊 |
| 爬蟲無 robots.txt 檢查 | 低 | 可能違反某些網站的使用條款 |
| Flask 以 `debug=False` 運行 | 已處理 | 不暴露除錯資訊 |

### 11.2 建議改善措施

```python
# 建議：將 config.py 改為讀取環境變數
import os
from dotenv import load_dotenv

load_dotenv()  # 讀取 .env 檔案

API_KEY = os.environ["GEMINI_API_KEY"]
LINE_CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]
LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
LINE_USER_ID = os.environ["LINE_USER_ID"]
```

並將 `.env` 加入 `.gitignore`。

### 11.3 LINE Webhook 驗證

`webhook.py` 使用 LINE SDK 的 `WebhookHandler` 驗證每個 Webhook 請求的 `X-Line-Signature`，確保請求來自 LINE 官方平台，防止偽造請求。

---

## 12. 已知限制與未來改善方向

### 12.1 目前限制

| 限制 | 影響 | 描述 |
|------|------|------|
| 單一推播目標 | 中 | `LINE_USER_ID` 寫死，只能推播給一位使用者 |
| ngrok 限制 | 中 | ngrok 免費版每次重啟 URL 改變，需重新設定 Webhook |
| 無排程可靠性保證 | 中 | 若電腦關機，Windows 工作排程器不執行 |
| SQLite 無並行控制 | 低 | 若多個程序同時寫入可能發生鎖定 |
| 對話歷史存於記憶體 | 低 | 伺服器重啟後對話歷史消失 |
| 無重試機制 | 低 | API 呼叫失敗時不自動重試 |

### 12.2 建議未來改善

| 方向 | 優先級 | 說明 |
|------|--------|------|
| 敏感憑證移至 `.env` | 高 | 避免洩漏至版本控制 |
| 支援多位使用者 | 中 | 將 LINE_USER_ID 改為可配置的列表 |
| 容器化部署 (Docker) | 中 | 確保跨環境一致性，解決 ngrok 問題 |
| 雲端部署 (GCP/AWS) | 中 | 使用 Cloud Run 或 EC2 替代本地電腦，提升可靠性 |
| 對話歷史持久化 | 低 | 將 `conversation_histories` 儲存至 SQLite |
| 新增 Reply API | 低 | Webhook 即時回覆使用 Reply API 降低成本 |
| 加入 LLM 重試邏輯 | 低 | API 呼叫失敗時指數退避重試 |
| 監控與告警 | 低 | 每日流程失敗時發送告警訊息 |
| 單元測試 | 低 | 為各模組撰寫測試案例 |

---

*文件結束*

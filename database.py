import sqlite3
import chromadb
from datetime import datetime, timedelta
from config import DB_PATH, CHROMA_DIR

# ── ChromaDB 向量資料庫 ──────────────────────────────────────────
_chroma_client     = None
_chroma_collection = None
_report_collection = None

def get_chroma_client():
    """取得（或建立）共用的 ChromaDB PersistentClient。"""
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
    return _chroma_client


def get_vector_collection():
    """取得（或建立）文章的 ChromaDB collection，使用 cosine 相似度。"""
    global _chroma_collection
    if _chroma_collection is None:
        _chroma_collection = get_chroma_client().get_or_create_collection(
            name="news_articles",
            metadata={"hnsw:space": "cosine"}
        )
    return _chroma_collection


def get_report_collection():
    """取得（或建立）報告的 ChromaDB collection，使用 cosine 相似度。"""
    global _report_collection
    if _report_collection is None:
        _report_collection = get_chroma_client().get_or_create_collection(
            name="news_reports",
            metadata={"hnsw:space": "cosine"}
        )
    return _report_collection


def save_article_embeddings(articles: list[dict], embeddings: list[list[float]]):
    """
    將文章的向量存入 ChromaDB。
    用 URL 當作 ID，天然去重（同一篇文章重複跑不會存兩次）。
    """
    collection = get_vector_collection()
    ids, vecs, docs, metas = [], [], [], []

    for article, embedding in zip(articles, embeddings):
        url = article.get("url", "")
        if not url:
            continue
        # ChromaDB ID 不能有特殊字元，用 hash 處理
        doc_id = str(abs(hash(url)))
        ids.append(doc_id)
        vecs.append(embedding)
        docs.append(f"{article.get('title', '')}\n{article.get('content', '')}")
        metas.append({
            "source":     article.get("source", ""),
            "title":      article.get("title", ""),
            "url":        url,
            "time":       article.get("time", ""),
            "fetched_at": datetime.now().strftime("%Y-%m-%d"),
        })

    if ids:
        # upsert：已存在的 ID 會更新，不會重複
        collection.upsert(ids=ids, embeddings=vecs, documents=docs, metadatas=metas)
        print(f"[Vector DB] 已儲存 {len(ids)} 篇文章的向量")


def save_report_embedding(date_str: str, content: str, embedding: list[float]):
    """
    將報告向量存入 ChromaDB。
    用日期字串當 ID，同一天重跑會 upsert 更新，不會重複。
    """
    collection = get_report_collection()
    doc_id = str(abs(hash(date_str)))
    collection.upsert(
        ids=[doc_id],
        embeddings=[embedding],
        documents=[content],
        metadatas=[{"date": date_str}]
    )
    print(f"[Vector DB] 已儲存報告向量（{date_str}）")


def search_similar_reports(query_embedding: list[float], n_results: int = 2) -> list[dict]:
    """
    用向量相似度搜尋最相關的歷史報告，回傳含 date/content 的 list。
    """
    collection = get_report_collection()
    total = collection.count()
    if total == 0:
        return []

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, total),
        include=["documents", "metadatas"]
    )

    reports = []
    for meta, doc in zip(results["metadatas"][0], results["documents"][0]):
        reports.append({
            "date":    meta.get("date", ""),
            "content": doc,
        })
    return reports


def search_similar_articles(query_embedding: list[float], n_results: int = 5) -> list[dict]:
    """
    用向量相似度搜尋最相關的文章，回傳含 source/title/url/time/content 的 list。
    """
    collection = get_vector_collection()
    total = collection.count()
    if total == 0:
        return []

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, total),
        include=["documents", "metadatas"]
    )

    articles = []
    for meta, doc in zip(results["metadatas"][0], results["documents"][0]):
        articles.append({
            "source":  meta.get("source", ""),
            "title":   meta.get("title", ""),
            "url":     meta.get("url", ""),
            "time":    meta.get("time", ""),
            "content": doc,
        })
    return articles

def get_connection():
    """取得資料庫連線"""
    return sqlite3.connect(DB_PATH)

def init_db():
    """
    初始化資料庫：如果資料表不存在就建立。
    程式每次啟動都會呼叫，但已存在的表不會被清空。
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 文章表：儲存每篇爬到的新聞
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            source      TEXT,        -- 來源（Yahoo / udn / 自由時報）
            title       TEXT,        -- 標題
            url         TEXT,        -- 網址
            time        TEXT,        -- 發布時間（原始字串）
            content     TEXT,        -- 文章內文
            fetched_at  TEXT         -- 本次抓取時間
        )
    """)

    # 報告表：儲存每次 Gemini 產出的摘要
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at  TEXT,        -- 報告產出時間
            content     TEXT,        -- Gemini 的完整回覆
            type        TEXT DEFAULT 'daily'   -- 報告類型：daily / weekly
        )
    """)

    # 遷移：舊資料庫缺少 type 欄時自動補上
    try:
        cursor.execute("ALTER TABLE reports ADD COLUMN type TEXT DEFAULT 'daily'")
    except Exception:
        pass  # 欄位已存在時 SQLite 會丟例外，直接略過

    # 建立 UNIQUE INDEX 前先清除既有重複資料（保留 id 最小的那筆）
    cursor.execute("""
        DELETE FROM articles WHERE id NOT IN (
            SELECT MIN(id) FROM articles GROUP BY url
        )
    """)
    # url 加 UNIQUE 約束，讓 INSERT OR IGNORE 真正起作用
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_url ON articles(url)
    """)
    # 在 fetched_at 加索引，之後查詢會更快
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_fetched_at ON articles(fetched_at)
    """)

    # 使用者表：儲存曾傳訊息的 LINE user_id，以頻道區分
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id    TEXT,
            channel_id TEXT,
            added_at   TEXT,
            PRIMARY KEY (user_id, channel_id)
        )
    """)

    # 遷移：舊資料庫缺少 channel_id 欄時自動補上
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN channel_id TEXT DEFAULT ''")
    except Exception:
        pass

    conn.commit()
    conn.close()
    print("[Database] 初始化完成")

def save_articles(articles):
    """
    將這次爬到的文章存進 articles 表。
    不做去重，去重是工具B的工作；
    資料庫存的是工具B整理後的乾淨資料。
    """
    if not articles:
        return

    conn = get_connection()
    cursor = conn.cursor()
    fetched_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for a in articles:
        cursor.execute("""
            INSERT OR IGNORE INTO articles
                (source, title, url, time, content, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            a.get("source",  ""),
            a.get("title",   ""),
            a.get("url",     ""),
            a.get("time",    ""),
            a.get("content", ""),
            fetched_at
        ))

    conn.commit()
    conn.close()
    with_content = sum(1 for a in articles if a.get("content", ""))
    print(f"[Database] 已儲存 {len(articles)} 篇文章（含內文：{with_content} 篇）")

def get_cached_content(url: str) -> str | None:
    """
    查詢 DB 中是否已有此 URL 的內文。
    有則回傳內文字串，沒有則回傳 None。
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT content FROM articles WHERE url = ? AND content != ''", (url,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def save_report(content, report_type: str = "daily"):
    """將 Gemini 的摘要報告存進 reports 表。
    report_type: 'daily'（預設）或 'weekly'
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO reports (created_at, content, type)
        VALUES (?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        content,
        report_type
    ))

    conn.commit()
    conn.close()
    print(f"[Database] {report_type} 報告已儲存")


def save_user_id(user_id: str, channel_id: str = ""):
    """將 LINE user_id 存入 users 表，已存在則略過。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO users (user_id, channel_id, added_at)
        VALUES (?, ?, ?)
    """, (user_id, channel_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()


def remove_user_id(user_id: str, channel_id: str = ""):
    """將 LINE user_id 從 users 表移除（封鎖或刪除好友時呼叫）。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE user_id = ? AND channel_id = ?", (user_id, channel_id))
    conn.commit()
    conn.close()


def get_all_user_ids(channel_id: str = "") -> list[str]:
    """取得指定頻道的所有已登錄 LINE user_id。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE channel_id = ?", (channel_id,))
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]


def get_recent_daily_reports(days: int = 7) -> list[dict]:
    """
    取得最近 N 天內的 daily 報告（預設 7 天）。
    回傳 list of dict，每筆含 'created_at' 與 'content'。
    """
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT created_at, content
        FROM   reports
        WHERE  type = 'daily'
          AND  created_at >= ?
        ORDER BY id DESC
    """, (cutoff,))
    rows = cursor.fetchall()
    conn.close()
    return [{"created_at": row[0], "content": row[1]} for row in rows]
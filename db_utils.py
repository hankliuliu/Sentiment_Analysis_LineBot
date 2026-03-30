"""
db_utils.py — 資料庫管理工具

用法：
  python db_utils.py status          # 查看目前資料量
  python db_utils.py clear-articles  # 清空文章（SQLite + ChromaDB）
  python db_utils.py clear-reports   # 清空報告
  python db_utils.py clear-all       # 清空全部
"""

import sys
import sqlite3
import shutil
import os
from config import DB_PATH, CHROMA_DIR

CHROMA_PATH = CHROMA_DIR


def get_conn():
    return sqlite3.connect(DB_PATH)


# ── 查看狀態 ─────────────────────────────────────────

def _get_chroma_client():
    import chromadb
    return chromadb.PersistentClient(path=CHROMA_PATH)


def status():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM articles")
    articles = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM reports")
    reports_total = cursor.fetchone()[0]
    try:
        cursor.execute("SELECT COUNT(*) FROM reports WHERE type = 'daily'")
        reports_daily = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM reports WHERE type = 'weekly'")
        reports_weekly = cursor.fetchone()[0]
    except Exception:
        reports_daily = reports_weekly = -1
    cursor.execute("SELECT MIN(fetched_at), MAX(fetched_at) FROM articles")
    date_range = cursor.fetchone()
    conn.close()

    articles_vec = reports_vec = 0
    if os.path.exists(CHROMA_PATH):
        try:
            client = _get_chroma_client()
            articles_vec = client.get_or_create_collection("news_articles").count()
            reports_vec  = client.get_or_create_collection("news_reports").count()
        except Exception:
            articles_vec = reports_vec = -1

    print("=== 資料庫狀態 ===")
    print(f"SQLite   文章數：{articles} 篇")
    print(f"         報告數：{reports_total} 份")
    if reports_daily >= 0:
        print(f"           ├─ 日報：{reports_daily} 份")
        print(f"           └─ 週報：{reports_weekly} 份")
    if date_range[0]:
        print(f"         資料範圍：{date_range[0]} ～ {date_range[1]}")
    print(f"ChromaDB 文章向量：{articles_vec if articles_vec >= 0 else '讀取失敗'} 筆")
    print(f"         報告向量：{reports_vec  if reports_vec  >= 0 else '讀取失敗'} 筆")


# ── 清空操作 ─────────────────────────────────────────

def clear_articles():
    """清空 SQLite articles 表 + ChromaDB news_articles collection。"""
    conn = get_conn()
    conn.execute("DELETE FROM articles")
    conn.commit()
    conn.close()
    print("[SQLite] articles 表已清空")

    if os.path.exists(CHROMA_PATH):
        try:
            _get_chroma_client().delete_collection("news_articles")
            print("[ChromaDB] news_articles collection 已清空")
        except Exception as e:
            print(f"[ChromaDB] 清空失敗：{e}")
    else:
        print("[ChromaDB] 無資料，略過")


def clear_reports():
    """清空 SQLite reports 表 + ChromaDB news_reports collection。"""
    conn = get_conn()
    conn.execute("DELETE FROM reports")
    conn.commit()
    conn.close()
    print("[SQLite] reports 表已清空")

    if os.path.exists(CHROMA_PATH):
        try:
            _get_chroma_client().delete_collection("news_reports")
            print("[ChromaDB] news_reports collection 已清空")
        except Exception as e:
            print(f"[ChromaDB] 清空失敗：{e}")
    else:
        print("[ChromaDB] 無資料，略過")


def clear_all():
    """清空所有資料。"""
    conn = get_conn()
    conn.execute("DELETE FROM articles")
    conn.execute("DELETE FROM reports")
    conn.commit()
    conn.close()
    print("[SQLite] 所有表已清空")

    if os.path.exists(CHROMA_PATH):
        shutil.rmtree(CHROMA_PATH)
        print("[ChromaDB] chroma_db 資料夾已刪除")
    else:
        print("[ChromaDB] 無資料，略過")
    print("所有資料已清空。")


# ── 主程式 ───────────────────────────────────────────

COMMANDS = {
    "status":         (status,         "查看目前資料量"),
    "clear-articles": (clear_articles, "清空文章（SQLite articles + ChromaDB）"),
    "clear-reports":  (clear_reports,  "清空報告（SQLite reports）"),
    "clear-all":      (clear_all,      "清空全部資料"),
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("用法：python db_utils.py <指令>\n")
        print("可用指令：")
        for cmd, (_, desc) in COMMANDS.items():
            print(f"  {cmd:<18} {desc}")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd.startswith("clear"):
        confirm = input(f"確定執行「{cmd}」？輸入 y 確認：").strip().lower()
        if confirm != "y":
            print("已取消。")
            sys.exit(0)

    COMMANDS[cmd][0]()

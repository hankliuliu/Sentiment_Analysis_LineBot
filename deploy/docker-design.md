# Docker 改版設計文件

## 專案現況

### 程序類型

| 程序 | 性質 | 說明 |
|------|------|------|
| `webhook.py` | 長期運行服務 | Flask + gunicorn，等待 LINE 傳入訊息 |
| `main.py` | 排程批次任務 | 每日新聞爬取、分析、推播 |
| `weekly.py` | 排程批次任務 | 每週報告合成 |

### 共用資料

| 資料 | 類型 | 讀寫方 |
|------|------|--------|
| `sentiment.db` | SQLite（檔案型） | webhook + main + weekly |
| `chroma_db/` | ChromaDB（檔案型向量 DB） | webhook + main |
| `reports/` | 文字檔 | main 寫入，webhook 可能讀取 |
| `logs/` | Log 檔 | gunicorn、cron 寫入 |

---

## 設計決策

### 1. 幾個 container？

**決策：一個 container**

考量過兩種做法：

| 方案 | 說明 | 問題 |
|------|------|------|
| 單一 container | webhook 常駐，cron 透過 `docker exec` 進去執行 | 無 |
| 兩個 container | webhook 一個，排程任務一個 | SQLite 不支援跨 container 同時讀寫，共掛同一個 `sentiment.db` 會 deadlock 或資料損毀 |

SQLite 是檔案鎖機制，兩個 process 同時寫入同一個檔案已有風險，跨 container 更無法保護。

### 2. 排程任務怎麼跑？

**決策：host crontab + `docker exec`**

考量過三種做法：

| 方案 | 說明 | 問題 |
|------|------|------|
| host crontab + `docker exec` | cron 在主機，指令進入 container 執行 | 需要 container 持續運行且名稱固定 |
| cron 裝在 container 內 | container 自己管排程 | 違反 Docker 單一職責原則，Dockerfile 複雜 |
| 獨立排程 container | 另起一個 container 專跑 cron | 回到上面的 SQLite 跨 container 問題 |

### 3. nginx 和 HTTPS 放在哪？

**決策：不需要 nginx，Traefik 直接路由到 container**

這台 server 是共用機器，前面已有 Traefik 統一管理 HTTPS（port 443）和 SSL 終止。
Traefik 依 domain 把流量路由到各服務分配的 port，下游只需接 HTTP。

本服務分配到 **port 9086**，Traefik 把流量送到 `host:9086`，docker-compose 把 `host:9086` 對應到 `container:5000`。

```
外部 HTTPS :443 → Traefik（SSL 終止）→ host:9086 → container:5000
```

`nginx.conf` 不需要，已移除。

### 4. torch 安裝方式

`torch==2.5.1` 預設裝含 CUDA 的版本（約 2.5GB）。Mac 和這台 server 都沒有 NVIDIA GPU。

`requirements.txt` 裡直接加 `--extra-index-url` 指令，讓任何人 `pip install -r requirements.txt` 都自動裝 CPU 版：

```
--extra-index-url https://download.pytorch.org/whl/cpu
torch==2.5.1
```

ARM64（Apple Silicon）上此 URL 沒有對應 wheel，pip 會自動 fallback 到 PyPI，行為正常。

### 5. 時區

container 預設 UTC，台灣是 UTC+8。
log 時間、排程時間都會差 8 小時，需在 docker-compose.yaml 設定：

```yaml
environment:
  - TZ=Asia/Taipei
```

---

## 目標架構

```
外部請求（LINE Server）
    ↓ HTTPS :443
Traefik（共用，SSL 終止）
    ↓ HTTP，路由到 host:9086
container sentiment-bot（127.0.0.1:9086 → container:5000）
    ├── gunicorn（常駐）
    │     └── webhook.py（Flask）
    ├── main.py（每日 21:00，由主機 cron 透過 docker exec 呼叫）
    └── weekly.py（每週一 09:00，同上）

Volumes（掛在主機，container 讀寫）
    ├── sentiment.db
    ├── chroma_db/
    ├── reports/
    └── logs/
```

---

## 需要新增 / 修改的檔案

| 檔案 | 動作 | 說明 |
|------|------|------|
| `Dockerfile` | 新增 | 定義 container 環境 |
| `docker-compose.yaml` | 新增 | 定義 container 設定、volumes、port |
| `.dockerignore` | 新增 | 排除不必要的檔案進 image |
| `deploy/crontab.txt` | 修改 | 改用 `docker exec` 呼叫 |
| `deploy/nginx.conf` | 移除 | Traefik 直接路由，不需要 nginx |

---

## 已知風險與注意事項

### sentiment.db 掛載問題
volume 掛載單一檔案時，若主機上該檔案不存在，Docker 會建立一個**同名目錄**，導致程式讀取失敗。
**處理方式**：啟動前確認 `sentiment.db` 存在，若無則先 `touch sentiment.db`。

### gunicorn 啟動時 init_db() 已執行
`webhook.py` 最底部有 `init_db()`，gunicorn 載入 app 時就會執行，會自動建立 SQLite 資料表。
若 `sentiment.db` 是空檔案，這是正常的。若是從舊 server 移過來的，不影響。

### docker exec 的 cron log
主機 crontab 用 `docker exec` 執行時，log 路徑需指向主機上的實際路徑（volume 掛載點），
不能用 container 內部路徑，否則 log 跑到主機但找不到對應目錄。
**處理方式**：crontab 的 log 路徑直接用主機上的 `logs/` 絕對路徑。

### container 重啟後 cron 會繼續運作
`docker exec` 依賴 container 名稱，只要 `docker-compose.yaml` 裡設定 `container_name: sentiment-bot` 且 `restart: always`，重啟後名稱不變，cron 不受影響。

### ChromaDB thread-safety
程式碼中已有註解說明 ChromaDB global client 非 thread-safe，webhook 已序列化向量搜尋。
cron job 是獨立 process，與 gunicorn worker 不共享記憶體，不會互相干擾。
但兩者同時寫入 `chroma_db/` 時仍有檔案層級衝突風險（機率低，因 cron 每日只跑一次）。

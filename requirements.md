# KnowledgeDeck AI Platform Requirements

## 1. 專案概述

KnowledgeDeck AI Platform 是一套支援企業或個人使用的 AI 應用平台，主要目標是整合大型語言模型、RAG 知識庫、文件管理、簡報生成與多使用者帳號管理功能。

平台需支援使用者上傳文件建立個人或共用知識庫，並透過 LLM 進行具備引用來源的問答。同時，平台也需支援使用者透過自然語言描述簡報需求，結合 RAG 內容與上傳範本，自動產生可編輯的 PPTX 簡報。

本系統預期可部署於內部環境，支援 Docker 化部署，並可整合 vLLM、Qdrant、LangChain、LangGraph、React 等技術。

---

## 2. 專案目標

### 2.1 核心目標

- 建立一個可支援 LLM 對話、RAG 問答與簡報製作的 AI 平台。
- 支援使用者管理自己的知識庫資料。
- 支援管理員建立全域共用知識庫。
- 支援有來源引用的 RAG 回答。
- 支援根據使用者需求與知識庫內容產生 PPTX 簡報。
- 支援多輪對話與 streaming 回應。
- 支援帳號、權限、登入紀錄與對話歷史管理。
- 支援 Docker 化部署，方便內部環境建置與維護。

### 2.2 使用情境

使用者可以透過平台完成以下任務：

- 上傳 PDF、PPTX、DOCX、TXT、Markdown 等文件作為知識庫資料。
- 針對已上傳的文件進行問答。
- 查看回答引用的來源檔案與位置。
- 要求 AI 根據知識庫內容產生簡報大綱。
- 要求 AI 產生完整 PPTX 簡報。
- 上傳既有 PPTX 作為簡報風格或格式範本。
- 透過多輪對話修改簡報內容、頁數、版型與語氣。
- 管理自己的知識庫與歷史對話。
- 管理員可建立組織共用知識庫供其他使用者查詢。

---

## 3. 使用者角色

### 3.1 一般使用者 User

一般使用者可以：

- 登入與登出系統。
- 使用 LLM 對話功能。
- 使用個人 RAG 知識庫。
- 上傳、刪除、更新自己的文件。
- 查看自己的文件處理狀態。
- 查詢自己的歷史對話。
- 產生與下載 PPTX 簡報。
- 上傳 PPTX / PDF 作為簡報範本。
- 管理自己的簡報生成紀錄。

### 3.2 管理員 Admin

管理員可以：

- 管理使用者帳號。
- 查看使用者登入與登出紀錄。
- 管理全域共用 RAG 知識庫。
- 上傳、刪除、更新共用知識庫文件。
- 檢視系統使用紀錄。
- 管理模型設定。
- 管理向量資料庫狀態。
- 管理系統設定與權限。

---

## 4. 功能需求

---

## 4.1 LLM 對話功能

### 4.1.1 基本對話

系統需支援使用者與 LLM 進行自然語言對話。

### 功能需求

- 支援文字輸入。
- 支援 streaming 回應。
- 支援多輪對話。
- 支援上下文記憶。
- 支援重新生成回答。
- 支援停止生成。
- 支援複製回答。
- 支援儲存對話紀錄。
- 支援切換是否使用 RAG。

### 4.1.2 Streaming 回應

LLM 回答需支援 streaming 模式，讓使用者可以即時看到模型輸出。

### 功能需求

- 前端需即時顯示 token 或 chunk。
- 後端需支援 Server-Sent Events 或 WebSocket。
- 使用者可中途停止生成。
- 若生成失敗，需顯示錯誤訊息。

---

## 4.2 RAG 知識庫功能

### 4.2.1 知識庫管理

系統需支援使用者建立與管理自己的 RAG 知識庫。

### 功能需求

- 使用者可以上傳文件。
- 使用者可以刪除文件。
- 使用者可以重新處理文件。
- 使用者可以查看文件處理狀態。
- 使用者可以查看文件是否已加入向量資料庫。
- 使用者可以設定文件是否啟用於 RAG 檢索。
- 使用者可以依照檔名、上傳時間、狀態搜尋文件。

### 4.2.2 支援文件格式

第一階段建議支援：

- PDF
- PPTX
- DOCX
- TXT
- Markdown
- CSV
- XLSX

第二階段可擴充支援：

- HTML
- 圖片 OCR
- 掃描 PDF
- 音訊逐字稿
- 企業內部資料庫資料

### 4.2.3 文件處理流程

文件上傳後，系統需進行以下處理：

1. 儲存原始檔案。
2. 解析文件內容。
3. 擷取文字、表格與頁碼資訊。
4. 依照段落或語意進行 chunking。
5. 建立 metadata。
6. 產生 embedding。
7. 寫入向量資料庫。
8. 建立檔案與 chunk 的引用對應。
9. 更新文件處理狀態。

### 4.2.4 Retrieval 檢索

系統需能根據使用者問題從知識庫中找出相關資料。

### 功能需求

- 支援向量檢索。
- 支援關鍵字檢索。
- 支援 hybrid retrieval。
- 支援 top-k 設定。
- 支援 metadata filter。
- 支援個人知識庫與共用知識庫混合查詢。
- 支援依文件類型、上傳者、時間範圍過濾。
- 支援 reranking。

### 4.2.5 引用來源 Citation

RAG 回答必須清楚標示資料來源。

### Citation 需求

每一段引用需包含：

- 檔案名稱。
- 文件類型。
- 頁碼或 slide 編號。
- chunk 位置。
- 原始段落摘要。
- 可點擊回到原始文件或預覽位置。

### 回答範例

```text
根據公司年度報告，2024 年主要營收成長來自海外市場擴張。

引用來源：
[1] 2024_annual_report.pdf, p.12
[2] market_strategy.pptx, slide 5
````

---

## 4.3 LLM 簡報製作功能

### 4.3.1 簡報生成

系統需支援使用者透過自然語言產生 PPTX 簡報。

### 使用者輸入範例

```text
請幫我根據知識庫中的 AI 專案資料，製作一份 10 頁的技術簡報，對象是主管，風格要專業簡潔。
```

### 功能需求

* 支援使用者輸入簡報主題。
* 支援使用者輸入簡報大綱。
* 支援使用者指定簡報頁數。
* 支援使用者指定簡報語言。
* 支援使用者指定簡報對象。
* 支援使用者指定簡報風格。
* 支援使用 RAG 知識庫內容生成簡報。
* 支援產生可下載的 PPTX。
* PPTX 內的文字、圖表、圖片需盡量保持可編輯。

### 4.3.2 簡報生成流程

建議流程如下：

1. 使用者輸入簡報需求。
2. 系統判斷是否需要 RAG。
3. 從知識庫檢索相關內容。
4. LLM 產生簡報大綱。
5. 使用者確認或修改大綱。
6. LLM 產生每頁 slide 內容。
7. 系統套用簡報模板。
8. 產生 PPTX。
9. 使用者下載或繼續修改。

### 4.3.3 多輪簡報修改

系統需支援使用者透過對話方式修改簡報。

### 修改範例

```text
幫我把第 3 頁改成技術架構圖。
```

```text
幫我把整份簡報改得更適合主管簡報。
```

```text
幫我增加一頁競品比較。
```

### 功能需求

* 支援針對特定頁面修改。
* 支援整體風格修改。
* 支援新增頁面。
* 支援刪除頁面。
* 支援重新排列頁面。
* 支援修改標題、段落、表格、圖片與圖表。
* 支援重新產生 PPTX。
* 支援保留修改歷史。

### 4.3.4 簡報範本支援

系統需支援使用者上傳 PPTX 或 PDF 作為簡報範本。

### 功能需求

* 使用者可上傳 PPTX 作為版型範本。
* 使用者可上傳 PDF 作為風格參考。
* 系統可解析 PPTX 中的版型、配色、字體與頁面結構。
* 產生的新簡報需套用使用者提供的範本風格。
* 簡報內容仍需依照使用者需求與 RAG 結果重新產生。
* 不應直接複製範本中的舊內容，除非使用者明確要求保留。

### 4.3.5 簡報輸出格式

第一階段必須支援：

* PPTX

第二階段可支援：

* PDF
* Markdown
* HTML
* 圖片匯出

---

## 4.4 UI / UX 需求

### 4.4.1 整體介面

UI 可參考 Open WebUI 形式。

### 主要 Layout

* 左側：聊天歷史紀錄。
* 中間 / 右側：主要對話區。
* 上方：模型選擇、知識庫選擇、使用者資訊。
* 側邊功能：RAG 管理、簡報管理、帳號管理。

### 4.4.2 聊天介面

聊天介面需包含：

* 對話輸入框。
* Streaming 回應區。
* 是否啟用 RAG 的切換。
* 選擇知識庫。
* 上傳附件。
* 生成中停止按鈕。
* 重新生成按鈕。
* 複製回答按鈕。
* 顯示引用來源。
* 顯示目前使用的模型。

### 4.4.3 RAG 管理介面

RAG 管理介面需包含：

* 文件上傳區。
* 文件列表。
* 文件狀態。
* 文件啟用 / 停用。
* 文件刪除。
* 文件重新處理。
* 知識庫分類。
* 個人知識庫與共用知識庫切換。
* 檢索測試功能。

### 4.4.4 簡報管理介面

簡報管理介面需包含：

* 簡報生成紀錄。
* 簡報下載。
* 簡報重新生成。
* 簡報版本紀錄。
* 範本上傳。
* 簡報預覽。
* 簡報頁面列表。
* 單頁修改功能。

### 4.4.5 帳號管理介面

帳號管理介面需包含：

* 使用者列表。
* 新增使用者。
* 停用使用者。
* 角色管理。
* 登入紀錄。
* 登出紀錄。
* 使用者知識庫使用情況。
* 使用者對話歷史查詢。

---

## 4.5 帳戶與權限管理

### 4.5.1 登入 / 登出

系統需支援帳號登入與登出。

### 功能需求

* 使用者需登入後才能使用系統。
* 系統需記錄登入時間。
* 系統需記錄登出時間。
* 系統需記錄 IP 或裝置資訊。
* 支援 session 管理。
* 支援 token 驗證。

### 4.5.2 使用者資料隔離

每個使用者需擁有獨立資料空間。

### 隔離項目

* 個人 RAG 文件。
* 個人向量資料。
* 個人對話歷史。
* 個人簡報生成紀錄。
* 個人上傳範本。

### 4.5.3 Admin 共用資料

Admin 可建立共用 RAG 知識庫。

### 功能需求

* Admin 可上傳共用文件。
* Admin 可刪除共用文件。
* Admin 可設定哪些使用者可使用共用知識庫。
* 一般使用者可以查詢共用知識庫，但不可修改。
* 共用知識庫可與個人知識庫一起進行檢索。

---

## 5. 系統架構需求

## 5.1 建議架構

系統可分為以下模組：

1. Frontend Web UI
2. Backend API Server
3. LLM Service
4. RAG Service
5. Document Processing Service
6. Slide Generation Service
7. Vector Database
8. Relational Database
9. Object Storage
10. Authentication Service

---

## 5.2 Frontend

### 建議技術

* React
* Next.js
* TypeScript
* Tailwind CSS
* Ant Design 或 shadcn/ui

### 前端需求

* 支援聊天介面。
* 支援 streaming 顯示。
* 支援文件上傳。
* 支援 PPTX 下載。
* 支援 RAG 管理頁面。
* 支援帳號管理頁面。
* 支援簡報管理頁面。
* 支援登入頁面。

---

## 5.3 Backend

### 建議技術

* FastAPI 或 Django REST Framework
* Python
* WebSocket 或 Server-Sent Events
* Celery / RQ / Dramatiq 作為背景任務工具

### 後端需求

* 提供 REST API。
* 提供 streaming API。
* 管理使用者資料。
* 管理對話歷史。
* 管理文件上傳與處理。
* 管理 RAG 查詢。
* 管理簡報生成。
* 管理權限。
* 管理系統設定。

---

## 5.4 LLM Service

### 建議技術

* vLLM
* OpenAI-compatible API
* 可替換成本地模型或外部模型

### 功能需求

* 支援 streaming。
* 支援多模型設定。
* 支援模型切換。
* 支援溫度、max tokens 等參數設定。
* 支援 RAG prompt 組裝。
* 支援簡報生成 prompt。
* 支援 structured output。

---

## 5.5 RAG Service

### 建議技術

* LangChain
* LangGraph
* LlamaIndex，可選
* Qdrant
* PostgreSQL

### 功能需求

* 文件 chunking。
* embedding 生成。
* 向量檢索。
* hybrid retrieval。
* reranking。
* citation mapping。
* prompt 組裝。
* 權限過濾。
* 個人與共用知識庫檢索。

---

## 5.6 Vector Store

### 建議技術

優先建議：

* Qdrant

替代方案：

* PostgreSQL + pgvector
* Milvus
* Weaviate
* Chroma

### 儲存內容

每個 chunk 需儲存：

* chunk_id
* user_id
* knowledge_base_id
* file_id
* file_name
* file_type
* page_number
* slide_number
* chunk_text
* embedding
* metadata
* created_at
* updated_at

---

## 5.7 Relational Database

### 建議技術

* PostgreSQL

### 主要資料表

* users
* roles
* login_logs
* chat_sessions
* chat_messages
* files
* knowledge_bases
* document_chunks
* slide_projects
* slide_versions
* templates
* system_settings

---

## 5.8 Object Storage

### 建議技術

* MinIO

### 儲存內容

* 原始上傳文件。
* 解析後的中間檔。
* 產生的 PPTX。
* 上傳的簡報範本。
* 圖片與附加檔案。

---

## 5.9 Slide Generation Service

### 建議技術

* python-pptx
* pptxgenjs
* LibreOffice，可用於轉 PDF 預覽
* 自定義 layout engine

### 功能需求

* 根據 LLM 產生的 slide JSON 建立 PPTX。
* 支援可編輯文字框。
* 支援表格。
* 支援圖片。
* 支援基本圖表。
* 支援範本套用。
* 支援多版本輸出。
* 支援下載 PPTX。

---

## 6. API 需求

### 6.1 Auth API

* POST /auth/login
* POST /auth/logout
* GET /auth/me

### 6.2 Chat API

* POST /chat
* POST /chat/stream
* GET /chat/sessions
* GET /chat/sessions/{id}
* DELETE /chat/sessions/{id}

### 6.3 RAG API

* POST /knowledge-bases
* GET /knowledge-bases
* POST /knowledge-bases/{id}/files
* GET /knowledge-bases/{id}/files
* DELETE /files/{id}
* POST /rag/query
* POST /rag/reindex

### 6.4 Slide API

* POST /slides/projects
* POST /slides/generate
* POST /slides/stream
* GET /slides/projects
* GET /slides/projects/{id}
* POST /slides/projects/{id}/revise
* GET /slides/projects/{id}/download
* POST /slides/templates

### 6.5 Admin API

* GET /admin/users
* POST /admin/users
* PATCH /admin/users/{id}
* GET /admin/login-logs
* GET /admin/system-status
* POST /admin/shared-knowledge-bases

---

## 7. 非功能需求

## 7.1 安全性

* 使用者資料需依 user_id 隔離。
* API 需驗證使用者權限。
* Admin API 僅限管理員使用。
* 上傳檔案需限制檔案大小與格式。
* 應避免任意檔案執行。
* 應避免 prompt injection 直接操作系統。
* RAG 檢索需套用權限過濾。
* Token 或 session 需具備過期機制。

## 7.2 效能

* LLM 回答需支援 streaming。
* 文件處理需使用背景任務。
* 大檔案處理不可阻塞主要 API。
* RAG 查詢需在合理時間內回傳。
* 簡報生成需顯示處理進度。
* 向量檢索需支援索引最佳化。

## 7.3 可維護性

* 前後端分離。
* 模組化設計。
* LLM、Vector DB、Embedding Model 可替換。
* 文件處理器可擴充。
* Prompt 模板需集中管理。
* 系統設定需可透過環境變數調整。

## 7.4 可部署性

* 使用 Docker Compose 部署。
* 支援本機部署。
* 支援內部伺服器部署。
* 可設定是否使用 GPU。
* 可設定 vLLM endpoint。
* 可設定 Qdrant endpoint。
* 可設定 MinIO endpoint。
* 可設定 PostgreSQL endpoint。

---

## 8. 建議 Docker Compose 服務

第一階段建議包含：

* frontend
* backend
* postgres
* qdrant
* minio
* redis
* worker
* vllm

### 服務說明

| Service  | 說明                        |
| -------- | ------------------------- |
| frontend | React / Next.js 前端        |
| backend  | FastAPI / Django REST API |
| postgres | 儲存使用者、對話、檔案 metadata      |
| qdrant   | 向量資料庫                     |
| minio    | 儲存原始文件與 PPTX              |
| redis    | 任務佇列與快取                   |
| worker   | 文件處理與簡報生成背景任務             |
| vllm     | 本地 LLM inference service  |

---

## 9. 建議資料流程

## 9.1 RAG 文件上傳流程

```text
User Upload File
    ↓
Backend Receive File
    ↓
Store Original File to MinIO
    ↓
Create File Metadata in PostgreSQL
    ↓
Send Processing Job to Worker
    ↓
Parse Document
    ↓
Chunk Document
    ↓
Generate Embeddings
    ↓
Store Vectors in Qdrant
    ↓
Update File Status
```

## 9.2 RAG 問答流程

```text
User Question
    ↓
Select Knowledge Base
    ↓
Permission Filtering
    ↓
Hybrid Retrieval
    ↓
Reranking
    ↓
Build Context with Citations
    ↓
LLM Streaming Answer
    ↓
Return Answer + Citation Sources
```

## 9.3 簡報生成流程

```text
User Slide Request
    ↓
Analyze Requirement
    ↓
Retrieve RAG Context
    ↓
Generate Slide Outline
    ↓
Generate Slide-by-Slide Content
    ↓
Apply Template
    ↓
Generate Editable PPTX
    ↓
Save Version
    ↓
User Download or Revise
```

---

## 10. MVP 範圍

第一階段 MVP 建議先完成以下功能：

### 10.1 必要功能

* 使用者登入 / 登出。
* LLM streaming 對話。
* 使用者上傳 PDF / PPTX / DOCX。
* 文件解析與 embedding。
* 個人 RAG 知識庫。
* RAG 問答與 citation。
* 對話歷史紀錄。
* PPTX 簡報生成。
* PPTX 下載。
* 基本 RAG 管理頁面。
* Docker Compose 部署。

### 10.2 可延後功能

* Admin 共用知識庫。
* 多角色細緻權限。
* 進階簡報範本解析。
* 簡報線上編輯器。
* PDF 預覽與 citation 點擊定位。
* Hybrid retrieval。
* Reranker。
* 多模型管理介面。
* 使用量統計 dashboard。

---

## 11. 第二階段功能

第二階段可加入：

* 共用知識庫。
* 群組權限。
* 文件版本管理。
* RAG 評估功能。
* Prompt 模板管理。
* 多模型切換。
* 簡報線上預覽。
* 簡報單頁修改。
* Citation 點擊回原文。
* 表格型資料分析。
* 使用者操作紀錄分析。
* 系統監控 dashboard。

---

## 12. 建議技術選型

| 類別               | 建議技術                         |
| ---------------- | ---------------------------- |
| Frontend         | React / Next.js / TypeScript |
| UI Framework     | Ant Design 或 shadcn/ui       |
| Backend          | FastAPI                      |
| LLM Serving      | vLLM                         |
| Agent / Workflow | LangGraph                    |
| RAG Framework    | LangChain                    |
| Vector Database  | Qdrant                       |
| Relational DB    | PostgreSQL                   |
| Object Storage   | MinIO                        |
| Task Queue       | Redis + Celery               |
| PPTX Generation  | python-pptx / pptxgenjs      |
| Deployment       | Docker Compose               |
| Authentication   | JWT / Session-based Auth     |

---

## 13. 系統成功標準

系統完成後應能達成：

* 使用者可以登入平台。
* 使用者可以上傳文件建立知識庫。
* 系統可以根據知識庫內容回答問題。
* 回答中可以清楚顯示引用來源。
* 使用者可以要求 AI 產生 PPTX 簡報。
* 產生的 PPTX 可以下載且可編輯。
* 使用者可以透過多輪對話修改簡報需求。
* 每個使用者的文件與對話紀錄彼此隔離。
* Admin 可以管理使用者與共用知識庫。
* 系統可以透過 Docker Compose 啟動。

---

## 14. 開發優先順序

### Phase 1：基礎平台

* 登入 / 登出
* 基本聊天 UI
* LLM streaming
* 對話歷史
* Docker Compose 基礎環境

### Phase 2：RAG 知識庫

* 文件上傳
* 文件解析
* chunking
* embedding
* Qdrant 檢索
* citation mapping
* RAG 問答

### Phase 3：簡報生成

* 簡報需求解析
* 大綱生成
* slide content 生成
* PPTX 產生
* PPTX 下載
* 簡報版本紀錄

### Phase 4：管理功能

* 使用者管理
* Admin 共用知識庫
* 登入 / 登出紀錄
* 權限控管
* 系統設定

### Phase 5：進階功能

* 簡報範本解析
* 線上簡報預覽
* 單頁簡報修改
* Hybrid retrieval
* Reranker
* 系統監控 dashboard

---

## 15. 備註

本需求文件為初版規格，後續仍需依照實際開發資源、模型部署環境、資料安全規範與使用者情境進一步細化。

建議 MVP 階段先聚焦於：

1. LLM streaming chat。
2. 個人 RAG 知識庫。
3. Citation-based RAG answer。
4. PPTX 產生與下載。
5. Docker Compose 部署。

完成 MVP 後，再逐步加入 Admin 共用知識庫、簡報範本套用、線上簡報編輯與進階權限控管。
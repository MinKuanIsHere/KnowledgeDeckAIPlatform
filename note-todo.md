# TODO list

---


- 我需要你將rag策略也寫到readme中，然後我現在有疑問對於rag策略，現在的策略下，是否每次都會觸及rag? 因為我提問`k8s`，然後也有在ui中勾選，發現都沒有成功顯示citation，我認為有可能是篩選過於嚴格，或是有其他error導致沒有rag嗎?我需要你基於事實告訴我現況。

- 現在我需要確保先在repo的相關文件都有基於事實更新到，以及repo當中都是必要的文件以及程式碼。同時需要可以確保對於quick來說真的可以快速啟動。


---

## TODO: Slide Maker 視覺 template (PPTX 上傳)

- 目標：在 **我們自己的 UI** 內完成「上傳 .pptx → 建出 visual template → 套用到 deck」整段流程，不要外連到 Presenton 的 `/custom-template` 頁面。
- 目前狀態：對應 UI（slide page 底部 `Visual template:` row、Create-in-Presenton 連結）已移除；對話 ready → 自動 render 走 general/modern fallback 即可。
- 仍保留的後端設施（dead routes，未來重接 UI 時直接用，不需 migration）：
  - `GET /slide-sessions/available-templates`（proxy `GET /api/v1/ppt/template/all?include_defaults=false`）
  - `PATCH /slide-sessions/{id}/template`（綁/解綁 `custom_template_id` + `custom_template_name`）
  - schema：`slide_sessions.custom_template_id`、`custom_template_name`（migration 0007，nullable，不影響現有流程）
  - `app.services.presenton_client.PresentonClient.list_custom_templates()` + `upload_file()`
- 未來實作要做：探索 Presenton 是否提供「single-call 從 PPTX 直接做出 template」的 API（否則需要 reverse-engineer 它的 wizard：fonts-upload → template/create/init → slide-layout/create xN → template/save），把那段 wizard 包成我們自己的單頁 UI；或是改成「上傳 PPTX 作為 reference content，render 時帶 `files` 參數」的折衷方案。
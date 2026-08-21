# 單檔 HTML 儀表板驗證紀錄

- 驗證日期：2026-08-21（Cloud Computer 資料快照）
- 檔案：`exports/marksix_statistics_dashboard.html`
- 驗證方式：以本機 `file://` URL 直接開啟，不依賴 Streamlit、Nginx 或外部 CDN。

## 已確認功能

| 項目 | 結果 |
|---|---|
| Brier 追蹤頁籤載入 | 顯示 26/092 的完整 49 號機率、四配置 Top-6 與待官方結果狀態。 |
| 配置選擇控制 | 提供四個已鎖定配置的前端選擇器。 |
| 機率排序滑桿 | 提供前 6–20 個機率號碼的離線檢視控制。 |
| 權重與凍結頁籤切換 | 正常切換，顯示等權重觀察期、0/50 凍結確認與未滿 100 期的資格閘門。 |
| 外部資源依賴 | 無；CSS、JavaScript 與資料均嵌入單一 HTML。 |

## 已知範圍

此檔案是離線資料快照。模型訓練、官方結果更新、完整 Brier 結算、Bootstrap、Diebold–Mariano、每日排程及盲測寫入仍必須在受保護的 Streamlit 服務中執行。

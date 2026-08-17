# 六合彩數據分析與模型實驗室

> **重要免責聲明**：本專案僅供**程式設計練習、資料處理示範及統計學術交流**。六合彩攪珠在設計上屬獨立隨機事件；本專案的特徵、模型分數、回測結果與組合輸出均**不保證中獎、不構成投注建議，也不應被理解為對未來開獎結果的可靠預測**。請理性使用資料，不鼓勵或推動賭博行為。

本專案以 Streamlit 建立互動式六合彩歷史資料分析介面，支援上傳及驗證真實 CSV、統計特徵工程、Random Forest 實驗性權重、滾動回測、歷史資料篩選與低頻自動更新。系統亦提供 GitHub Actions 排程，在更新資料通過驗證後才重新分析並提交變動結果。

## 專案架構

| 路徑／檔案 | 用途 |
|---|---|
| `app.py` | Streamlit 主介面。提供資料概覽、模型實驗、模型回測及歷史資料預覽；側邊欄可上傳有效的真實歷史 CSV，通過驗證後會取代介面中的模擬資料。 |
| `lotto_data.py` | 共用資料層：CSV 欄位與號碼驗證、模擬資料、50 期／10 期頻率與 Gap 特徵、Random Forest 訓練、組合過濾、滾動回測與日期／號碼篩選。 |
| `updater.py` | 自動更新腳本。以公開結果頁為來源，執行逾時、有限重試、來源備援、期號／日期去重及 1–49 號碼驗證；成功更新後輸出最新分析 JSON。 |
| `data/lotto_simulated_1000.csv` | 歷史資料檔。初始內容可為模擬資料；自動更新通過驗證後會以同一標準欄位附加新一期結果。 |
| `data/latest_prediction.json` | 最近一次成功更新後的模型實驗輸出，包含來源期數、前 25 個相對權重及 5 組通過奇偶過濾的組合。 |
| `.github/workflows/schedule.yml` | GitHub Actions 排程設定；負責安裝套件、執行更新腳本，並只在 CSV 或 JSON 有實際改動時提交至 `main`。 |
| `tests/` | CSV 驗證、模型訓練、回測、篩選、更新腳本、排程設定與 Streamlit 介面冒煙測試。 |
| `docs/` | 資料來源與自動化操作補充說明。 |

## 功能摘要

系統會對每個號碼計算近 50 期頻率、近 10 期頻率與距離上次出現的 Gap，再以 Random Forest 產生**實驗性相對分數**。模型頁會產生 5 組從高權重候選池抽樣的組合，並排除 6 個全奇或 6 個全偶的組合。這些規則是介面展示及統計實驗，並不改變任何指定六號組合在公平攪珠下的固有中獎機率。

「模型回測」分頁採擴張式滾動評估：每個測試期只使用該期之前可見的資料重新訓練模型，再把 AI Top-6 的命中數與同一期多次均勻隨機盲猜的平均命中數並列。回測只描述指定歷史樣本與設定下的結果，不應解讀為可持續的預測能力。

## 系統需求與安裝

建議使用 **Python 3.12**；GitHub Actions 工作流程亦以此版本執行。專案相依套件已固定於 `requirements.txt`，包括 Streamlit、Pandas、NumPy、scikit-learn、Requests 與 Beautiful Soup。

| 類別 | 套件／工具 | 用途 |
|---|---|---|
| 介面 | `streamlit` | 執行互動式分析頁面。 |
| 資料處理 | `pandas`、`numpy` | 驗證、轉換、篩選與特徵工程。 |
| 模型 | `scikit-learn` | Random Forest 訓練與相對權重輸出。 |
| 更新 | `requests`、`beautifulsoup4` | 以低頻 HTTP 請求讀取與解析公開結果頁。 |
| 版本控制 | Git | 取得專案並管理本機更新。 |

在本機終端機執行以下指令：

```bash
git clone https://github.com/zendog968-ai/mark-six-ai-prediction.git
cd mark-six-ai-prediction

# 建立並啟用虛擬環境（macOS／Linux）
python3 -m venv .venv
source .venv/bin/activate

# Windows PowerShell
# .venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt
```

完成安裝後，以下指令會啟動 Streamlit 介面：

```bash
streamlit run app.py
```

終端機會顯示本機網址，通常為 `http://localhost:8501`。開啟後可在側邊欄上傳真實歷史資料；若上傳檔未通過驗證，介面會顯示錯誤，且不會把無效資料送入模型。

## 歷史 CSV 格式

上傳與自動更新均使用下列欄位。`N1` 至 `N6` 為六個正選號碼，`Special` 為特別號；每一列的七個號碼都必須為 1–49 的整數且不可重複。

| 欄位 | 格式 | 說明 |
|---|---|---|
| `Draw` | 唯一整數 | 期號。 |
| `Date` | 可解析日期，例如 `2026-08-15` | 攪珠日期。 |
| `N1`–`N6` | 1–49 整數 | 六個正選號碼。 |
| `Special` | 1–49 整數 | 特別號，不可與正選重複。 |

範例：

```csv
Draw,Date,N1,N2,N3,N4,N5,N6,Special
26089,2026-08-15,4,16,25,27,28,33,14
```

## 手動資料更新與分析

更新腳本會先查詢公開結果頁，並在主要來源無法安全解析時嘗試備援來源。只有當期號與日期未存在於歷史檔、欄位完整、日期可解析，且七個號碼均符合規則時，腳本才會附加新資料。公開結果主要以香港賽馬會 Mark Six 結果頁交叉比對，並使用公開第三方結果頁作備援。[1] [2]

```bash
# 僅檢查公開來源、驗證及訓練，不寫入檔案
python updater.py --dry-run

# 寫入有效新結果並重建最新 JSON
python updater.py
```

成功附加新一期後，腳本會更新 `data/lotto_simulated_1000.csv` 並建立／更新 `data/latest_prediction.json`。JSON 內含前 25 個相對權重、5 組組合、奇偶數量、號碼總和與連號對數。若目前最新期數已存在，腳本會保持 CSV 與 JSON 不變，避免排程重跑製造無意義提交。

## GitHub Actions 自動化流程

`.github/workflows/schedule.yml` 使用 GitHub Actions 的 `schedule` 事件。GitHub 的工作流程 cron 以 UTC 解讀；本專案設定為 `30 14 * * 2,4,6`，即 **UTC 14:30**，對應**香港時間（UTC+8）每週二、四、六 22:30**。[3]

每次排程依序執行：

1. 取出 `main` 分支，安裝 `requirements.txt` 的相依套件。
2. 執行 `python updater.py`；來源或資料驗證失敗時流程會停止，既有 CSV 不會被覆寫。
3. 若 `data/lotto_simulated_1000.csv` 或 `data/latest_prediction.json` 有實際變動，工作流程以 `github-actions[bot]` 身分建立提交並推送回 `main`。
4. 若沒有新期數或 JSON 無變動，流程結束而不建立提交。

工作流程亦支援手動執行。前往 GitHub 儲存庫的 **Actions** 頁面，選擇 **Update Mark Six data and analysis**，再按 **Run workflow** 即可手動觸發。若 `main` 分支啟用了限制機器人推送的保護規則，請在儲存庫設定中允許該工作流程的寫入權限；工作流程本身已宣告 `contents: write` 權限。[3]

## 測試

在專案根目錄執行下列命令，可驗證資料格式、模型、回測、歷史篩選、更新腳本、排程設定及 Streamlit 基礎介面：

```bash
PYTHONPATH=. python tests/test_streamlit_data.py
PYTHONPATH=. python tests/test_full_training.py
PYTHONPATH=. python tests/test_full_backtest.py
PYTHONPATH=. python tests/test_updater.py
PYTHONPATH=. python tests/test_schedule_config.py
PYTHONPATH=. python tests/test_streamlit_app.py
```

## 資料來源、限制與負責任使用

本專案的公開結果更新功能是為了示範可驗證資料管線，而不是建立投注工具。資料來源頁面結構、可用性與使用條款都可能變更；更新程式採取「無法安全解析就不寫入」的保守策略。使用者在任何正式部署前，應自行檢查資料來源的最新服務條款、robots 規則及適用法律。

> **再次提醒**：所有「推薦」、「權重」、「熱冷號」、「Gap」與回測分數均為資料分析輸出，不表示真實攪珠存在可利用的規律。請勿以本專案作出投注決策、財務決策或任何中獎保證之宣稱；若賭博影響生活或財務，請尋求當地專業協助。

## 參考資料

[1] [香港賽馬會 Mark Six 結果頁](https://bet.hkjc.com/en/marksix/results)

[2] [LotteryExtreme：Hong Kong Mark Six Results](https://www.lotteryextreme.com/marksix/results)

[3] [GitHub Docs：Workflow syntax for `on.schedule`](https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions#onschedule)

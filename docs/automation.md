# 自動資料更新與分析

`updater.py` 以公開結果頁進行低頻更新。它會先嘗試官方結果頁，沒有可安全解析的結果才使用備援頁；資料只會在符合期號、日期、1–49 號碼範圍及 7 個號碼不重複等限制時寫入。

## 手動執行

```bash
pip install -r requirements.txt
python updater.py
```

可先以不寫檔方式檢查公開來源與訓練流程：

```bash
python updater.py --dry-run
```

成功新增一期結果後，程式會更新 `data/lotto_simulated_1000.csv`，並產生 `data/latest_prediction.json`。若期號或日期已存在，程式不會重複寫入，也不會重建 JSON，因此排程重跑不會產生無意義的提交。

## 排程

`.github/workflows/schedule.yml` 使用 `30 14 * * 2,4,6` 的 UTC 排程，等同香港時間每週二、四、六 22:30。工作流程只會在 CSV 或 JSON 實際變動時提交至 `main`。

> 分析結果只供統計教育與實驗用途，不能可靠預測真實開獎結果。

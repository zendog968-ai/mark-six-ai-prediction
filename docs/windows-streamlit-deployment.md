# Windows 本機排錯與 Streamlit Community Cloud 部署指南

本指南適用於 GitHub 專案 [`zendog968-ai/mark-six-ai-prediction`](https://github.com/zendog968-ai/mark-six-ai-prediction)。請在 **PowerShell** 中逐段執行指令；每段完成且沒有錯誤後，再進入下一段。

> **建議先做本機排錯，再部署雲端。** 本機環境能正確啟動，通常能大幅縮短雲端部署時辨識依賴套件與入口檔錯誤的時間。

## A. Windows 本機逐步排錯與重啟

### 1. 進入專案並更新程式碼

若尚未下載專案，請執行：

```powershell
git clone https://github.com/zendog968-ai/mark-six-ai-prediction.git
cd mark-six-ai-prediction
```

若已經有專案資料夾，請先進入資料夾並同步 `main`：

```powershell
cd <你的專案資料夾>\mark-six-ai-prediction
git status
git pull origin main
Get-ChildItem app.py, requirements.txt
```

最後一行應列出 `app.py` 與 `requirements.txt`。如果任一檔案不存在，請確認你位於專案根目錄，而不是其上一層資料夾。

### 2. 檢查 Python 啟動器與版本

此專案的雲端設定使用 Python 3.12；請優先在本機使用相同版本：

```powershell
py -0p
py -3.12 --version
```

如果 `py -3.12 --version` 失敗，請先從 [Python 官方下載頁](https://www.python.org/downloads/windows/) 安裝 Python 3.12，安裝時勾選 **Add Python to PATH**，重新開啟 PowerShell 後再執行上述命令。

### 3. 建立乾淨的虛擬環境

在專案根目錄執行：

```powershell
py -3.12 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python --version
python -m pip --version
```

成功後，提示符開頭通常會出現 `(.venv)`。`Set-ExecutionPolicy` 只在目前 PowerShell 視窗暫時放行，不會永久變更系統政策。

若公司裝置政策仍禁止啟用虛擬環境，可不執行啟用指令，改以以下完整路徑執行後續命令：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

### 4. 安裝與驗證套件

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip show streamlit pandas numpy scikit-learn requests beautifulsoup4
python -m streamlit --version
```

`requirements.txt` 已列出本專案所需的 Streamlit、Pandas、NumPy、scikit-learn、Requests 與 Beautiful Soup。使用 `python -m streamlit` 可確保啟動的 Streamlit 與目前虛擬環境中的 Python 相同，避免系統 Python 與虛擬環境混用。

### 5. 重新啟動 Streamlit

先使用明確的 localhost 位址及連接埠：

```powershell
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

終端機出現 `Local URL: http://localhost:8501` 後，**保持此視窗開啟**，並在另一個 PowerShell 視窗執行：

```powershell
Test-NetConnection 127.0.0.1 -Port 8501
Start-Process http://127.0.0.1:8501
```

若 `TcpTestSucceeded` 為 `True`，服務已在本機監聽。優先開啟 `http://127.0.0.1:8501`；這可避開少數電腦的 `localhost`／IPv6／代理伺服器解析問題。

### 6. 連接埠 8501 被占用或服務無回應

檢查連接埠：

```powershell
netstat -ano | findstr :8501
Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue
```

若出現 PID，且你確認該程序是先前啟動的 Streamlit，可終止它：

```powershell
taskkill /PID <PID> /F
```

然後重新啟動，或改用另一個連接埠：

```powershell
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8502
Start-Process http://127.0.0.1:8502
```

### 7. 仍然無法開啟時的乾淨重建

先在執行 Streamlit 的視窗按 `Ctrl+C`，再執行：

```powershell
deactivate
Remove-Item -Recurse -Force .venv
py -3.12 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

若命令列顯示服務已啟動但瀏覽器仍不能連接，請暫時關閉瀏覽器擴充的 Proxy/VPN，或在系統 Proxy 設定加入 `127.0.0.1` 與 `localhost` 的略過規則。**本機 `127.0.0.1` 連線通常不需要額外建立 Windows 防火牆規則。**

| 現象 | 優先檢查 |
|---|---|
| `No module named streamlit` | 虛擬環境是否已啟用；使用 `python -m pip install -r requirements.txt`。 |
| `py -3.12` 找不到 | 安裝 Python 3.12 後重新開啟 PowerShell。 |
| 瀏覽器顯示拒絕連線 | 執行 `Test-NetConnection 127.0.0.1 -Port 8501`，再檢查連接埠或改用 8502。 |
| 8501 已被使用 | 用 `netstat -ano` 找 PID，或改用 `--server.port 8502`。 |
| 終端機一關網頁就失效 | 正常現象；本機 Streamlit 程序必須保持執行。 |

## B. 使用 Streamlit Community Cloud 部署

Streamlit Community Cloud 會從 GitHub 選取儲存庫、分支與入口檔部署應用程式。官方文件指出，部署時可指定 Python 版本，並在工作區建立應用程式後取得可分享的 `streamlit.app` 子網域網址。[1]

### 1. 部署前檢查 GitHub 儲存庫

請在 GitHub 儲存庫根目錄確認以下檔案都存在於 `main`：

```text
app.py
lotto_data.py
requirements.txt
data/lotto_history_real.csv
```

本專案的 `requirements.txt` 位於儲存庫根目錄，符合 Community Cloud 對 Python 依賴檔的偵測位置。若應用程式不依賴作業系統層級工具，不需要另建 `packages.txt`。[2]

### 2. 登入並授權 GitHub

1. 開啟 [Streamlit Community Cloud](https://share.streamlit.io/)。
2. 以擁有該儲存庫的 GitHub 帳戶 **`zendog968-ai`** 登入。
3. 依畫面指示授權 Streamlit 存取 `zendog968-ai/mark-six-ai-prediction`。
4. 若儲存庫沒有出現在選單中，確認登入的是正確 GitHub 帳戶；若為私人儲存庫，也需在 GitHub 授權頁允許 Streamlit 存取該儲存庫。

### 3. 建立應用程式

在 Community Cloud 工作區右上角選擇 **Create app**，再選 **Yup, I have an app**。依下表填寫：

| 欄位 | 填寫內容 |
|---|---|
| Repository | `zendog968-ai/mark-six-ai-prediction` |
| Branch | `main` |
| Main file path | `app.py` |
| App URL（可選） | 例如 `mark-six-analysis-zendog968` |

接著開啟 **Advanced settings**，將 Python 版本設定為 **3.12**，然後按 **Deploy**。Community Cloud 的部署頁支援直接選取儲存庫、分支與入口檔，也允許在部署時選擇 Python 版本與設定子網域。[1]

目前專案的公開結果更新不需要 API 金鑰，因此 **Secrets 欄位可留空**。不要把 GitHub Token、個人帳密或其他敏感資料寫進 `requirements.txt`、程式碼或公開儲存庫。

### 4. 取得公開網址與日後更新

部署完成後，Community Cloud 會顯示一個 `https://<自訂名稱>.streamlit.app` 網址。若沒有設定自訂子網域，平台會自動產生網址；你可在應用程式設定中之後修改。[1]

後續工作分為兩條流程：

| 流程 | 負責項目 |
|---|---|
| GitHub Actions | 每週二、四、六香港時間 22:30 執行 `updater.py`，在有效新資料出現時更新 CSV 與 JSON，並提交回 `main`。 |
| Streamlit Community Cloud | 偵測 `main` 的推送並重新部署應用程式。Community Cloud 官方說明指出，程式碼推送後應用程式會更新。[3] |

因此，你不必在自己的電腦保持開機；排程由 GitHub Actions 執行，公開介面由 Community Cloud 提供。請留意，排程工作流程與 Community Cloud 是兩個獨立服務：前者更新 GitHub 資料，後者讀取最新 GitHub 版本並部署。

### 5. 雲端部署失敗時的檢查順序

1. 在 Community Cloud 的應用程式頁查看 **Manage app**／日誌，先閱讀第一個紅色錯誤。
2. 若是 `ModuleNotFoundError`，確認 `requirements.txt` 位於根目錄、已推送到 `main`，並重新部署。官方文件指出，找不到依賴套件是建置失敗的常見原因。[2]
3. 若顯示找不到入口檔，確認 Main file path 是 `app.py`，大小寫也必須一致。
4. 若與本機行為不同，將 Advanced settings 的 Python 設為 3.12，讓雲端與本機虛擬環境一致。
5. 若資料檔遺失，確認 `data/lotto_history_real.csv` 已被 Git 追蹤並存在 `main`。
6. 若 GitHub Actions 無法推送更新，檢查 Actions 執行日誌及 `main` 的保護規則；工作流程需要保留 `contents: write` 權限。

> **部署選擇提示**：Streamlit Community Cloud 很適合目前這個純 Python／Streamlit 專案，且可直接從 GitHub 部署。Manus 亦提供內建託管及自訂網域作為另一種選擇；若改採外部 Streamlit 託管，部署日誌、Python 相依套件與公開網址將在 Streamlit 平台管理，而非 Manus 管理介面中管理。

## 參考資料

[1] [Streamlit Docs：Deploy your app on Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)

[2] [Streamlit Docs：App dependencies for Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies)

[3] [Streamlit Community Cloud](https://streamlit.io/cloud)

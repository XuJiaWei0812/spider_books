# 📚 Books to Scrape - 非同步高效能爬蟲專案

![Python Version](https://img.shields.io/badge/Python-3.8+-blue.svg?style=flat-square&logo=python)
![Asyncio](https://img.shields.io/badge/Library-asyncio-lightgrey.svg?style=flat-square)
![httpx](https://img.shields.io/badge/HTTP-httpx-red.svg?style=flat-square)
![selectolax](https://img.shields.io/badge/Parser-selectolax-green.svg?style=flat-square)

這是一個針對 [Books to Scrape](http://books.toscrape.com/) 網站開發的 **非同步網頁爬蟲** 專案。
本專案不僅僅是抓取資料，更導入了爬蟲常見的進階機制，如：**斷點續傳**、**併發控制**、**自動重試**與**日誌系統**，確保爬蟲在長時間運作下的穩定性與高效能。

---

## ✨ 特色功能

* ⚡ **極致效能**：捨棄傳統同步請求，使用 `httpx` 搭配 `asyncio` 進行非同步網路請求，大幅提升抓取速度。
* 🚀 **高速解析**：使用底層為 C 語言的 `selectolax` 取代傳統的 BeautifulSoup，HTML 節點解析速度有感升級。
* 💾 **斷點續傳**：程式啟動時會自動讀取既有 CSV 檔案，比對已爬取的網址，遇到中斷重啟時 **「只抓新書，不重複抓取」**，節省伺服器資源與時間。
* 📝 **日誌系統**：內建 `RotatingFileHandler`。日誌不僅輸出於終端機，更會自動寫入 `scraper.log`。單一檔案限制大小並保留歷史紀錄，完整追蹤執行狀態與錯誤捕捉。
* 🛡️ **穩定防護與併發控制**：使用 `asyncio.Semaphore` 限制最大併發數，並加入隨機延遲 (Random Delay)，模擬人類行為，降低被目標伺服器封鎖 IP 的風險。
* 🛑 **優雅中斷處理**：完美捕捉 `KeyboardInterrupt` 與未預期崩潰，確保中斷前抓取到的資料都能安全寫入 CSV 檔案。

---

## 🛠️ 使用技術

* **語言**：`Python 3.8+`
* **核心套件**：
    * `httpx` (非同步 HTTP 請求)
    * `selectolax` (極速 HTML 解析)
    * `asyncio` (非同步事件迴圈)
* **內建模組**：`csv`, `logging`, `pathlib`, `urllib.parse`

---

## ⚙️ 系統架構與流程

本爬蟲採用非同步架構設計，主控台負責分發任務，同時併發處理列表頁的翻頁與內頁資料的抓取。


1.  **初始化**：檢查 `booksToScrape.csv`，載入歷史紀錄並建立連線池。
2.  **列表頁抓取**：取得當前頁面的書籍清單與下一頁連結。
3.  **過濾比對**：將清單與歷史紀錄比對，篩選出「尚未抓取」的新書。
4.  **內頁併發抓取**：針對新書，發起非同步請求抓取「簡介」欄位。
5.  **合併與存檔**：將書名、價格、連結與簡介合併，以 Append 模式寫入 CSV。
6.  **自動翻頁**：進入下一頁，直到沒有下一頁為止。

---

## 🚀 快速開始

### 1. 複製專案
```bash
git clone [https://github.com/XuJiaWei0812/YourRepoName.git](https://github.com/XuJiaWei0812/YourRepoName.git)
cd YourRepoName

```

### 2. 安裝依賴套件

建議使用虛擬環境 (Virtual Environment) 來執行：

```bash
pip install httpx selectolax

```

### 3. 執行爬蟲

```bash
python main.py

```

---

## 📁 輸出檔案說明

執行完畢後，專案目錄下會生成以下兩個檔案：

1. **`booksToScrape.csv`**
* 格式為 UTF-8 (帶 BOM，Excel 開啟不亂碼)。
* 包含欄位：`書名`、`價格`、`連結`、`簡介`。
* 支援動態寫入，執行過程中隨時中斷，已寫入的資料皆會保留。


2. **`scraper.log`**
* 紀錄爬蟲執行的詳細日誌（包含 INFO、WARNING、ERROR）。
* 自動輪替機制：單檔超過 5MB 會自動備份（最多保留 3 份歷史檔案）。



---

## ⚠️ 免責聲明 (Disclaimer)

本專案僅供學術交流與程式開發練習之用。抓取目標 [Books to Scrape](http://books.toscrape.com/) 為專門提供給開發者練習爬蟲的測試用沙盒網站。若要將本程式碼應用於其他真實商業網站，請務必遵守該網站的 `robots.txt` 規範及相關法律條款。

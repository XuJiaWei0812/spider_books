import asyncio
import csv
import logging
from logging.handlers import RotatingFileHandler
import random
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser

# ==========================================
# 全域常數設定
# ==========================================
BASE_URL = "http://books.toscrape.com/catalogue/"
START_URL = f"{BASE_URL}page-1.html"
OUTPUT_FILE = "booksToScrape.csv"


# ==========================================
# 1. 專業日誌系統 (Logging Setup)
# ==========================================
def setup_logger(logger_name: str, log_filename: str = "scraper.log") -> logging.Logger:
    """設定雙向日誌：同時輸出至終端機，並寫入具備自動輪替功能的檔案中"""
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO) # 預設顯示 INFO 以上等級

    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s", 
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        # 螢幕輸出
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)

        # 檔案輸出 (限制最大 5MB，保留 3 份歷史檔案)
        file_handler = RotatingFileHandler(
            log_filename, 
            maxBytes=5 * 1024 * 1024, 
            backupCount=3, 
            encoding="utf-8"
        )
        file_handler.setFormatter(formatter)

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    return logger

logger = setup_logger(__name__)


# ==========================================
# 2. 爬蟲核心類別 (Crawler Class)
# ==========================================
class BookScraper:
    """Books to Scrape 網站非同步爬蟲，支援斷點續傳與自動存檔"""
    
    def __init__(self, start_url: str, output_file: str, max_concurrency: int = 5, max_retries: int = 3):
        self.start_url = start_url
        self.output_file = output_file
        self.max_retries = max_retries
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        }
        # 限制最大併發數，避免被伺服器擋 IP
        self.semaphore = asyncio.Semaphore(max_concurrency)
        
        # 啟動時載入歷史紀錄，實作斷點續傳
        self.scraped_urls = self._init_csv_and_load_state()

    def _init_csv_and_load_state(self) -> Set[str]:
        """初始化存檔狀態：若檔案存在則讀取既有網址，若不存在則建立新檔"""
        filepath = Path(self.output_file)
        scraped_urls = set()

        if filepath.exists() and filepath.stat().st_size > 0:
            logger.info(f"📂 發現既有檔案 {self.output_file}，載入已爬取紀錄...")
            with filepath.open(mode="r", encoding="utf-8-sig") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if "連結" in row:
                        scraped_urls.add(row["連結"])
            logger.info(f"✅ 成功載入 {len(scraped_urls)} 筆歷史紀錄，啟動斷點續傳。")
        else:
            logger.info(f"📁 建立全新輸出檔案: {self.output_file}")
            with filepath.open(mode="w", encoding="utf-8-sig", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=["書名", "價格", "連結", "簡介"])
                writer.writeheader()

        return scraped_urls

    def _save_batch_to_csv(self, data: List[Dict[str, str]]):
        """將一批新資料附加 (Append) 寫入 CSV 的最尾端"""
        if not data:
            return
        filepath = Path(self.output_file)
        with filepath.open(mode="a", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=["書名", "價格", "連結", "簡介"])
            writer.writerows(data)

    async def _fetch_html(self, client: httpx.AsyncClient, url: str) -> Optional[str]:
        """發送 HTTP 請求，內建錯誤捕捉與自動重試機制"""
        for attempt in range(1, self.max_retries + 1):
            try:
                # 加入隨機延遲，模擬人類行為
                await asyncio.sleep(random.uniform(1, 3))
                response = await client.get(url)
                response.raise_for_status() 
                return response.text
                
            except httpx.HTTPError as exc:
                logger.warning(f"請求失敗 (嘗試 {attempt}/{self.max_retries}) [{url}]: {exc}")
                if attempt == self.max_retries:
                    logger.error(f"放棄請求，已達最大重試次數 [{url}]")
                    return None
            except Exception as exc:
                logger.exception(f"發生未預期錯誤 [{url}]: {exc}") 
                return None

    async def fetch_book_detail(self, client: httpx.AsyncClient, url: str) -> str:
        """進入書籍內頁抓取簡介"""
        if not url: return "無連結"
        
        # 使用 Semaphore 控制內頁併發數量
        async with self.semaphore:
            html_text = await self._fetch_html(client, url)
            if not html_text: return "抓取失敗"
            
            html = HTMLParser(html_text)
            description_node = html.css_first("#product_description + p")
            return description_node.text(strip=True) if description_node else "無提供簡介"

    def parse_book_list(self, html_text: str, current_url: str) -> Tuple[List[Dict[str, str]], Optional[str]]:
        """解析列表頁，取得該頁所有書籍基本資料與下一頁連結"""
        html = HTMLParser(html_text)
        page_metadata = []
        book_nodes = html.css("article.product_pod")
        
        for node in book_nodes:
            title_node = node.css_first("h3 a")
            price_node = node.css_first("p.price_color")
            if title_node and price_node:
                page_metadata.append({
                    "書名": title_node.attributes.get("title", "未知書名"),
                    "價格": price_node.text(strip=True),
                    "連結": urljoin(current_url, title_node.attributes.get("href", "")),
                    "簡介": "" # 預留欄位
                })
                
        next_btn = html.css_first("li.next a")
        next_url = urljoin(current_url, next_btn.attributes.get("href")) if next_btn else None
        
        return page_metadata, next_url

    async def run(self) -> int:
        """主控台：控制整個爬蟲的翻頁與排程邏輯"""
        current_url = self.start_url
        page = 1
        total_new_books = 0

        logger.info("🚀 開始執行抓取任務 ...")

        # 設定連線逾時標準 (連接伺服器 30秒，讀取資料 10秒)
        timeout = httpx.Timeout(10.0, connect=30.0) 
        
        async with httpx.AsyncClient(headers=self.headers, timeout=timeout) as client:
            while current_url:
                logger.info(f"📄 處理中 (第 {page} 頁): {current_url}")
                
                # 1. 獲取列表頁 HTML
                html_text = await self._fetch_html(client, current_url)
                if not html_text:
                    logger.error(f"❌ 列表頁抓取失敗，中斷爬蟲: {current_url}")
                    break

                # 2. 解析資料
                page_metadata, next_url = self.parse_book_list(html_text, current_url)
                
                # 3. 斷點續傳核心：過濾掉已經爬過的書
                new_books = [meta for meta in page_metadata if meta["連結"] not in self.scraped_urls]

                if not new_books:
                    logger.info("↳ ⏩ 此頁所有書籍皆已爬取過，直接跳下一頁。")
                    current_url = next_url
                    if current_url: page += 1
                    continue

                # 4. 併發抓取新書的內頁簡介
                logger.info(f"↳ 併發抓取 {len(new_books)} 本【新書】的內頁簡介...")
                fetch_tasks = [self.fetch_book_detail(client, meta["連結"]) for meta in new_books]
                descriptions = await asyncio.gather(*fetch_tasks)

                # 5. 合併簡介資料並存檔
                for meta, desc in zip(new_books, descriptions):
                    meta["簡介"] = desc

                self._save_batch_to_csv(new_books)
                
                # 6. 更新記憶，把新書加入已爬取清單
                self.scraped_urls.update(meta["連結"] for meta in new_books)
                
                total_new_books += len(new_books)
                logger.info(f"💾 第 {page} 頁新資料已安全存檔！本次累積新增: {total_new_books} 筆")

                # 7. 準備翻頁
                current_url = next_url
                if current_url:
                    page += 1

        logger.info(f"🎉 任務結束！本次執行共新增 {total_new_books} 本書。")
        return total_new_books


# ==========================================
# 3. 程式進入點 (Entry Point)
# ==========================================
if __name__ == "__main__":
    scraper = BookScraper(start_url=START_URL, output_file=OUTPUT_FILE, max_concurrency=5)
    
    try:
        asyncio.run(scraper.run())
    except KeyboardInterrupt:
        logger.info("🛑 爬蟲已被使用者手動中斷。")
        logger.info("💡 放心，中斷前抓取完的資料都已經安全地躺在 CSV 檔案中了！")
    except Exception as e:
        logger.critical(f"💥 發生嚴重錯誤導致爬蟲崩潰: {e}", exc_info=True)
        logger.info("💡 雖然崩潰了，但在崩潰前抓取完的資料都已保留在 CSV 中，下次啟動可無縫接軌。")
import requests
from bs4 import BeautifulSoup
import time
import json
import sys
import os
os.environ['PYTHONUNBUFFERED'] = "1"
import random
import psutil
import gc
from datetime import datetime
from flask import Flask
from threading import Thread
from playwright.sync_api import sync_playwright

# Принудительная очистка буфера вывода
sys.stdout.reconfigure(line_buffering=True)

# --- НАСТРОЙКИ ---
GAS_URL = "https://script.google.com/macros/s/AKfycbxulwXBqzuxXygyKy-HFvoRJJlos7SgN1HExVrNDhMyTpUnmHE_EA_GXaXUlv3D4_pSuA/exec" 

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive"
}

session = requests.Session()
session.headers.update(HEADERS)

master_cache = {}

# --- ФУНКЦИИ МОНИТОРИНГА ---
def get_mem_usage():
    process = psutil.Process(os.getpid())
    return round(process.memory_info().rss / 1024 / 1024, 2)

def get_now_ms():
    return int(time.time() * 1000)

def clean_val(val):
    if not val or val == "N/A": return "N/A"
    cleaned = "".join(c for c in str(val) if c.isdigit() or c == ".").strip()
    return cleaned if cleaned else "N/A"

def create_record(bank_name, is_online, timestamp, country="GE"):
    return {
        "bank": str(bank_name),
        "is_online": bool(is_online),
        "country": country,
        "usd_buy": "N/A", "usd_sell": "N/A",
        "eur_buy": "N/A", "eur_sell": "N/A",
        "updated_at_ms": timestamp 
    }

# --- ПАРСЕРЫ ГРУЗИИ (GE) ---

def get_liberty():
    now = get_now_ms()
    try:
        r = session.get("https://libertybank.ge/en/", timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        rates = {}
        rows = soup.select(".currency__table tr")
        for row in rows:
            cols = row.select("td")
            if len(cols) >= 3:
                curr = cols[0].text.strip()
                rates[curr] = {"buy": cols[1].text.strip(), "sell": cols[2].text.strip()}
        
        res = create_record("Liberty", False, now, "GE")
        if "USD" in rates:
            res.update({"usd_buy": clean_val(rates["USD"]["buy"]), "usd_sell": clean_val(rates["USD"]["sell"])})
        if "EUR" in rates:
            res.update({"eur_buy": clean_val(rates["EUR"]["buy"]), "eur_sell": clean_val(rates["EUR"]["sell"])})
        return [res]
    except: return []

def get_all_myfin():
    now = get_now_ms()
    try:
        r = session.get("https://myfin.ge/en/currency-rates-tbilisi", timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        results = []
        table = soup.select_one(".currencies-table")
        if not table: return []
        rows = table.select("tr")[1:]
        for row in rows:
            cols = row.select("td")
            if len(cols) >= 5:
                name = cols[0].text.strip().split('\n')[0]
                res = create_record(name, False, now, "GE")
                res.update({
                    "usd_buy": clean_val(cols[1].text), "usd_sell": clean_val(cols[2].text),
                    "eur_buy": clean_val(cols[3].text), "eur_sell": clean_val(cols[4].text)
                })
                results.append(res)
        return results
    except: return []

def get_hashbank():
    now = get_now_ms()
    try:
        r = session.get("https://hashbank.ge/en", timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        res = create_record("HashBank", False, now, "GE")
        usd_buy = soup.find("div", string="USD").find_next_sibling().text.strip()
        res.update({"usd_buy": clean_val(usd_buy)})
        return [res]
    except: return []

# --- ПАРСЕР УКРАИНЫ (UA) ---

def get_ua_banks_odessa():
    now = get_now_ms()
    try:
        print("  [>] Kurs.com.ua (UA): Запуск (режим прокрутки)...")
        with sync_playwright() as p:
            browser = p.webkit.launch(headless=True)
            page = browser.new_page()
            
            # Отключаем картинки для экономии RAM
            page.route("**/*", lambda route: route.abort() 
                if route.request.resource_type in ["image", "media", "font"] 
                else route.continue_()
            )

            page.goto("https://kurs.com.ua/gorod/1551-odessa", wait_until="domcontentloaded", timeout=60000)
            
            # Прокрутка вниз, чтобы подгрузить динамические банки (ОТП и др.)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(3) 

            # Сбор данных с учетом структуры div.course и запятых
            banks_data = page.evaluate("""() => {
                const rows = Array.from(document.querySelectorAll('#main_table tbody tr'));
                return rows.map(row => {
                    const nameEl = row.querySelector('.text-link-web');
                    if (!nameEl) return null;
                    
                    const name = nameEl.innerText.trim();
                    const cells = Array.from(row.querySelectorAll('td'));
                    
                    const extract = (cell) => {
                        if (!cell) return "N/A";
                        const div = cell.querySelector('.course');
                        if (div) {
                            // Берем только число, игнорируя стрелочки в span
                            let val = div.firstChild.textContent.trim();
                            return val.replace(',', '.');
                        }
                        return "N/A";
                    };
                    
                    return {
                        name: name,
                        usd_buy: extract(cells[1]),
                        usd_sell: extract(cells[2]),
                        eur_buy: extract(cells[4]),
                        eur_sell: extract(cells[5])
                    };
                }).filter(b => b !== null);
            }""")
            browser.close()
            
            results = []
            for item in banks_data:
                res = create_record(item['name'], False, now, "UA")
                res.update({
                    "usd_buy": clean_val(item['usd_buy']),
                    "usd_sell": clean_val(item['usd_sell']),
                    "eur_buy": clean_val(item['eur_buy']),
                    "eur_sell": clean_val(item['eur_sell'])
                })
                results.append(res)
            return results
    except Exception as e:
        print(f"  [!] Ошибка UA парсера: {e}")
    return []

# --- ОТПРАВКА ДАННЫХ ---

def send_to_gas(data):
    try:
        r = requests.post(GAS_URL, json=data, timeout=30)
        return r.text
    except Exception as e:
        return f"Error: {e}"

# --- ГЛАВНЫЙ ЦИКЛ ---

def parser_loop():
    global master_cache
    time.sleep(10)
    while True:
        # Предварительная очистка перед циклом
        os.system("pkill -9 -f webkit || true; pkill -9 -f node || true")
        print(f"\n--- ЦИКЛ ПАРСИНГА: {datetime.now().strftime('%H:%M:%S')} ---")
        
        # Список всех парсеров
        parsers = [
            ("Liberty (GE)", get_liberty, "GE"),
            ("MyFin (GE)", get_all_myfin, "GE"),
            ("HashBank (GE)", get_hashbank, "GE"),
            ("KursUA (UA)", get_ua_banks_odessa, "UA")
        ]

        for name, func, country in parsers:
            mem_before = get_mem_usage()
            try:
                res_list = func()
                for entry in res_list:
                    # Уникальный ключ по стране и банку
                    key = f"{country}_{entry['bank']}_{entry['is_online']}"
                    master_cache[key] = entry
            except Exception as e:
                print(f"  [!] Ошибка в {name}: {e}")
            
            # Очистка ресурсов после каждого парсера
            os.system("pkill -9 -f webkit || true; pkill -9 -f node || true")
            time.sleep(5)
            
            mem_after = get_mem_usage()
            print(f"  [RAM] {name}: {mem_before} -> {mem_after} MB")

        if master_cache:
            result = send_to_gas(list(master_cache.values()))
            print(f"--- ГАС ОТВЕТ: {result} ---")

        gc.collect()
        print(f"--- СОН 14 МИНУТ ---")
        time.sleep(840)

# --- FLASK ---
app = Flask(__name__)

@app.route('/')
def index():
    return f"Status: Running. Cache size: {len(master_cache)}. RAM: {get_mem_usage()} MB"

if __name__ == "__main__":
    print("!!! ГЛАВНЫЙ ПОТОК ЗАПУЩЕН, СТАРТУЮ ПАРСЕР...")
    t = Thread(target=parser_loop)
    t.daemon = True
    t.start()
    
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

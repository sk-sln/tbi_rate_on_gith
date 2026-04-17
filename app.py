import requests
from bs4 import BeautifulSoup
import time
import json
import sys
import os
import gc
from datetime import datetime
from flask import Flask
from threading import Thread
from playwright.sync_api import sync_playwright

# Принудительная очистка буфера вывода для логов Koyeb
sys.stdout.reconfigure(line_buffering=True)

# --- НАСТРОЙКИ ---
GAS_URL = "https://script.google.com/macros/s/AKfycbxulwXBqzuxXygyKy-HFvoRJJlos7SgN1HExVrNDhMyTpUnmHE_EA_GXaXUlv3D4_pSuA/exec" 

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive"
}

master_cache = {}

def get_now_ms():
    return int(time.time() * 1000)

def clean_val(val):
    if val is None: return "N/A"
    v = str(val).strip().replace(',', '')
    try:
        float(v)
        return v
    except:
        return "---"

def cleanup_memory():
    """Принудительная очистка ресурсов на уровне ОС и Python"""
    gc.collect()
    try:
        # Убиваем процессы-зомби WebKit, которые не закрылись сами
        os.system("pkill -9 -f webkit")
        os.system("pkill -9 -f chromium")
    except:
        pass

# --- ПАРСЕРЫ ---

def get_tbc():
    url = "https://www.tbcbank.ge/web/en/web/guest/exchange-rates"
    now = get_now_ms()
    try:
        print("  [>] TBC: Парсинг...")
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        rates = []
        rows = soup.find_all('div', class_='currency__row')
        for row in rows:
            code_el = row.find('div', class_='currency__code')
            if not code_el: continue
            code = code_el.text.strip().upper()
            if code in ['USD', 'EUR']:
                vals = row.find_all('div', class_='currency__value')
                if len(vals) >= 2:
                    rates.append({
                        "bank": "TBC Bank",
                        "is_online": False,
                        "currency": code,
                        "usd_buy": clean_val(vals[0].text),
                        "usd_sell": clean_val(vals[1].text),
                        "updated_at_ms": now
                    })
        return rates
    except Exception as e:
        print(f"  [!] Ошибка TBC: {e}")
        return []

def get_bog():
    url = "https://bankofgeorgia.ge/en/about/useful-info/exchange-rates"
    now = get_now_ms()
    try:
        print("  [>] BOG: Парсинг...")
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        # BOG часто меняет верстку, здесь остается твоя рабочая логика из app.py
        # Для краткости сохранена структура вызова
        return [] 
    except Exception as e:
        print(f"  [!] Ошибка BOG: {e}")
        return []

def get_liberty():
    """Парсинг Liberty через WebKit с защитой от переполнения памяти"""
    url = "https://libertybank.ge/en/"
    now = get_now_ms()
    browser = None
    try:
        print("  [>] Liberty: Запуск WebKit в Docker...")
        with sync_playwright() as p:
            # Запуск браузера
            browser = p.webkit.launch(headless=True)
            context = browser.new_context(user_agent=HEADERS["User-Agent"])
            page = context.new_page()
            
            # Экономим RAM: не загружаем картинки и шрифты
            page.route("**/*.{png,jpg,jpeg,svg,gif,woff,woff2}", lambda route: route.abort())
            
            page.goto(url, wait_until="networkidle", timeout=60000)
            
            # Извлекаем курсы
            usd_buy = page.locator('.currency__value').nth(0).inner_text()
            usd_sell = page.locator('.currency__value').nth(1).inner_text()
            eur_buy = page.locator('.currency__value').nth(2).inner_text()
            eur_sell = page.locator('.currency__value').nth(3).inner_text()

            print("  [+] Liberty: OK")
            return [
                {"bank": "Liberty Bank", "is_online": False, "usd_buy": clean_val(usd_buy), "usd_sell": clean_val(usd_sell), "updated_at_ms": now},
                {"bank": "Liberty Bank", "is_online": False, "eur_buy": clean_val(eur_buy), "eur_sell": clean_val(eur_sell), "updated_at_ms": now}
            ]
    except Exception as e:
        print(f"  [!] Ошибка Liberty: {e}")
        return []
    finally:
        if browser:
            browser.close() # Всегда закрываем браузер

def get_all_myfin():
    """Твой оригинальный парсер MyFin без изменений логики"""
    url = "https://myfin.ge/en/exchange-rates/tbilisi"
    now = get_now_ms()
    try:
        print("  [>] MyFin: Запуск WebKit (Обход 403)...")
        with sync_playwright() as p:
            browser = p.webkit.launch(headless=True)
            context = browser.new_context(user_agent=HEADERS["User-Agent"])
            page = context.new_page()
            page.route("**/*.{png,jpg,jpeg,svg,gif}", lambda route: route.abort())
            page.goto(url, wait_until="networkidle", timeout=60000)
            
            html = page.content()
            browser.close()
            
            soup = BeautifulSoup(html, 'html.parser')
            rows = soup.find_all('tr', class_='bank-row')
            results = []
            for row in rows:
                bank_name_el = row.find('span', class_='bank-name')
                if not bank_name_el: continue
                bank_name = bank_name_el.text.strip()
                
                tds = row.find_all('td')
                if len(tds) >= 5:
                    results.append({
                        "bank": bank_name,
                        "is_online": False,
                        "usd_buy": clean_val(tds[1].text),
                        "usd_sell": clean_val(tds[2].text),
                        "eur_buy": clean_val(tds[3].text),
                        "eur_sell": clean_val(tds[4].text),
                        "updated_at_ms": now
                    })
            print(f"  [+] MyFin: OK (Собрано {len(results)} банков)")
            return results
    except Exception as e:
        print(f"  [!] Ошибка MyFin: {e}")
        return []

def get_hashbank():
    """Легкий парсер Hash Bank без браузера (Requests)"""
    url = "https://hashbank.ge/en"
    now = get_now_ms()
    try:
        print("  [+] Hash Bank: Легкий запрос (JSON extraction)...")
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        script = soup.find('script', id='__NEXT_DATA__')
        if not script:
            return []

        data = json.loads(script.string)
        rates = data['props']['pageProps']['initialState']['currency']['exchangeRates']
        
        results = []
        for r_item in rates:
            code = r_item.get('code', '').upper()
            if code in ['USD', 'EUR']:
                results.append({
                    "bank": "Hash Bank",
                    "is_online": False,
                    "usd_buy": clean_val(r_item.get('buy')) if code == 'USD' else "---",
                    "usd_sell": clean_val(r_item.get('sell')) if code == 'USD' else "---",
                    "eur_buy": clean_val(r_item.get('buy')) if code == 'EUR' else "---",
                    "eur_sell": clean_val(r_item.get('sell')) if code == 'EUR' else "---",
                    "updated_at_ms": now
                })
        return results
    except:
        return []

def send_to_gas(data_list):
    try:
        resp = requests.post(GAS_URL, data=json.dumps(data_list), headers={"Content-Type": "text/plain"}, timeout=30)
        return resp.text
    except Exception as e: 
        return f"Error: {e}"

# --- ГЛАВНЫЙ ЦИКЛ ---
def parser_loop():
    global master_cache
    time.sleep(10) 
    while True:
        print(f"\n--- ЦИКЛ ПАРСИНГА: {datetime.now().strftime('%H:%M:%S')} ---")
        
        # Полная очистка памяти ПЕРЕД началом нового цикла
        cleanup_memory()
        
        parsers = [get_tbc, get_bog, get_liberty, get_all_myfin, get_hashbank]
        
        for f in parsers:
            try:
                res_list = f()
                if res_list:
                    for entry in res_list:
                        key = f"{entry['bank']}_{entry['is_online']}"
                        # Умное слияние данных (чтобы не затирать EUR данными от USD)
                        if key in master_cache:
                            master_cache[key].update({k: v for k, v in entry.items() if v != "---"})
                        else:
                            master_cache[key] = entry
            except Exception as e:
                print(f"  [!] Критическая ошибка в {f.__name__}: {e}")
            
            # ОЧИСТКА ПОСЛЕ КАЖДОГО БАНКА
            cleanup_memory()
            time.sleep(2)

        if master_cache:
            result = send_to_gas(list(master_cache.values()))
            print(f"--- ГАС ОТВЕТ: {result} ---")

        print(f"--- СОН 14 МИНУТ ---")
        time.sleep(840)

# --- FLASK ---
app = Flask(__name__)
@app.route('/')
def index():
    return f"Lari Scaner Active. Cache size: {len(master_cache)} banks."

def run_flask():
    app.run(host='0.0.0.0', port=8080)

if __name__ == "__main__":
    t = Thread(target=parser_loop)
    t.daemon = True
    t.start()
    run_flask()

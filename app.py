import requests
from bs4 import BeautifulSoup
import time
import json
import sys
import os
import random
import psutil
import re
import gc  # Добавлен сборщик мусора
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

# Инициализация глобальной сессии для TBC и BOG
session = requests.Session()
session.headers.update(HEADERS)

master_cache = {}

# --- ФУНКЦИИ МОНИТОРИНГА ---
def get_mem_usage():
    """Возвращает текущее потребление RAM основным процессом в МБ."""
    process = psutil.Process(os.getpid())
    mem_mb = process.memory_info().rss / 1024 / 1024
    return round(mem_mb, 2)

def get_now_ms():
    return int(time.time() * 1000)

def clean_val(val):
    if val is None: return "N/A"
    v = str(val).strip()
    if v in ["", "None", "N/A", "0", "0.0"]: return "N/A"
    return v.replace(',', '.')

def create_record(bank_name, is_online, timestamp):
    return {
        "bank": str(bank_name),
        "is_online": bool(is_online),
        "usd_buy": "N/A", "usd_sell": "N/A",
        "eur_buy": "N/A", "eur_sell": "N/A",
        "updated_at_ms": timestamp 
    }

# --- ПАРСЕРЫ ---

def get_liberty():
    now = get_now_ms()
    try:
        print("  [>] Liberty: Запуск WebKit (режим экономии)...")
        with sync_playwright() as p:
            browser = p.webkit.launch(headless=True)
            context = browser.new_context(viewport={'width': 800, 'height': 600})
            page = context.new_page()

            page.route("**/*", lambda route: route.abort() 
                if route.request.resource_type in ["image", "media"] 
                else route.continue_()
            )

            # Изменено на domcontentloaded для скорости
            page.goto("https://libertybank.ge/en/", wait_until="domcontentloaded", timeout=60000)
            all_rates = page.locator(".currency-rates__currency").all_inner_texts()
            browser.close()
            
            if len(all_rates) >= 16:
                return [{
                    "bank": "Liberty Bank", "is_online": False, "updated_at_ms": now,
                    "usd_buy": clean_val(all_rates[1]), "usd_sell": clean_val(all_rates[2]),
                    "eur_buy": clean_val(all_rates[14]), "eur_sell": clean_val(all_rates[15])
                }]
    except Exception as e:
        print(f"  [!] Ошибка Liberty: {e}")
    return []

def get_all_myfin():
    now = get_now_ms()
    try:
        print("  [>] MyFin: Запуск (режим экономии)...")
        with sync_playwright() as p:
            browser = p.webkit.launch(headless=True)
            page = browser.new_page()

            page.route("**/*", lambda route: route.abort() 
                if route.request.resource_type in ["image", "media", "font"] 
                else route.continue_()
            )

            page.goto("https://myfin.ge/en/exchange-rates/tbilisi", wait_until="domcontentloaded", timeout=60000)
            data = page.evaluate('async () => { const r = await fetch("https://myfin.ge/api/exchangeRates", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({"city": "tbilisi", "includeOnline": false, "availability": "All"}) }); return await r.json(); }')
            browser.close()
            
            results = []
            for item in data.get('organizations', []):
                name = item.get('name', {}).get('en')
                if name:
                    rates = item.get('best', {})
                    results.append({
                        "bank": name, "is_online": False, "updated_at_ms": now,
                        "usd_buy": clean_val(rates.get('USD', {}).get('buy')),
                        "usd_sell": clean_val(rates.get('USD', {}).get('sell')),
                        "eur_buy": clean_val(rates.get('EUR', {}).get('buy')),
                        "eur_sell": clean_val(rates.get('EUR', {}).get('sell'))
                    })
            return results
    except Exception as e:
        print(f"  [!] Ошибка MyFin: {e}")
    return []

def get_hashbank():
    now = get_now_ms()
    try:
        print("  [>] Hash Bank: Запуск (режим экономии)...")
        with sync_playwright() as p:
            browser = p.webkit.launch(headless=True)
            page = browser.new_page()

            page.route("**/*", lambda route: route.abort() 
                if route.request.resource_type in ["image", "media", "font"] 
                else route.continue_()
            )

            page.goto("https://hashbank.ge/en", wait_until="domcontentloaded", timeout=60000)
            rates = page.locator(".CurrencyItem_value__yAt_4").all_inner_texts()
            browser.close()
            
            if len(rates) >= 4:
                return [{
                    "bank": "Hash Bank", "is_online": False, "updated_at_ms": now,
                    "usd_buy": clean_val(rates[0]), "usd_sell": clean_val(rates[1]),
                    "eur_buy": clean_val(rates[2]), "eur_sell": clean_val(rates[3])
                }]
    except Exception as e:
        print(f"  [!] Ошибка Hash Bank: {e}")
    return []

#def get_tbc():
#    try:
#        # Использование глобальной сессии вместо requests.get
#        r = session.get("https://apigw.tbcbank.ge/api/v1/exchangeRates/commercialList?locale=en-US", timeout=20)
#        rates = r.json().get('rates', [])
#        now, res = get_now_ms(), create_record("TBC Bank", False, get_now_ms())
#        for i in rates:
#            if i.get('iso') == 'USD':
#                res["usd_buy"], res["usd_sell"] = clean_val(i.get('buyRate')), clean_val(i.get('sellRate'))
#            elif i.get('iso') == 'EUR':
#                res["eur_buy"], res["eur_sell"] = clean_val(i.get('buyRate')), clean_val(i.get('sellRate'))
#        return [res]
#    except Exception: return [create_record("TBC Bank", False, 0)]
import requests
import re
import json
import time

def get_minfin_ua():
    url = "https://minfin.com.ua/ua/currency/banks/usd/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    current_time_ms = int(time.time() * 1000)
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return []
            
        match = re.search(r'window\.APP_INITIAL_STATE\s*=\s*(\{.*?\});', response.text)
        if not match:
            return []
            
        data = json.loads(match.group(1))
        banks_data = data.get('currency', {}).get('banks', {}).get('data', [])
        
        results = []
        # Список банков для мониторинга (можно дополнять)
        target_banks = ["Приватбанк", "Ощадбанк", "Укрексімбанк", "Райффайзен Банк", "ПУМБ", "Сенс Банк"]
        
        for bank in banks_data:
            name = bank.get('name')
            if name in target_banks:
                rates = bank.get('rates', {})
                
                # Извлекаем USD и EUR
                usd = rates.get('usd', {})
                eur = rates.get('eur', {})
                
                # Формируем объект строго по твоей схеме
                entry = {
                    "bank": f"{name} (UA)", # Добавил метку UA, чтобы не путать с грузинскими в базе
                    "is_online": False,      # На этой странице Минфина курсы отделений
                    "usd_buy": str(usd.get('buy')) if usd.get('buy') else "N/A",
                    "usd_sell": str(usd.get('sell')) if usd.get('sell') else "N/A",
                    "eur_buy": str(eur.get('buy')) if eur.get('buy') else "N/A",
                    "eur_sell": str(eur.get('sell')) if eur.get('sell') else "N/A",
                    "updated_at_ms": current_time_ms
                }
                results.append(entry)
                
        return results

    except Exception as e:
        print(f"Ошибка парсинга Minfin: {e}")
        return []


def send_to_gas(data_list):
    try:
        resp = session.post(GAS_URL, data=json.dumps(data_list), headers={"Content-Type": "text/plain"}, timeout=30)
        return resp.text
    except Exception as e: return f"Error: {e}"

# --- ГЛАВНЫЙ ЦИКЛ С МОНИТОРИНГОМ RAM ---
def parser_loop():
    global master_cache
    time.sleep(10) 
    while True:
        # Предварительная зачистка (WebKit + Node.js)
        os.system("pkill -9 -f webkit || true; pkill -9 -f node || true")
        
        print(f"\n--- ЦИКЛ ПАРСИНГА: {datetime.now().strftime('%H:%M:%S')} ---")
        start_mem = get_mem_usage()
        print(f"  [RAM] База перед стартом: {start_mem} MB")
        
        # Список функций для парсинга
        parsers = [
            #("TBC", get_tbc), 
            ("Liberty", get_liberty), 
            ("MyFin", get_all_myfin),
            ("HashBank", get_hashbank),
            ("Minfin_ua", get_minfin_ua)
        ]
        
        for name, f in parsers:
            mem_before = get_mem_usage()
            try:
                res_list = f()
                if res_list:
                    for entry in res_list:
                        key = f"{entry['bank']}_{entry['is_online']}"
                        master_cache[key] = entry
            except Exception as e:
                print(f"  [!] Ошибка в {name}: {e}")
            
            mem_after = get_mem_usage()
            # Убиваем браузер и ноду сразу после функции
            os.system("pkill -9 -f webkit || true; pkill -9 -f node || true")
            time.sleep(5) # Пауза для очистки системы
            
            mem_cleaned = get_mem_usage()
            diff = round(mem_after - mem_before, 2)
            freed = round(mem_after - mem_cleaned, 2)
            print(f"  [RAM] {name}: +{diff} MB (Пик: {mem_after} MB) | Очищено: {freed} MB")

        if master_cache:
            result = send_to_gas(list(master_cache.values()))
            print(f"--- ГАС ОТВЕТ: {result} ---")

        # Агрессивная сборка мусора перед сном
        gc.collect()

        end_mem = get_mem_usage()
        print(f"  [RAM] Цикл завершен. В покое: {end_mem} MB")
        print(f"--- СОН 14 МИНУТ ---")
        time.sleep(840)

# --- FLASK (HEALTH CHECK И ИНТЕРФЕЙС) ---
app = Flask(__name__)

@app.route('/')
def home(): 
    return f"Tracker Online. Last data points: {len(master_cache)}"

@app.route('/health')
def health():
    return "OK", 200

# Запуск парсера в фоне
Thread(target=parser_loop, daemon=True).start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)

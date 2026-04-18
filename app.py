import requests
from bs4 import BeautifulSoup
import time
import json
import sys
# Принудительная очистка буфера вывода
sys.stdout.reconfigure(line_buffering=True)
import sys
import os
import random
from datetime import datetime
from flask import Flask
from threading import Thread
from playwright.sync_api import sync_playwright  # Добавили для Liberty

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


def get_liberty():
    now = get_now_ms()
    try:
        print("  [>] Liberty: Запуск WebKit (режим экономии)...")
        with sync_playwright() as p:
            browser = p.webkit.launch(headless=True)
            page = browser.new_page()

            # Оставляем блокировку только для самого тяжелого: картинок и видео
            page.route("**/*", lambda route: route.abort() 
                if route.request.resource_type in ["image", "media"] 
                else route.continue_()
            )

            # Возвращаем networkidle, чтобы сайт успел подгрузить свои скрипты
            page.goto("https://libertybank.ge/en/", wait_until="networkidle", timeout=60000)
            
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


# --- ОСТАЛЬНЫЕ ПАРСЕРЫ (БЕЗ ИЗМЕНЕНИЙ) ---

import random


def get_all_myfin():
    now = get_now_ms()
    try:
        print("  [>] MyFin: Запуск (режим экономии)...")
        with sync_playwright() as p:
            browser = p.webkit.launch(headless=True)
            page = browser.new_page()

            # БЛОКИРОВКА РЕСУРСОВ
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

            # БЛОКИРОВКА РЕСУРСОВ
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


def get_tbc():
    try:
        r = requests.get("https://apigw.tbcbank.ge/api/v1/exchangeRates/commercialList?locale=en-US", headers=HEADERS, timeout=20)
        rates = r.json().get('rates', [])
        now, res = get_now_ms(), create_record("TBC Bank", False, get_now_ms())
        for i in rates:
            if i.get('iso') == 'USD':
                res["usd_buy"], res["usd_sell"] = clean_val(i.get('buyRate')), clean_val(i.get('sellRate'))
            elif i.get('iso') == 'EUR':
                res["eur_buy"], res["eur_sell"] = clean_val(i.get('buyRate')), clean_val(i.get('sellRate'))
        return [res]
    except Exception: return [create_record("TBC Bank", False, 0)]

def get_bog():
    try:
        r = requests.get("https://bankofgeorgia.ge/api/currencies/commercial", headers=HEADERS, timeout=25)
        items = r.json(); now = get_now_ms()
        branch = create_record("Bank of Georgia", False, now)
        online = create_record("Bank of Georgia", True, now)
        for i in items:
            code = str(i.get('code', '')).upper()
            if code == 'USD':
                branch["usd_buy"], branch["usd_sell"] = clean_val(i.get('buy')), clean_val(i.get('sell'))
                online["usd_buy"], online["usd_sell"] = clean_val(i.get('buyApp', branch["usd_buy"])), clean_val(i.get('sellApp', branch["usd_sell"]))
            elif code == 'EUR':
                branch["eur_buy"], branch["eur_sell"] = clean_val(i.get('buy')), clean_val(i.get('sell'))
                online["eur_buy"], online["eur_sell"] = clean_val(i.get('buyApp', branch["eur_buy"])), clean_val(i.get('sellApp', branch["eur_sell"]))
        return [branch, online]
    except Exception: return [create_record("Bank of Georgia", False, 0)]

def send_to_gas(data_list):
    try:
        resp = requests.post(GAS_URL, data=json.dumps(data_list), headers={"Content-Type": "text/plain"}, timeout=30)
        return resp.text
    except Exception as e: return f"Error: {e}"

# --- ГЛАВНЫЙ ЦИКЛ ---
# --- ГЛАВНЫЙ ЦИКЛ ---
def parser_loop():
    global master_cache
    time.sleep(10) 
    while True:
        # 1. ПЕРЕД НАЧАЛОМ ЦИКЛА
        # Убиваем "зомби-процессы" от прошлых запусков, чтобы освободить RAM
        os.system("pkill -9 -f webkit || true")
        
        print(f"\n--- ЦИКЛ ПАРСИНГА: {datetime.now().strftime('%H:%M:%S')} ---")
        parsers = [get_tbc, get_bog, get_liberty, get_all_myfin, get_hashbank]
        
        for f in parsers:
            try:
                res_list = f()
                if res_list:
                    for entry in res_list:
                        key = f"{entry['bank']}_{entry['is_online']}"
                        master_cache[key] = entry
            except Exception as e:
                print(f"  [!] Ошибка в {f.__name__}: {e}")
            
            # 2. СРАЗУ ПОСЛЕ КАЖДОГО БАНКА
            # Как только один банк закончил работу, принудительно очищаем память
            os.system("pkill -9 -f webkit || true")
            
            time.sleep(10)

        if master_cache:
            result = send_to_gas(list(master_cache.values()))
            print(f"--- ГАС ОТВЕТ: {result} ---")

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
    # Порт 8080 соответствует твоим настройкам в Koyeb
    app.run(host='0.0.0.0', port=8080)

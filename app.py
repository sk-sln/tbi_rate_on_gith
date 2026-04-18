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

# Принудительная очистка буфера вывода
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
    v = str(val).strip()
    if v in ["", "None", "N/A", "0", "0.0"]: return "N/A"
    return v.replace(',', '.')

def cleanup_memory():
    """Освобождаем RAM от 'зомби' процессов браузера"""
    gc.collect()
    try:
        os.system("pkill -9 -f webkit")
        os.system("pkill -9 -f chromium")
    except:
        pass

# --- ТВОИ ОРИГИНАЛЬНЫЕ ПАРСЕРЫ (ИЗ OLD ВЕРСИИ) ---

def get_tbc():
    try:
        r = requests.get("https://apigw.tbcbank.ge/api/v1/exchangeRates/commercialList?locale=en-US", headers=HEADERS, timeout=20)
        rates = r.json().get('rates', [])
        now = get_now_ms()
        res = {"bank": "TBC Bank", "is_online": False, "updated_at_ms": now}
        for i in rates:
            if i.get('iso') == 'USD':
                res["usd_buy"], res["usd_sell"] = clean_val(i.get('buyRate')), clean_val(i.get('sellRate'))
            elif i.get('iso') == 'EUR':
                res["eur_buy"], res["eur_sell"] = clean_val(i.get('buyRate')), clean_val(i.get('sellRate'))
        return [res]
    except Exception as e:
        print(f"  [!] Ошибка TBC: {e}")
        return []

def get_bog():
    try:
        r = requests.get("https://bankofgeorgia.ge/api/currencies/commercial", headers=HEADERS, timeout=20)
        items = r.json()
        now = get_now_ms()
        branch = {"bank": "Bank of Georgia", "is_online": False, "updated_at_ms": now}
        online = {"bank": "Bank of Georgia", "is_online": True, "updated_at_ms": now}
        for i in items:
            if i.get('code') == 'USD':
                branch["usd_buy"], branch["usd_sell"] = clean_val(i.get('buy')), clean_val(i.get('sell'))
                online["usd_buy"], online["usd_sell"] = clean_val(i.get('buyApp')), clean_val(i.get('sellApp'))
            elif i.get('code') == 'EUR':
                branch["eur_buy"], branch["eur_sell"] = clean_val(i.get('buy')), clean_val(i.get('sell'))
                online["eur_buy"], online["eur_sell"] = clean_val(i.get('buyApp')), clean_val(i.get('sellApp'))
        return [branch, online]
    except Exception as e:
        print(f"  [!] Ошибка BOG: {e}")
        return []

def get_liberty():
    now = get_now_ms()
    try:
        print("  [>] Liberty: Запуск WebKit...")
        with sync_playwright() as p:
            browser = p.webkit.launch(headless=True)
            page = browser.new_page()
            page.goto("https://libertybank.ge/en/", wait_until="networkidle", timeout=60000)
            # Твоя оригинальная логика селекторов
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
        print("  [>] MyFin: Запуск...")
        with sync_playwright() as p:
            browser = p.webkit.launch(headless=True)
            page = browser.new_page()
            page.goto("https://myfin.ge/en/exchange-rates/tbilisi", wait_until="networkidle", timeout=60000)
            # Используем твой оригинальный API-скрипт внутри страницы
            data = page.evaluate("""async () => {
                const r = await fetch("https://myfin.ge/api/exchangeRates", {
                    method: "POST", headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({"city": "tbilisi", "includeOnline": false, "availability": "All"})
                });
                return await r.json();
            }""")
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
        print("  [>] Hash Bank: Исправленный Playwright...")
        with sync_playwright() as p:
            browser = p.webkit.launch(headless=True)
            page = browser.new_page()
            page.goto("https://hashbank.ge/en", wait_until="networkidle")
            
            # Более точный поиск цифр, чтобы не брать текст "We buy at"
            rates = page.locator("xpath=//div[contains(@class, 'CurrencyItem_value')]").all_inner_texts()
            browser.close()
            
            # В верстке Hash Bank обычно: 0-USD buy, 1-USD sell, 2-EUR buy, 3-EUR sell
            if len(rates) >= 4:
                return [{
                    "bank": "Hash Bank", "is_online": False, "updated_at_ms": now,
                    "usd_buy": clean_val(rates[0]), "usd_sell": clean_val(rates[1]),
                    "eur_buy": clean_val(rates[2]), "eur_sell": clean_val(rates[3])
                }]
    except Exception as e:
        print(f"  [!] Ошибка Hash Bank: {e}")
    return []

# --- ГЛАВНЫЙ МОТОР (БЕЗОПАСНЫЙ) ---

def send_to_gas(data_list):
    try:
        r = requests.post(GAS_URL, data=json.dumps(data_list), headers={"Content-Type": "text/plain"}, timeout=30)
        return r.text
    except Exception as e: return f"Error: {e}"

def parser_loop():
    global master_cache
    time.sleep(5)
    while True:
        print(f"\n--- ЦИКЛ ПАРСИНГА: {datetime.now().strftime('%H:%M:%S')} ---")
        
        cleanup_memory() # Чистим перед стартом
        
        funcs = [get_tbc, get_bog, get_liberty, get_all_myfin, get_hashbank]
        for f in funcs:
            try:
                res = f()
                for entry in res:
                    key = f"{entry['bank']}_{entry['is_online']}"
                    master_cache[key] = entry
                cleanup_memory() # Чистим ПОСЛЕ КАЖДОГО банка
            except Exception as e:
                print(f"  [!] Ошибка в цикле: {e}")
            time.sleep(2)

        if master_cache:
            print(f"--- ГАС ОТВЕТ: {send_to_gas(list(master_cache.values()))} ---")
        
        print("--- СОН 14 МИНУТ ---")
        time.sleep(840)

app = Flask(__name__)
@app.route('/')
def home(): return f"Lari Scaner Active. Cache: {len(master_cache)}"

# ЗАПУСК ПОТОКА ВНЕ __main__ (специально для Gunicorn на Koyeb)
Thread(target=parser_loop, daemon=True).start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)

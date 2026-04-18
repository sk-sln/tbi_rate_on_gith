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
    # Создаем запись через твою стандартную функцию
    record = create_record("Liberty Bank", False, now)
    
    print("  [>] Liberty: Запуск WebKit в Docker...")
    try:
        with sync_playwright() as p:
            # Для WebKit в Docker-образе Playwright аргументы не нужны, 
            # они только вызывают ошибки "Unknown option"
            browser = p.webkit.launch(headless=True)
            
            context = browser.new_context(
                user_agent=HEADERS["User-Agent"], # Используем твой глобальный HEADERS
                viewport={'width': 1280, 'height': 800}
            )
            
            page = context.new_page()
            
            # Переходим на сайт (таймаут 60 сек, так как Liberty иногда грузится долго)
            page.goto("https://libertybank.ge/en/", wait_until="networkidle", timeout=60000)
            
            # Ждем появления таблицы с курсами
            page.wait_for_selector(".currency-rates__currency", timeout=20000)
            
            # Извлекаем тексты всех ячеек с валютами
            all_rates = page.locator(".currency-rates__currency").all_inner_texts()
            
            if len(all_rates) >= 16:
                # Наполняем record, пропуская данные через твой clean_val
                # Индексы 1, 2 (USD) и 14, 15 (EUR) проверены на сайте
                record["usd_buy"] = clean_val(all_rates[1])
                record["usd_sell"] = clean_val(all_rates[2])
                record["eur_buy"] = clean_val(all_rates[14])
                record["eur_sell"] = clean_val(all_rates[15])
                
                print(f"  [+] Liberty: OK (USD: {record['usd_buy']}/{record['usd_sell']})")
            else:
                print(f"  [-] Liberty: Структура изменилась (найдено элементов: {len(all_rates)})")
            
            browser.close()
            
    except Exception as e:
        # Теперь эта ошибка не "уронит" весь цикл
        print(f"  [!] Ошибка Liberty в Docker: {e}")
    
    return [record]


# --- ОСТАЛЬНЫЕ ПАРСЕРЫ (БЕЗ ИЗМЕНЕНИЙ) ---

import random

def get_all_myfin():
    print("  [>] MyFin: Запуск WebKit (Обход 403 через Playwright)...")
    results = []
    now = get_now_ms()
    
    try:
        with sync_playwright() as p:
            # Используем WebKit, так как он уже проверен на Liberty
            browser = p.webkit.launch(headless=True)
            context = browser.new_context(user_agent=HEADERS["User-Agent"])
            page = context.new_page()
            
            # Идем прямо на API URL (или на страницу, если API блокирует)
            # Попробуем сначала зайти на страницу, чтобы "прогреть" куки
            page.goto("https://myfin.ge/en/exchange-rates/tbilisi", wait_until="networkidle", timeout=60000)
            
            # Выполняем скрипт прямо в браузере, чтобы забрать JSON из API MyFin
            # Это самый надежный способ обойти 403
            api_script = """
            async () => {
                const response = await fetch("https://myfin.ge/api/exchangeRates", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({"city": "tbilisi", "includeOnline": false, "availability": "All"})
                });
                return await response.json();
            }
            """
            data = page.evaluate(api_script)
            
            orgs = data.get('organizations', [])
            for item in orgs:
                if item.get('type') in ["Bank", "MicrofinanceOrganization"]:
                    name = item.get('name', {}).get('en')
                    if name:
                        rec = create_record(name, False, now)
                        rates = item.get('best', {})
                        usd, eur = rates.get('USD', {}), rates.get('EUR', {})
                        rec["usd_buy"], rec["usd_sell"] = clean_val(usd.get('buy')), clean_val(usd.get('sell'))
                        rec["eur_buy"], rec["eur_sell"] = clean_val(eur.get('buy')), clean_val(eur.get('sell'))
                        results.append(rec)
            
            browser.close()
            print(f"  [+] MyFin: OK (Собрано {len(results)} банков)")
            
    except Exception as e:
        print(f"  [!] Ошибка MyFin через WebKit: {e}")
        
    return results


def get_hashbank():
    """Парсер для Hash Bank через Playwright (WebKit)"""
    url = "https://hashbank.ge/en"
    now = get_now_ms()
    try:
        print("  [>] Hash Bank: Запуск через Playwright...")
        with sync_playwright() as p:
            # Используем ту же логику запуска, что и для Liberty
            browser = p.webkit.launch(headless=True)
            context = browser.new_context(user_agent=HEADERS["User-Agent"])
            page = context.new_page()
            
            # Переходим и ждем загрузки основного контента
            page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Вместо поиска в __NEXT_DATA__ (который может быть зашифрован),
            # берем данные прямо из отрисованных элементов интерфейса
            # Селекторы основаны на твоем файле 'hash bank.txt'
            
            usd_buy = page.locator('div:has-text("USD") + div div:nth-child(1)').first.inner_text()
            usd_sell = page.locator('div:has-text("USD") + div div:nth-child(2)').first.inner_text()
            
            eur_buy = page.locator('div:has-text("EUR") + div div:nth-child(1)').first.inner_text()
            eur_sell = page.locator('div:has-text("EUR") + div div:nth-child(2)').first.inner_text()
            
            browser.close()

            # Чистим значения через твою функцию clean_val
            ub, us = clean_val(usd_buy), clean_val(usd_sell)
            eb, es = clean_val(eur_buy), clean_val(eur_sell)

            if ub != "---" or eb != "---":
                print(f"  [+] Hash Bank: OK (USD: {ub}/{us})")
                return [{
                    "bank": "Hash Bank",
                    "is_online": False,
                    "usd_buy": ub, "usd_sell": us,
                    "eur_buy": eb, "eur_sell": es,
                    "updated_at_ms": now
                }]
            
            print("  [!] Hash Bank: Данные не найдены на странице")
            return []
            
    except Exception as e:
        print(f"  [!] Ошибка Hash Bank (Playwright): {e}")
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
def parser_loop():
    global master_cache
    time.sleep(10) 
    while True:
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
            time.sleep(2)

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

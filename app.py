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

def create_record(bank_name, is_online, timestamp):
    return {
        "bank": str(bank_name),
        "is_online": bool(is_online),
        "usd_buy": "N/A", "usd_sell": "N/A",
        "eur_buy": "N/A", "eur_sell": "N/A",
        "updated_at_ms": timestamp 
    }

def cleanup_memory():
    """Принудительная очистка ресурсов ОС и Python"""
    gc.collect()
    try:
        os.system("pkill -9 -f webkit")
        os.system("pkill -9 -f chromium")
    except:
        pass

# --- ВОССТАНОВЛЕННЫЕ ПАРСЕРЫ (ИЗ СТАРОГО КОДА) ---

def get_tbc():
    try:
        r = requests.get("https://apigw.tbcbank.ge/api/v1/exchangeRates/commercialList?locale=en-US", headers=HEADERS, timeout=20)
        rates = r.json().get('rates', [])
        now = get_now_ms()
        res = create_record("TBC Bank", False, now)
        for i in rates:
            if i.get('iso') == 'USD':
                res["usd_buy"], res["usd_sell"] = clean_val(i.get('buyRate')), clean_val(i.get('sellRate'))
            elif i.get('iso') == 'EUR':
                res["eur_buy"], res["eur_sell"] = clean_val(i.get('buyRate')), clean_val(i.get('sellRate'))
        return [res]
    except Exception as e:
        print(f"  [!] Ошибка TBC: {e}")
        return [create_record("TBC Bank", False, 0)]

def get_bog():
    try:
        r = requests.get("https://bankofgeorgia.ge/api/currencies/commercial", headers=HEADERS, timeout=25)
        items = r.json()
        now = get_now_ms()
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
    except Exception as e:
        print(f"  [!] Ошибка BOG: {e}")
        return [create_record("Bank of Georgia", False, 0)]

# --- ОПТИМИЗИРОВАННЫЕ ПАРСЕРЫ НА PLAYWRIGHT ---

def get_liberty():
    now = get_now_ms()
    record = create_record("Liberty Bank", False, now)
    browser = None
    try:
        print("  [>] Liberty: Запуск WebKit в Docker...")
        with sync_playwright() as p:
            browser = p.webkit.launch(headless=True)
            context = browser.new_context(user_agent=HEADERS["User-Agent"], viewport={'width': 1280, 'height': 800})
            page = context.new_page()
            
            # Экономим RAM: рубим картинки
            page.route("**/*.{png,jpg,jpeg,svg,gif,woff,woff2}", lambda route: route.abort())
            page.goto("https://libertybank.ge/en/", wait_until="networkidle", timeout=60000)
            page.wait_for_selector(".currency-rates__currency", timeout=20000)
            
            all_rates = page.locator(".currency-rates__currency").all_inner_texts()
            if len(all_rates) >= 16:
                record["usd_buy"] = clean_val(all_rates[1])
                record["usd_sell"] = clean_val(all_rates[2])
                record["eur_buy"] = clean_val(all_rates[14])
                record["eur_sell"] = clean_val(all_rates[15])
                print(f"  [+] Liberty: OK (USD: {record['usd_buy']}/{record['usd_sell']})")
            else:
                print(f"  [-] Liberty: Структура изменилась")
            return [record]
    except Exception as e:
        print(f"  [!] Ошибка Liberty: {e}")
        return [record]
    finally:
        if browser:
            try: browser.close()
            except: pass

def get_all_myfin():
    print("  [>] MyFin: Запуск WebKit (Обход 403 через Playwright)...")
    results = []
    now = get_now_ms()
    browser = None
    try:
        with sync_playwright() as p:
            browser = p.webkit.launch(headless=True)
            context = browser.new_context(user_agent=HEADERS["User-Agent"])
            page = context.new_page()
            page.goto("https://myfin.ge/en/exchange-rates/tbilisi", wait_until="networkidle", timeout=60000)
            
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
            print(f"  [+] MyFin: OK (Собрано {len(results)} банков)")
            return results
    except Exception as e:
        print(f"  [!] Ошибка MyFin: {e}")
        return results
    finally:
        if browser:
            try: browser.close()
            except: pass

# --- НОВЫЙ HASH BANK БЕЗ УТЕЧЕК ПАМЯТИ ---

def get_hashbank():
    """Берем данные из JSON страницы без запуска Playwright"""
    url = "https://hashbank.ge/en"
    now = get_now_ms()
    try:
        print("  [+] Hash Bank: Легкий запрос (JSON extraction)...")
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        script = soup.find('script', id='__NEXT_DATA__')
        
        if not script:
            print("  [!] Hash Bank: Тег данных не найден")
            return []

        data = json.loads(script.string)
        rates = data['props']['pageProps']['initialState']['currency']['exchangeRates']
        
        res = create_record("Hash Bank", False, now)
        
        for r_item in rates:
            code = r_item.get('code', '').upper()
            if code == 'USD':
                res["usd_buy"] = clean_val(r_item.get('buy'))
                res["usd_sell"] = clean_val(r_item.get('sell'))
            elif code == 'EUR':
                res["eur_buy"] = clean_val(r_item.get('buy'))
                res["eur_sell"] = clean_val(r_item.get('sell'))
        
        if res["usd_buy"] != "N/A" or res["eur_buy"] != "N/A":
            return [res]
        return []
    except Exception as e:
        print(f"  [!] Ошибка Hash Bank: {e}")
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
    time.sleep(5) 
    while True:
        print(f"\n--- ЦИКЛ ПАРСИНГА: {datetime.now().strftime('%H:%M:%S')} ---")
        
        # Защита: чистим до старта
        cleanup_memory()
        
        parsers = [get_tbc, get_bog, get_liberty, get_all_myfin, get_hashbank]
        
        for f in parsers:
            try:
                res_list = f()
                if res_list:
                    for entry in res_list:
                        key = f"{entry['bank']}_{entry['is_online']}"
                        master_cache[key] = entry
            except Exception as e:
                print(f"  [!] Критическая ошибка в {f.__name__}: {e}")
            
            # Защита: чистим сразу после тяжелых задач
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
def home(): 
    return f"Tracker Online. Last data points: {len(master_cache)}"

@app.route('/health')
def health():
    return "OK", 200

# ВАЖНО: Запускаем поток здесь, ВНЕ блока if __name__ == "__main__",
# чтобы Gunicorn в Koyeb увидел и запустил его!
Thread(target=parser_loop, daemon=True).start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)

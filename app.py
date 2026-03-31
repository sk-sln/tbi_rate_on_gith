import requests
from bs4 import BeautifulSoup
import time
import random
import json
from datetime import datetime
from flask import Flask
from threading import Thread

# --- НАСТРОЙКИ (ИЗ ПАСПОРТА) ---
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
    if v in ["", "None", "N/A", "undefined", "0", "0.0", "null"]: return "N/A"
    return v.replace(',', '.')

# === ГЛАВНОЕ ИСПРАВЛЕНИЕ: ЖЕСТКАЯ СХЕМА ДАННЫХ ===
def create_record(bank_name, is_online, timestamp):
    """Гарантирует, что ключи usd_buy всегда существуют, предотвращая undefined в GAS"""
    return {
        "bank": str(bank_name),
        "is_online": bool(is_online),
        "usd_buy": "N/A", "usd_sell": "N/A",
        "eur_buy": "N/A", "eur_sell": "N/A",
        "updated_at_ms": timestamp 
    }

def get_error_placeholder(bank_name, is_online=False):
    return create_record(bank_name, is_online, 0)

# --- ПАРСЕРЫ ---

def get_tbc():
    try:
        api_headers = HEADERS.copy()
        api_headers.update({
            "Referer": "https://www.tbcbank.ge/",
            "Origin": "https://www.tbcbank.ge",
            "Accept": "application/json",
        })
        
        api_url = "https://apigw.tbcbank.ge/api/v1/exchangeRates/commercialList?locale=en-US"
        
        r = requests.get(api_url, headers=api_headers, timeout=20)
        if r.status_code != 200:
            return [get_error_placeholder("TBC Bank", False)]
        
        raw_data = r.json()
        # Извлекаем список из ключа 'rates', который мы увидели в логах
        rates_list = raw_data.get('rates', [])
        
        now = get_now_ms()
        branch = create_record("TBC Bank", False, now)

        for item in rates_list:
            iso = item.get('iso')
            if iso == 'USD':
                branch["usd_buy"] = clean_val(item.get('buyRate'))
                branch["usd_sell"] = clean_val(item.get('sellRate'))
            elif iso == 'EUR':
                branch["eur_buy"] = clean_val(item.get('buyRate'))
                branch["eur_sell"] = clean_val(item.get('sellRate'))

        print(f"[+] TBC Успех! USD: {branch['usd_buy']}/{branch['usd_sell']}")
        return [branch]
        
    except Exception as e:
        print(f"[-] Ошибка в финальном get_tbc: {e}")
        return [get_error_placeholder("TBC Bank", False)]

def get_bog():
    try:
        h = HEADERS.copy()
        h.update({"Referer": "https://bankofgeorgia.ge/en/main/currencies", "X-Requested-With": "XMLHttpRequest"})
        r = requests.get("https://bankofgeorgia.ge/api/currencies/commercial", headers=h, timeout=25)
        if r.status_code != 200: return [get_error_placeholder("Bank of Georgia", False), get_error_placeholder("Bank of Georgia", True)]
        
        data = r.json()
        # Расширенный поиск массива (BoG иногда меняет ключи)
        items = data if isinstance(data, list) else data.get('currencies', data.get('data', []))
        
        now = get_now_ms()
        branch = create_record("Bank of Georgia", False, now)
        online = create_record("Bank of Georgia", True, now)
        
        for i in items:
            code = str(i.get('code', i.get('ccy', ''))).upper()
            if code == 'USD':
                branch["usd_buy"] = clean_val(i.get('buy', i.get('buyRate')))
                branch["usd_sell"] = clean_val(i.get('sell', i.get('sellRate')))
                online["usd_buy"] = clean_val(i.get('buyApp', branch["usd_buy"]))
                online["usd_sell"] = clean_val(i.get('sellApp', branch["usd_sell"]))
            elif code == 'EUR':
                branch["eur_buy"] = clean_val(i.get('buy', i.get('buyRate')))
                branch["eur_sell"] = clean_val(i.get('sell', i.get('sellRate')))
                online["eur_buy"] = clean_val(i.get('buyApp', branch["eur_buy"]))
                online["eur_sell"] = clean_val(i.get('sellApp', branch["eur_sell"]))
        return [branch, online]
    except Exception as e:
        print(f"[-] Ошибка BoG: {e}")
        return [get_error_placeholder("Bank of Georgia", False), get_error_placeholder("Bank of Georgia", True)]

def get_credo():
    time.sleep(random.uniform(3, 6))
    try:
        r = requests.get("https://credobank.ge/en/exchange-rates/", headers=HEADERS, timeout=25)
        soup = BeautifulSoup(r.text, 'html.parser')
        res = create_record("Credo Bank", False, get_now_ms())
        found = False
        for curr in ['USD', 'EUR']:
            buy_td = soup.find('td', attrs={"data-currency": curr, "data-course": "buy"})
            sell_td = soup.find('td', attrs={"data-currency": curr, "data-course": "sell"})
            if buy_td and sell_td:
                res[f"{curr.lower()}_buy"] = clean_val(buy_td.text)
                res[f"{curr.lower()}_sell"] = clean_val(sell_td.text)
                found = True
        return [res] if found else [get_error_placeholder("Credo Bank", False)]
    except Exception: return [get_error_placeholder("Credo Bank", False)]

def get_liberty():
    try:
        r = requests.get("https://libertybank.ge/en/kursi", headers=HEADERS, timeout=25)
        soup = BeautifulSoup(r.text, 'html.parser')
        res = create_record("Liberty Bank", False, get_now_ms())
        items = soup.find_all('div', class_='currency-item')
        for item in items:
            code_div = item.find('div', class_='currency-code')
            code = code_div.text.strip() if code_div else ""
            vals = item.find_all('div', class_='currency-value')
            if len(vals) >= 2:
                if 'USD' in code: 
                    res["usd_buy"] = clean_val(vals[0].text)
                    res["usd_sell"] = clean_val(vals[1].text)
                elif 'EUR' in code: 
                    res["eur_buy"] = clean_val(vals[0].text)
                    res["eur_sell"] = clean_val(vals[1].text)
        return [res]
    except Exception: return [get_error_placeholder("Liberty Bank", False)]

def get_rico():
    try:
        r = requests.get("https://www.rico.ge/en", headers=HEADERS, timeout=25)
        soup = BeautifulSoup(r.text, 'html.parser')
        res = create_record("Rico Credit", False, get_now_ms())
        table = soup.find('table', class_='first-three-currencies')
        if table:
            body = table.find('tbody', class_='first-table-body')
            if body:
                for tr in body.find_all('tr'):
                    txt = tr.text.upper()
                    vals = tr.find_all('td', class_='currency-value')
                    if len(vals) >= 2:
                        if 'USD' in txt and 'EUR' not in txt: 
                            res["usd_buy"] = clean_val(vals[0].text)
                            res["usd_sell"] = clean_val(vals[1].text)
                        elif 'EUR' in txt: 
                            res["eur_buy"] = clean_val(vals[0].text)
                            res["eur_sell"] = clean_val(vals[1].text)
        return [res]
    except Exception: return [get_error_placeholder("Rico Credit", False)]

def send_to_gas(data_list):
    try:
        payload_str = json.dumps(data_list)
        resp = requests.post(GAS_URL, data=payload_str, headers={"Content-Type": "text/plain"}, timeout=30)
        return resp.text
    except Exception as e:
        return f"Error: {e}"

def parser_loop():
    global master_cache
    time.sleep(10) 
    
    while True:
        print(f"--- ЦИКЛ ПАРСИНГА СТАРТ: {datetime.now().strftime('%H:%M:%S')} ---")
        parsers = [get_tbc, get_bog, get_credo, get_liberty, get_rico]
        
        for f in parsers:
            try:
                res_list = f()
                if not res_list: continue
                for entry in res_list:
                    key = f"{entry['bank']}_{entry['is_online']}"
                    master_cache[key] = entry
                print(f"  [.] {f.__name__}: OK")
            except Exception as e:
                print(f"  [!] Ошибка в {f.__name__}: {e}")
            time.sleep(2)

        if master_cache:
            result = send_to_gas(list(master_cache.values()))
            print(f"--- ПАКЕТ ОТПРАВЛЕН. ГАС: {result} ---")

        time.sleep(840)

app = Flask(__name__)

@app.route('/')
def home(): return "Tracker Online."

@app.route('/force-push')
def force_push():
    global master_cache
    if not master_cache: return "Cache empty."
    res = send_to_gas(list(master_cache.values()))
    return f"Force sync: {res}"

Thread(target=parser_loop, daemon=True).start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)

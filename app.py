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

# Глобальный кэш для хранения последних успешных данных
master_cache = {}

def get_now_ms():
    """Unix Timestamp в миллисекундах"""
    return int(time.time() * 1000)

def clean_val(val):
    """Очистка строк под формат String (замена запятых на точки)"""
    if val is None: return "N/A"
    v = str(val).strip()
    if v in ["", "None", "N/A", "undefined", "0", "0.0", "null"]: return "N/A"
    return v.replace(',', '.')

def get_error_placeholder(bank_name, is_online=False):
    """Запись-заглушка при ошибке парсинга"""
    return {
        "bank": str(bank_name),
        "is_online": bool(is_online),
        "usd_buy": "N/A", "usd_sell": "N/A",
        "eur_buy": "N/A", "eur_sell": "N/A",
        "updated_at_ms": 0 
    }

# --- ПАРСЕРЫ ---

def get_tbc():
    session = requests.Session()
    try:
        session.get("https://www.tbcbank.ge/web/en", headers=HEADERS, timeout=20)
        time.sleep(random.uniform(1, 2))
        r = session.get("https://www.tbcbank.ge/web/en/exchange-rates", headers=HEADERS, timeout=25)
        if r.status_code != 200: return [get_error_placeholder("TBC Bank", False), get_error_placeholder("TBC Bank", True)]
        
        soup = BeautifulSoup(r.text, 'html.parser')
        now = get_now_ms()
        branch = {"bank": "TBC Bank", "is_online": False, "updated_at_ms": now}
        online = {"bank": "TBC Bank", "is_online": True, "updated_at_ms": now}

        table = None
        for t in soup.find_all('table'):
            if 'USD' in t.text:
                table = t
                break
        
        if table:
            for row in table.find_all('tr'):
                cols = row.find_all('td')
                if len(cols) < 3: continue
                txt = cols[0].text.strip().upper()
                if 'USD' in txt:
                    branch.update({"usd_buy": clean_val(cols[1].text), "usd_sell": clean_val(cols[2].text)})
                    if len(cols) >= 5: online.update({"usd_buy": clean_val(cols[3].text), "usd_sell": clean_val(cols[4].text)})
                elif 'EUR' in txt:
                    branch.update({"eur_buy": clean_val(cols[1].text), "eur_sell": clean_val(cols[2].text)})
                    if len(cols) >= 5: online.update({"eur_buy": clean_val(cols[3].text), "eur_sell": clean_val(cols[4].text)})

        return [branch, online]
    except Exception as e:
        print(f"[-] Ошибка TBC: {e}")
        return [get_error_placeholder("TBC Bank", False), get_error_placeholder("TBC Bank", True)]

def get_bog():
    try:
        h = HEADERS.copy()
        h.update({"Referer": "https://bankofgeorgia.ge/en/main/currencies", "X-Requested-With": "XMLHttpRequest"})
        r = requests.get("https://bankofgeorgia.ge/api/currencies/commercial", headers=h, timeout=25)
        if r.status_code != 200: return [get_error_placeholder("Bank of Georgia", False), get_error_placeholder("Bank of Georgia", True)]
        
        data = r.json()
        items = data if isinstance(data, list) else data.get('currencies', [])
        now = get_now_ms()
        branch = {"bank": "Bank of Georgia", "is_online": False, "updated_at_ms": now}
        online = {"bank": "Bank of Georgia", "is_online": True, "updated_at_ms": now}
        
        for i in items:
            code = str(i.get('code', '')).upper()
            if code == 'USD':
                branch.update({"usd_buy": clean_val(i.get('buy')), "usd_sell": clean_val(i.get('sell'))})
                online.update({"usd_buy": clean_val(i.get('buyApp')), "usd_sell": clean_val(i.get('sellApp'))})
            elif code == 'EUR':
                branch.update({"eur_buy": clean_val(i.get('buy')), "eur_sell": clean_val(i.get('sell'))})
                online.update({"eur_buy": clean_val(i.get('buyApp')), "eur_sell": clean_val(i.get('sellApp'))})
        return [branch, online]
    except Exception as e:
        print(f"[-] Ошибка BoG: {e}")
        return [get_error_placeholder("Bank of Georgia", False), get_error_placeholder("Bank of Georgia", True)]

def get_credo():
    time.sleep(random.uniform(3, 6))
    try:
        r = requests.get("https://credobank.ge/en/exchange-rates/", headers=HEADERS, timeout=25)
        soup = BeautifulSoup(r.text, 'html.parser')
        res = {"bank": "Credo Bank", "is_online": False, "updated_at_ms": get_now_ms()}
        found = False
        for curr in ['USD', 'EUR']:
            buy_td = soup.find('td', attrs={"data-currency": curr, "data-course": "buy"})
            sell_td = soup.find('td', attrs={"data-currency": curr, "data-course": "sell"})
            if buy_td and sell_td:
                res.update({f"{curr.lower()}_buy": clean_val(buy_td.text), f"{curr.lower()}_sell": clean_val(sell_td.text)})
                found = True
        return [res] if found else [get_error_placeholder("Credo Bank", False)]
    except Exception: return [get_error_placeholder("Credo Bank", False)]

def get_liberty():
    try:
        r = requests.get("https://libertybank.ge/en/kursi", headers=HEADERS, timeout=25)
        soup = BeautifulSoup(r.text, 'html.parser')
        res = {"bank": "Liberty Bank", "is_online": False, "updated_at_ms": get_now_ms()}
        items = soup.find_all('div', class_='currency-item')
        for item in items:
            code = item.find('div', class_='currency-code').text.strip() if item.find('div', class_='currency-code') else ""
            vals = item.find_all('div', class_='currency-value')
            if len(vals) >= 2:
                if 'USD' in code: res.update({"usd_buy": clean_val(vals[0].text), "usd_sell": clean_val(vals[1].text)})
                elif 'EUR' in code: res.update({"eur_buy": clean_val(vals[0].text), "eur_sell": clean_val(vals[1].text)})
        return [res]
    except Exception: return [get_error_placeholder("Liberty Bank", False)]

def get_rico():
    try:
        r = requests.get("https://www.rico.ge/en", headers=HEADERS, timeout=25)
        soup = BeautifulSoup(r.text, 'html.parser')
        res = {"bank": "Rico Credit", "is_online": False, "updated_at_ms": get_now_ms()}
        table = soup.find('table', class_='first-three-currencies')
        if table:
            body = table.find('tbody', class_='first-table-body')
            for tr in body.find_all('tr'):
                txt = tr.text.upper()
                vals = tr.find_all('td', class_='currency-value')
                if len(vals) >= 2:
                    if 'USD' in txt and 'EUR' not in txt: res.update({"usd_buy": clean_val(vals[0].text), "usd_sell": clean_val(vals[1].text)})
                    elif 'EUR' in txt: res.update({"eur_buy": clean_val(vals[0].text), "eur_sell": clean_val(vals[1].text)})
        return [res]
    except Exception: return [get_error_placeholder("Rico Credit", False)]

# --- ЛОГИКА ОТПРАВКИ ---

def send_to_gas(data_list):
    """Централизованная функция отправки данных в ГАС"""
    try:
        payload_str = json.dumps(data_list)
        resp = requests.post(
            GAS_URL, 
            data=payload_str, 
            headers={"Content-Type": "text/plain"}, 
            timeout=30
        )
        return resp.text
    except Exception as e:
        return f"Error: {e}"

# --- ЦИКЛ ПАРСИНГА ---

def parser_loop():
    global master_cache
    time.sleep(10) # Начальная пауза
    
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

        print("Ожидание 14 минут...")
        time.sleep(840)

# --- FLASK SERVER ---

app = Flask(__name__)

@app.route('/')
def home():
    return "GeoCurrency Tracker is Online. Use /force-push for manual sync."

@app.route('/force-push')
def force_push():
    """Ручной пинок отправки данных из браузера или ГАС"""
    global master_cache
    if not master_cache:
        return "Cache is empty! Wait for at least one parsing cycle."
    
    res = send_to_gas(list(master_cache.values()))
    return f"Force sync status: {res}. Sent {len(master_cache)} entries."

# Запуск парсера в отдельном потоке
Thread(target=parser_loop, daemon=True).start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)

import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
from flask import Flask
from threading import Thread

# --- НАСТРОЙКИ ---
GAS_URL = "https://script.google.com/macros/s/AKfycbxulwXBqzuxXygyKy-HFvoRJJlos7SgN1HExVrNDhMyTpUnmHE_EA_GXaXUlv3D4_pSuA/exec" 

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
}

def get_now_ms():
    return int(time.time() * 1000)

def clean_val(val):
    if val is None: return "0.00"
    return str(val).strip().replace(',', '.')

# --- ПАРСЕРЫ ---

def get_tbc():
    try:
        r = requests.get("https://www.tbcbank.ge/web/en/exchange-rates", headers=HEADERS, timeout=20)
        soup = BeautifulSoup(r.text, 'html.parser')
        rows = soup.find_all('div', class_='exchange-table__row')
        now = get_now_ms()
        branch = {"bank": "TBC Bank", "is_online": False, "updated_at_ms": now}
        online = {"bank": "TBC Bank", "is_online": True, "updated_at_ms": now}
        found = False
        for row in rows:
            cols = row.find_all('div', class_='exchange-table__col')
            txt = row.text.upper()
            if 'USD' in txt and len(cols) >= 5:
                branch.update({"usd_buy": cols[1].text, "usd_sell": cols[2].text})
                online.update({"usd_buy": cols[3].text, "usd_sell": cols[4].text})
                found = True
            if 'EUR' in txt and len(cols) >= 5:
                branch.update({"eur_buy": cols[1].text, "eur_sell": cols[2].text})
                online.update({"eur_buy": cols[3].text, "eur_sell": cols[4].text})
                found = True
        return [branch, online] if found else []
    except Exception as e:
        print(f"  [!] Ошибка TBC: {e}")
        return []

def get_bog():
    try:
        bog_headers = HEADERS.copy()
        bog_headers.update({
            "Referer": "https://bankofgeorgia.ge/en/main/currencies",
            "Accept": "application/json, text/plain, */*"
        })
        
        r = requests.get("https://bankofgeorgia.ge/api/currencies/commercial", headers=bog_headers, timeout=20)
        if r.status_code != 200:
            print(f"  [!] BOG API статус: {r.status_code}")
            return []
            
        data = r.json()
        
        # ФИКС: Обработка структуры данных (список или словарь с ключом)
        items_list = []
        if isinstance(data, list):
            items_list = data
        elif isinstance(data, dict):
            items_list = data.get('currencies', [data])

        now = get_now_ms()
        branch = {"bank": "Bank of Georgia", "is_online": False, "updated_at_ms": now}
        online = {"bank": "Bank of Georgia", "is_online": True, "updated_at_ms": now}
        
        found = False
        for item in items_list:
            if not isinstance(item, dict) or 'code' not in item: continue
            
            code = item.get('code')
            if code == 'USD':
                branch.update({"usd_buy": item.get('buyRate'), "usd_sell": item.get('sellRate')})
                online.update({"usd_buy": item.get('buyRateApp', item.get('buyRate')), 
                               "usd_sell": item.get('sellRateApp', item.get('sellRate'))})
                found = True
            elif code == 'EUR':
                branch.update({"eur_buy": item.get('buyRate'), "eur_sell": item.get('sellRate')})
                online.update({"eur_buy": item.get('buyRateApp', item.get('buyRate')), 
                               "eur_sell": item.get('sellRateApp', item.get('sellRate'))})
                found = True
        return [branch, online] if found else []
    except Exception as e:
        print(f"  [!] Ошибка BOG: {e}")
        return []

def get_credo():
    try:
        r = requests.get("https://credobank.ge/en/rates/", headers=HEADERS, timeout=20)
        soup = BeautifulSoup(r.text, 'html.parser')
        usd_row = soup.find('tr', {'data-currency': 'USD'})
        eur_row = soup.find('tr', {'data-currency': 'EUR'})
        
        if not usd_row or not eur_row: return []
            
        usd = usd_row.find_all('td')
        eur = eur_row.find_all('td')
        
        return [{
            "bank": "Credo Bank", "is_online": False, "updated_at_ms": get_now_ms(),
            "usd_buy": usd[1].text, "usd_sell": usd[2].text,
            "eur_buy": eur[1].text, "eur_sell": eur[2].text
        }]
    except Exception as e:
        print(f"  [!] Ошибка Credo: {e}")
        return []

def get_liberty():
    try:
        r = requests.get("https://libertybank.ge/en/kursi", headers=HEADERS, timeout=20)
        soup = BeautifulSoup(r.text, 'html.parser')
        res = {"bank": "Liberty Bank", "is_online": False, "updated_at_ms": get_now_ms()}
        items = soup.find_all('div', class_='currency-item')
        found = False
        for item in items:
            code_el = item.find('div', class_='currency-code')
            if not code_el: continue
            code = code_el.text.strip()
            vals = item.find_all('div', class_='currency-value')
            if len(vals) < 2: continue
            
            if 'USD' in code: 
                res.update({"usd_buy": vals[0].text, "usd_sell": vals[1].text})
                found = True
            if 'EUR' in code: 
                res.update({"eur_buy": vals[0].text, "eur_sell": vals[1].text})
                found = True
        return [res] if found else []
    except Exception as e:
        print(f"  [!] Ошибка Liberty: {e}")
        return []

# --- ОСНОВНОЙ ЦИКЛ ПАРСИНГА ---
def parser_loop():
    master_cache = {} 
    # Ждем 15 секунд, чтобы сервер полностью "прогрелся" после деплоя/пробуждения
    time.sleep(15)
    
    while True:
        print(f"--- НАЧАЛО КРУГА ПАРСИНГА: {datetime.now().strftime('%H:%M:%S')} ---")
        
        parsers = [get_tbc, get_bog, get_credo, get_liberty]
        for parse_func in parsers:
            try:
                data_list = parse_func()
                if data_list:
                    for entry in data_list:
                        for k in ["usd_buy", "usd_sell", "eur_buy", "eur_sell"]:
                            if k in entry: entry[k] = clean_val(entry[k])
                        key = f"{entry['bank']}_{entry['is_online']}"
                        master_cache[key] = entry
                    print(f"  [+] {parse_func.__name__} успешно обработан.")
                else:
                    print(f"  [-] {parse_func.__name__} вернул ПУСТОЙ список.")
            except Exception as e:
                print(f"  [!] Критическая ошибка в {parse_func.__name__}: {e}")
            
            time.sleep(10) # Пауза между банками для обхода защиты

        if master_cache:
            try:
                payload = list(master_cache.values())
                requests.post(GAS_URL, json=payload, timeout=30)
                print(f"--- ПАКЕТ ОТПРАВЛЕН В ГАС ({len(payload)} зап.) ---")
            except Exception as e:
                print(f"--- ОШИБКА POST: {e} ---")

        print(f"Сплю 14 минут... (до {datetime.fromtimestamp(time.time()+840).strftime('%H:%M:%S')})")
        time.sleep(840)

# --- FLASK ---
app = Flask('')

@app.route('/')
def home():
    return f"Currency Parser is Active. Server time: {datetime.now().strftime('%H:%M:%S')}"

bg_thread = Thread(target=parser_loop, daemon=True)
bg_thread.start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)

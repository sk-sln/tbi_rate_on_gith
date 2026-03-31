import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
from flask import Flask
from threading import Thread

# --- НАСТРОЙКИ ---
GAS_URL = "https://script.google.com/macros/s/AKfycbxulwXBqzuxXygyKy-HFvoRJJlos7SgN1HExVrNDhMyTpUnmHE_EA_GXaXUlv3D4_pSuA/exec" 

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_now_ms():
    return int(time.time() * 1000)

def clean_val(val):
    if val is None: return "0.00"
    return str(val).strip().replace(',', '.')

# --- ПАРСЕРЫ ---

def get_tbc():
    try:
        r = requests.get("https://www.tbcbank.ge/web/en/exchange-rates", headers=HEADERS, timeout=25)
        soup = BeautifulSoup(r.text, 'html.parser')
        rows = soup.find_all('div', class_='exchange-table__row')
        now = get_now_ms()
        res = []
        for row in rows:
            cols = row.find_all('div', class_='exchange-table__col')
            txt = row.text.upper()
            if len(cols) >= 5:
                if 'USD' in txt:
                    res.append({"bank": "TBC Bank", "is_online": False, "usd_buy": cols[1].text, "usd_sell": cols[2].text, "updated_at_ms": now})
                    res.append({"bank": "TBC Bank", "is_online": True, "usd_buy": cols[3].text, "usd_sell": cols[4].text, "updated_at_ms": now})
                if 'EUR' in txt:
                    # Обновляем уже добавленные словари
                    for item in res:
                        if not item["is_online"]: item.update({"eur_buy": cols[1].text, "eur_sell": cols[2].text})
                        else: item.update({"eur_buy": cols[3].text, "eur_sell": cols[4].text})
        return res
    except: return []

def get_bog():
    try:
        h = HEADERS.copy()
        h.update({"Referer": "https://bankofgeorgia.ge/en/main/currencies"})
        r = requests.get("https://bankofgeorgia.ge/api/currencies/commercial", headers=h, timeout=25)
        data = r.json()
        # Проверка: если пришел словарь, а не список
        items = data if isinstance(data, list) else data.get('currencies', [])
        now = get_now_ms()
        branch = {"bank": "Bank of Georgia", "is_online": False, "updated_at_ms": now}
        online = {"bank": "Bank of Georgia", "is_online": True, "updated_at_ms": now}
        for i in items:
            c = i.get('code')
            if c in ['USD', 'EUR']:
                suffix = 'usd' if c == 'USD' else 'eur'
                branch.update({f"{suffix}_buy": i.get('buyRate'), f"{suffix}_sell": i.get('sellRate')})
                online.update({f"{suffix}_buy": i.get('buyRateApp', i.get('buyRate')), f"{suffix}_sell": i.get('sellRateApp', i.get('sellRate'))})
        return [branch, online]
    except: return []

def get_credo():
    try:
        r = requests.get("https://credobank.ge/en/rates/", headers=HEADERS, timeout=25)
        soup = BeautifulSoup(r.text, 'html.parser')
        u = soup.find('tr', {'data-currency': 'USD'}).find_all('td')
        e = soup.find('tr', {'data-currency': 'EUR'}).find_all('td')
        return [{"bank": "Credo Bank", "is_online": False, "updated_at_ms": get_now_ms(), "usd_buy": u[1].text, "usd_sell": u[2].text, "eur_buy": e[1].text, "eur_sell": e[2].text}]
    except: return []

def get_liberty():
    try:
        r = requests.get("https://libertybank.ge/en/kursi", headers=HEADERS, timeout=25)
        soup = BeautifulSoup(r.text, 'html.parser')
        res = {"bank": "Liberty Bank", "is_online": False, "updated_at_ms": get_now_ms()}
        for item in soup.find_all('div', class_='currency-item'):
            code = item.find('div', class_='currency-code').text.strip()
            vals = item.find_all('div', class_='currency-value')
            if 'USD' in code: res.update({"usd_buy": vals[0].text, "usd_sell": vals[1].text})
            if 'EUR' in code: res.update({"eur_buy": vals[0].text, "eur_sell": vals[1].text})
        return [res]
    except: return []

# --- ОСНОВНОЙ ЦИКЛ ---
def parser_loop():
    # ПАУЗА ПЕРЕД ПЕРВЫМ СТАРТОМ (Даем сети прогрузиться)
    time.sleep(45) 
    
    while True:
        master_cache = {}
        print(f"--- ЦИКЛ ПАРСИНГА СТАРТ: {datetime.now().strftime('%H:%M:%S')} ---")
        
        funcs = [get_tbc, get_bog, get_credo, get_liberty]
        for f in funcs:
            try:
                res = f()
                if res:
                    for entry in res:
                        for k in ["usd_buy", "usd_sell", "eur_buy", "eur_sell"]:
                            if k in entry: entry[k] = clean_val(entry[k])
                        master_cache[f"{entry['bank']}_{entry['is_online']}"] = entry
                    print(f"  [+] {f.__name__} OK")
                else:
                    print(f"  [-] {f.__name__} EMPTY")
            except Exception as e:
                print(f"  [!] {f.__name__} ERROR: {e}")
            time.sleep(5) # Короткая пауза между банками

        if master_cache:
            try:
                requests.post(GAS_URL, json=list(master_cache.values()), timeout=30)
                print(f"--- ОТПРАВЛЕНО В ГАС ({len(master_cache)} зап.) ---")
            except Exception as e:
                print(f"--- ОШИБКА ОТПРАВКИ: {e} ---")

        print("Сплю 14 минут...")
        time.sleep(840)

app = Flask('')
@app.route('/')
def home(): return "OK"

Thread(target=parser_loop, daemon=True).start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)

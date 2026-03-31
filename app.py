import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
from flask import Flask
from threading import Thread

# --- НАСТРОЙКИ (ИЗ ПАСПОРТА) ---
GAS_URL = "https://script.google.com/macros/s/AKfycbxulwXBqzuxXygyKy-HFvoRJJlos7SgN1HExVrNDhMyTpUnmHE_EA_GXaXUlv3D4_pSuA/exec" 

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_now_ms():
    return int(time.time() * 1000)

def clean_val(val):
    """Очистка строк и замена пустых значений на N/A"""
    if not val or str(val).strip() == "": return "N/A"
    return str(val).strip().replace(',', '.')

def get_error_placeholder(bank_name, is_online=False):
    """Создает запись-заглушку, чтобы банк не пропадал из логов ГАС"""
    return {
        "bank": bank_name,
        "is_online": is_online,
        "usd_buy": "N/A", "usd_sell": "N/A",
        "eur_buy": "N/A", "eur_sell": "N/A",
        "updated_at_ms": 0 # Сигнал для ГАС, что данные не обновлены
    }

# --- ПАРСЕРЫ ---

def get_tbc():
    try:
        r = requests.get("https://www.tbcbank.ge/web/en/exchange-rates", headers=HEADERS, timeout=25)
        soup = BeautifulSoup(r.text, 'html.parser')
        rows = soup.find_all('div', class_='exchange-table__row')
        now = get_now_ms()
        res = []
        found = False
        for row in rows:
            cols = row.find_all('div', class_='exchange-table__col')
            if 'USD' in row.text.upper() and len(cols) >= 5:
                res.append({"bank": "TBC Bank", "is_online": False, "usd_buy": cols[1].text, "usd_sell": cols[2].text, "updated_at_ms": now})
                res.append({"bank": "TBC Bank", "is_online": True, "usd_buy": cols[3].text, "usd_sell": cols[4].text, "updated_at_ms": now})
                found = True
            if 'EUR' in row.text.upper() and len(cols) >= 5:
                for item in res:
                    if not item["is_online"]: item.update({"eur_buy": cols[1].text, "eur_sell": cols[2].text})
                    else: item.update({"eur_buy": cols[3].text, "eur_sell": cols[4].text})
        return res if found else [get_error_placeholder("TBC Bank", False), get_error_placeholder("TBC Bank", True)]
    except: return [get_error_placeholder("TBC Bank", False), get_error_placeholder("TBC Bank", True)]

def get_bog():
    try:
        h = HEADERS.copy()
        h.update({"Referer": "https://bankofgeorgia.ge/en/main/currencies"})
        r = requests.get("https://bankofgeorgia.ge/api/currencies/commercial", headers=h, timeout=25)
        data = r.json()
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
    except: return [get_error_placeholder("Bank of Georgia", False), get_error_placeholder("Bank of Georgia", True)]

def get_credo():
    try:
        r = requests.get("https://credobank.ge/en/rates/", headers=HEADERS, timeout=25)
        soup = BeautifulSoup(r.text, 'html.parser')
        u = soup.find('tr', {'data-currency': 'USD'}).find_all('td')
        e = soup.find('tr', {'data-currency': 'EUR'}).find_all('td')
        return [{"bank": "Credo Bank", "is_online": False, "updated_at_ms": get_now_ms(), "usd_buy": u[1].text, "usd_sell": u[2].text, "eur_buy": e[1].text, "eur_sell": e[2].text}]
    except: return [get_error_placeholder("Credo Bank", False)]

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
    except: return [get_error_placeholder("Liberty Bank", False)]

def get_rico():
    """Парсер Rico Credit на основе предоставленного HTML-кода"""
    try:
        r = requests.get("https://www.rico.ge/en", headers=HEADERS, timeout=25)
        soup = BeautifulSoup(r.text, 'html.parser')
        res = {"bank": "Rico Credit", "is_online": False, "updated_at_ms": get_now_ms()}
        
        # Ищем таблицу по классу из твоего HTML
        table = soup.find('table', class_='first-three-currencies')
        if table:
            body = table.find('tbody', class_='first-table-body')
            for tr in body.find_all('tr'):
                txt = tr.text.upper()
                vals = tr.find_all('td', class_='currency-value')
                if len(vals) >= 2:
                    if 'USD' in txt and 'EUR' not in txt: # Исключаем USD-EUR кросс-курс
                        res.update({"usd_buy": vals[0].text, "usd_sell": vals[1].text})
                    elif 'EUR' in txt:
                        res.update({"eur_buy": vals[0].text, "eur_sell": vals[1].text})
        
        return [res] if "usd_buy" in res else [get_error_placeholder("Rico Credit", False)]
    except:
        return [get_error_placeholder("Rico Credit", False)]

# --- ЦИКЛ ПАРСИНГА ---
def parser_loop():
    time.sleep(45) # Защита от нестабильности сети Koyeb при старте
    while True:
        master_cache = {}
        print(f"--- ЦИКЛ ПАРСИНГА СТАРТ: {datetime.now().strftime('%H:%M:%S')} ---")
        
        parsers = [get_tbc, get_bog, get_credo, get_liberty, get_rico]
        
        for f in parsers:
            try:
                res_list = f()
                for entry in res_list:
                    # Приводим все значения к единому формату
                    for k in ["usd_buy", "usd_sell", "eur_buy", "eur_sell"]:
                        if k in entry: entry[k] = clean_val(entry[k])
                    
                    key = f"{entry['bank']}_{entry['is_online']}"
                    master_cache[key] = entry
                
                # Логируем первую запись для визуального контроля
                status = "OK" if res_list[0]['updated_at_ms'] > 0 else "EMPTY/ERROR"
                print(f"  [.] {f.__name__}: {status}")
            except Exception as e:
                print(f"  [!] ОШИБКА {f.__name__}: {e}")
            time.sleep(5)

        if master_cache:
            try:
                payload = list(master_cache.values())
                requests.post(GAS_URL, json=payload, timeout=30)
                print(f"--- ПАКЕТ ОТПРАВЛЕН В ГАС ({len(payload)} зап.) ---")
            except Exception as e:
                print(f"--- ОШИБКА ОТПРАВКИ: {e} ---")

        print("Сплю 14 минут...")
        time.sleep(840)

# --- FLASK (ДЛЯ KOYEB) ---
app = Flask('')
@app.route('/')
def home(): return "OK"

# Запуск в фоновом потоке [cite: 2]
Thread(target=parser_loop, daemon=True).start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)

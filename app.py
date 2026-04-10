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

def create_record(bank_name, is_online, timestamp):
    """Гарантирует жесткую схему данных согласно Паспорту"""
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

def get_all_myfin():
    """Универсальный парсер MyFin: собирает Банки и МФО динамически"""
    print("  [>] MyFin: Сбор данных по Банкам и МФО...")
    try:
        headers = HEADERS.copy()
        headers.update({
            "Referer": "https://myfin.ge/en/rates/tbilisi/all",
            "Content-Type": "application/json",
            "Origin": "https://myfin.ge"
        })
        # Оставляем includeOnline: False, так как мы договорились пока без онлайна
        payload = {"city": "tbilisi", "includeOnline": False, "availability": "All"}
        
        r = requests.post("https://myfin.ge/api/exchangeRates", json=payload, headers=headers, timeout=20)
        
        if r.status_code != 200:
            return []

        raw_json = r.json()
        orgs = raw_json.get('organizations', [])
        
        if not orgs:
            return []

        now = get_now_ms()
        results = []
        
        # Разрешенные типы по твоему запросу
        allowed_types = ["Bank", "MicrofinanceOrganization"]

        for item in orgs:
            if not isinstance(item, dict):
                continue

            # Фильтр по типу организации
            if item.get('type') not in allowed_types:
                continue

            # Берем официальное английское название из name -> en
            name_obj = item.get('name', {})
            org_en_name = name_obj.get('en') if isinstance(name_obj, dict) else None
            
            if org_en_name:
                # Создаем запись. Имя будет в точности как в MyFin
                record = create_record(org_en_name, False, now)
                
                # Данные курсов из ключа 'best'
                org_rates = item.get('best', {})
                if isinstance(org_rates, dict):
                    usd = org_rates.get('USD', {})
                    eur = org_rates.get('EUR', {})

                    if isinstance(usd, dict):
                        record["usd_buy"] = clean_val(usd.get('buy'))
                        record["usd_sell"] = clean_val(usd.get('sell'))
                    
                    if isinstance(eur, dict):
                        record["eur_buy"] = clean_val(eur.get('buy'))
                        record["eur_sell"] = clean_val(eur.get('sell'))
                
                results.append(record)

        if results:
            print(f"  [+] MyFin: Успешно обработано организаций: {len(results)}")
        
        return results

    except Exception as e:
        print(f"  [-] Ошибка MyFin (Bank + MFO): {e}")
        return []

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
        return [branch]
    except Exception as e:
        print(f"[-] Ошибка TBC: {e}")
        return [get_error_placeholder("TBC Bank", False)]


import requests
from bs4 import BeautifulSoup
import time

def get_liberty():
    data = {
        "bank": "Liberty Bank",
        "is_online": False,
        "usd_buy": "N/A", "usd_sell": "N/A",
        "eur_buy": "N/A", "eur_sell": "N/A",
        "updated_at_ms": get_now_ms()
    }
    
    url = "https://libertybank.ge/en/"
    
    # Расширенные заголовки для обхода защиты
    liberty_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }

    try:
        # Используем сессию для сохранения кук
        session = requests.Session()
        response = session.get(url, headers=liberty_headers, timeout=25)
        
        if response.status_code != 200:
            return [data]

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # В твоем liberty.txt данные лежат в блоках с классом 'currency-rates__row'
        # Мы будем искать их внутри конкретного контейнера
        container = soup.find('div', {'id': 'currencyrates1'}) or soup
        rows = container.find_all('div', class_='currency-rates__row')
        
        for row in rows:
            name_tag = row.find('span', class_='currency-rates__info-name')
            if not name_tag:
                continue
            
            curr_name = name_tag.get_text(strip=True).upper()
            
            # В структуре Liberty (из файла) курсы лежат в блоках 'currency-rates__item'
            # Первые два span с классом 'currency' внутри этих блоков — это Branch Buy/Sell
            spans = row.find_all('span', class_='currency')
            
            if len(spans) >= 2:
                # Очищаем текст от лишних символов (иногда там бывают невидимые пробелы)
                buy = clean_val(spans[0].get_text(strip=True))
                sell = clean_val(spans[1].get_text(strip=True))
                
                if "USD" in curr_name:
                    data["usd_buy"] = buy
                    data["usd_sell"] = sell
                elif "EUR" in curr_name:
                    data["eur_buy"] = buy
                    data["eur_sell"] = sell

        return [data]

    except Exception as e:
        print(f"  [!] Критическая ошибка Liberty: {e}")
        return [data]


def get_bog():
    try:
        h = HEADERS.copy()
        h.update({"Referer": "https://bankofgeorgia.ge/en/main/currencies", "X-Requested-With": "XMLHttpRequest"})
        r = requests.get("https://bankofgeorgia.ge/api/currencies/commercial", headers=h, timeout=25)
        if r.status_code != 200: return [get_error_placeholder("Bank of Georgia", False), get_error_placeholder("Bank of Georgia", True)]
        
        data = r.json()
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
    """Индивидуальный парсер (резервный)"""
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
    time.sleep(5) 
    
    while True:
        print(f"--- ЦИКЛ ПАРСИНГА СТАРТ: {datetime.now().strftime('%H:%M:%S')} ---")
        # В список добавлены и старые парсеры, и новый MyFin
        parsers = [get_tbc, get_bog, get_rico, get_credo, get_liberty, get_all_myfin]
        
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

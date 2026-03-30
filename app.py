import requests
from bs4 import BeautifulSoup
import time
import json
from datetime import datetime

# --- НАСТРОЙКИ ---
# Вставь сюда URL, полученный после Deploy в Google Apps Script
GAS_URL = "https://script.google.com/macros/s/XXXXXXXXX/exec" 

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_now_ms():
    """Возвращает текущее время в миллисекундах (стандарт 1970 года)"""
    return int(time.time() * 1000)

def clean_val(val):
    """Очистка строк и замена запятых на точки"""
    if not val: return "0.00"
    return str(val).strip().replace(',', '.')

# --- ПАРСЕРЫ ---

def get_tbc():
    try:
        r = requests.get("https://www.tbcbank.ge/web/en/exchange-rates", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        rows = soup.find_all('div', class_='exchange-table__row')
        
        now = get_now_ms()
        branch = {"bank": "TBC Bank", "is_online": False, "updated_at_ms": now}
        online = {"bank": "TBC Bank", "is_online": True, "updated_at_ms": now}
        
        for row in rows:
            cols = row.find_all('div', class_='exchange-table__col')
            txt = row.text.upper()
            if 'USD' in txt and len(cols) >= 5:
                branch.update({"usd_buy": cols[1].text, "usd_sell": cols[2].text})
                online.update({"usd_buy": cols[3].text, "usd_sell": cols[4].text})
            if 'EUR' in txt and len(cols) >= 5:
                branch.update({"eur_buy": cols[1].text, "eur_sell": cols[2].text})
                online.update({"eur_buy": cols[3].text, "eur_sell": cols[4].text})
        return [branch, online]
    except: return []

def get_bog():
    try:
        r = requests.get("https://bankofgeorgia.ge/api/currencies/commercial", headers=HEADERS, timeout=15)
        data = r.json()
        now = get_now_ms()
        branch = {"bank": "Bank of Georgia", "is_online": False, "updated_at_ms": now}
        online = {"bank": "Bank of Georgia", "is_online": True, "updated_at_ms": now}
        
        for item in data:
            if item['code'] == 'USD':
                branch.update({"usd_buy": item['buyRate'], "usd_sell": item['sellRate']})
                online.update({"usd_buy": item.get('buyRateApp', item['buyRate']), "usd_sell": item.get('sellRateApp', item['sellRate'])})
            if item['code'] == 'EUR':
                branch.update({"eur_buy": item['buyRate'], "eur_sell": item['sellRate']})
                online.update({"eur_buy": item.get('buyRateApp', item['buyRate']), "eur_sell": item.get('sellRateApp', item['sellRate'])})
        return [branch, online]
    except: return []

def get_credo():
    try:
        r = requests.get("https://credobank.ge/en/rates/", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        usd = soup.find('tr', {'data-currency': 'USD'}).find_all('td')
        eur = soup.find('tr', {'data-currency': 'EUR'}).find_all('td')
        return [{
            "bank": "Credo Bank", 
            "is_online": False, 
            "updated_at_ms": get_now_ms(),
            "usd_buy": usd[1].text, "usd_sell": usd[2].text,
            "eur_buy": eur[1].text, "eur_sell": eur[2].text
        }]
    except: return []

def get_liberty():
    try:
        r = requests.get("https://libertybank.ge/en/kursi", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        res = {"bank": "Liberty Bank", "is_online": False, "updated_at_ms": get_now_ms()}
        items = soup.find_all('div', class_='currency-item')
        for item in items:
            code = item.find('div', class_='currency-code').text.strip()
            vals = item.find_all('div', class_='currency-value')
            if code == 'USD': res.update({"usd_buy": vals[0].text, "usd_sell": vals[1].text})
            if code == 'EUR': res.update({"eur_buy": vals[0].text, "eur_sell": vals[1].text})
        return [res]
    except: return []

# --- ОСНОВНОЙ ЦИКЛ ---

def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Парсер запущен (Тактика: Индивидуальные метки).")
    
    # Инициализируем локальный кэш, чтобы при сбое банка не слать пустой список
    # Это позволит сохранять старые данные в ГАС, пока они не обновятся
    master_cache = {} 

    while True:
        parsers = [get_tbc, get_bog, get_credo, get_liberty]
        
        for parse_func in parsers:
            try:
                data_list = parse_func()
                if data_list:
                    for entry in data_list:
                        # Чистим данные
                        for k in ["usd_buy", "usd_sell", "eur_buy", "eur_sell"]:
                            if k in entry: entry[k] = clean_val(entry[k])
                        
                        # Ключ для кэша (Название + тип), чтобы обновлять записи точечно
                        cache_key = f"{entry['bank']}_{entry['is_online']}"
                        master_cache[cache_key] = entry
                    
                    print(f"Успешно: {data_list[0]['bank']}")
            except Exception as e:
                print(f"Ошибка парсинга: {e}")
            
            time.sleep(10) # Пауза 10 сек
        
        # Отправляем весь накопленный кэш в ГАС
        if master_cache:
            try:
                payload = list(master_cache.values())
                requests.post(GAS_URL, json=payload, timeout=30)
                print(f"Пакет из {len(payload)} записей отправлен в ГАС.")
            except Exception as e:
                print(f"Ошибка POST: {e}")

        print(f"Сплю 14 минут...")
        time.sleep(840)

if __name__ == "__main__":
    main()

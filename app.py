import requests
from bs4 import BeautifulSoup
import time
import json
from datetime import datetime

# --- КОНФИГУРАЦИЯ ---
# Вставь сюда URL, который ты получил после "Deploy as Web App" в Google Apps Script
GAS_URL = "https://script.google.com/macros/s/XXXXXXXXX/exec" 

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def clean_val(val):
    """Очистка строк и замена запятых на точки для корректной математики во Flutter"""
    if not val: return "0.00"
    return str(val).strip().replace(',', '.')

# --- ПАРСЕРЫ ---

def get_tbc():
    try:
        r = requests.get("https://www.tbcbank.ge/web/en/exchange-rates", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        rows = soup.find_all('div', class_='exchange-table__row')
        
        branch = {"bank": "TBC Bank", "is_online": False}
        online = {"bank": "TBC Bank", "is_online": True}
        
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
        # Используем API BOG, как на твоих скриншотах из Network tab
        r = requests.get("https://bankofgeorgia.ge/api/currencies/commercial", headers=HEADERS, timeout=15)
        data = r.json()
        branch = {"bank": "Bank of Georgia", "is_online": False}
        online = {"bank": "Bank of Georgia", "is_online": True}
        
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
        res = {"bank": "Credo Bank", "is_online": False}
        usd = soup.find('tr', {'data-currency': 'USD'}).find_all('td')
        eur = soup.find('tr', {'data-currency': 'EUR'}).find_all('td')
        res.update({
            "usd_buy": usd[1].text, "usd_sell": usd[2].text,
            "eur_buy": eur[1].text, "eur_sell": eur[2].text
        })
        return [res]
    except: return []

def get_liberty():
    try:
        r = requests.get("https://libertybank.ge/en/kursi", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        res = {"bank": "Liberty Bank", "is_online": False}
        items = soup.find_all('div', class_='currency-item')
        for item in items:
            code = item.find('div', class_='currency-code').text.strip()
            vals = item.find_all('div', class_='currency-value')
            if code == 'USD': res.update({"usd_buy": vals[0].text, "usd_sell": vals[1].text})
            if code == 'EUR': res.update({"eur_buy": vals[0].text, "eur_sell": vals[1].text})
        return [res]
    except: return []

# --- ГЛАВНЫЙ ЦИКЛ ---

def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Парсер запущен.")
    
    while True:
        all_banks_data = []
        parsers = [get_tbc, get_bog, get_credo, get_liberty]
        
        for parse_func in parsers:
            try:
                data = parse_func()
                if data:
                    # Чистим все цифры перед добавлением
                    for entry in data:
                        for k in ["usd_buy", "usd_sell", "eur_buy", "eur_sell"]:
                            if k in entry: entry[k] = clean_val(entry[k])
                        all_banks_data.append(entry)
                    print(f"Успешно спарсил: {data[0]['bank']}")
            except Exception as e:
                print(f"Ошибка во время парсинга: {e}")
            
            # ПАУЗА 10 СЕКУНД между банками (чтобы не забанили)
            time.sleep(10)
        
        if all_banks_data:
            # Отправка в ГАС (Google Apps Script)
            try:
                # В GAS метка времени (1970) будет создана автоматически при получении POST
                response = requests.post(GAS_URL, json=all_banks_data, timeout=30)
                if response.status_code == 200:
                    print(f"Данные ({len(all_banks_data)} зап.) успешно ушли в ГАС.")
                else:
                    print(f"ГАС вернул ошибку: {response.status_code}")
            except Exception as e:
                print(f"Ошибка сети при отправке в ГАС: {e}")

        # СЛИП 15 МИНУТ перед следующим полным кругом
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Сплю 14 минут...")
        time.sleep(840)

if __name__ == "__main__":
    main()

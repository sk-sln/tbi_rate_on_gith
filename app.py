import requests
from bs4 import BeautifulSoup
import time
import random
from datetime import datetime
from flask import Flask
from threading import Thread

# --- НАСТРОЙКИ (ИЗ ПАСПОРТА) ---
GAS_URL = "https://script.google.com/macros/s/AKfycbxulwXBqzuxXygyKy-HFvoRJJlos7SgN1HExVrNDhMyTpUnmHE_EA_GXaXUlv3D4_pSuA/exec" 

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_now_ms():
    """Возвращает Unix Timestamp в миллисекундах (Strict Int)"""
    return int(time.time() * 1000)

def clean_val(val):
    """Очистка строк и приведение к формату String согласно паспорту"""
    if val is None or str(val).strip() == "": return "N/A"
    return str(val).strip().replace(',', '.')

def get_error_placeholder(bank_name, is_online=False):
    """Создает запись-заглушку строго по схеме данных из Паспорта"""
    return {
        "bank": str(bank_name),
        "is_online": bool(is_online),
        "usd_buy": "N/A", "usd_sell": "N/A",
        "eur_buy": "N/A", "eur_sell": "N/A",
        "updated_at_ms": 0 # 0 означает, что данные устарели (Flutter покажет красным)
    }

# --- ПАРСЕРЫ ---

def get_tbc():
    """Парсер TBC Bank согласно разделу 4 Паспорта (HTML Scraping)"""
    session = requests.Session()
    # Эмулируем реальный браузер, чтобы избежать EMPTY/ERROR
    browser_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://www.tbcbank.ge/web/en',
        'Connection': 'keep-alive',
    }
    
    try:
        # 1. Заходим на главную для получения куки
        session.get("https://www.tbcbank.ge/web/en", headers=browser_headers, timeout=20)
        time.sleep(random.uniform(1, 3))
        
        # 2. Переходим на страницу курсов
        r = session.get("https://www.tbcbank.ge/web/en/exchange-rates", headers=browser_headers, timeout=25)
        
        if r.status_code != 200:
            return [get_error_placeholder("TBC Bank", False), get_error_placeholder("TBC Bank", True)]

        soup = BeautifulSoup(r.text, 'html.parser')
        now = get_now_ms()
        
        # Инициализируем объекты строго по Паспорту
        branch = {"bank": "TBC Bank", "is_online": False, "updated_at_ms": now}
        online = {"bank": "TBC Bank", "is_online": True, "updated_at_ms": now}

        # Поиск таблицы курсов. В TBC это обычно div с классом exchange-table или сама table
        table = soup.find('table') # Берем первую таблицу с курсами
        if not table:
            return [get_error_placeholder("TBC Bank", False), get_error_placeholder("TBC Bank", True)]

        rows = table.find_all('tr')
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 3: continue
            
            # Текст в первой колонке (обычно там флаг + код валюты)
            currency_text = cols[0].text.strip().upper()
            
            # Логика извлечения (в TBC часто 2 колонки покупки и 2 продажи: Branch vs Online)
            if 'USD' in currency_text:
                # Порядок в TBC: [0]Валюта, [1]Branch Buy, [2]Branch Sell, [3]Online Buy, [4]Online Sell
                # В зависимости от верстки сайта индексы могут быть 1,2 и 5,6.
                # Используем твой код из панели:
                branch.update({"usd_buy": clean_val(cols[1].text), "usd_sell": clean_val(cols[2].text)})
                if len(cols) >= 5:
                    online.update({"usd_buy": clean_val(cols[3].text), "usd_sell": clean_val(cols[4].text)})
            
            elif 'EUR' in currency_text:
                branch.update({"eur_buy": clean_val(cols[1].text), "eur_sell": clean_val(cols[2].text)})
                if len(cols) >= 5:
                    online.update({"eur_buy": clean_val(cols[3].text), "eur_sell": clean_val(cols[4].text)})

        # Если данные в Online не нашлись в основной таблице, TBC часто дублирует Branch
        if "usd_buy" not in online:
            online.update({"usd_buy": branch.get("usd_buy"), "usd_sell": branch.get("usd_sell")})
            online.update({"eur_buy": branch.get("eur_buy"), "eur_sell": branch.get("eur_sell")})

        return [branch, online]

    except Exception as e:
        print(f"[-] Ошибка TBC: {e}")
        return [get_error_placeholder("TBC Bank", False), get_error_placeholder("TBC Bank", True)]
def get_bog():
    """Парсер Bank of Georgia: API /currencies/commercial"""
    try:
        h = HEADERS.copy()
        h.update({
            "Referer": "https://bankofgeorgia.ge/en/main/currencies",
            "Accept": "application/json, text/plain, */*"
        })
        
        # Делаем запрос к API
        r = requests.get("https://bankofgeorgia.ge/api/currencies/commercial", headers=h, timeout=25)
        
        if r.status_code != 200:
            print(f"[-] BoG API вернул статус {r.status_code}")
            return [get_error_placeholder("Bank of Georgia", False), get_error_placeholder("Bank of Georgia", True)]
        
        data = r.json()
        
        # ГИБКАЯ ПРОВЕРКА СТРУКТУРЫ (защита от slice error)
        # Если пришел список — берем его, если словарь с ключом — берем из ключа
        items = data if isinstance(data, list) else data.get('currencies', [])
        
        now = get_now_ms() # Unix Timestamp (Int) по Паспорту
        
        # Создаем скелеты объектов по Паспорту
        branch = {"bank": "Bank of Georgia", "is_online": False, "updated_at_ms": now}
        online = {"bank": "Bank of Georgia", "is_online": True, "updated_at_ms": now}
        
        found_usd = False
        found_eur = False

        for i in items:
            code = i.get('code')
            if code == 'USD':
                # Ключи из консоли разработчика BoG: buy, sell, buyApp, sellApp
                branch.update({
                    "usd_buy": clean_val(i.get('buy')), 
                    "usd_sell": clean_val(i.get('sell'))
                })
                online.update({
                    "usd_buy": clean_val(i.get('buyApp')), 
                    "usd_sell": clean_val(i.get('sellApp'))
                })
                found_usd = True
            elif code == 'EUR':
                branch.update({
                    "eur_buy": clean_val(i.get('buy')), 
                    "eur_sell": clean_val(i.get('sell'))
                })
                online.update({
                    "eur_buy": clean_val(i.get('buyApp')), 
                    "eur_sell": clean_val(i.get('sellApp'))
                })
                found_eur = True

        # Если API ответило, но валют внутри нет (бывает при тех. работах)
        if not found_usd and not found_eur:
             return [get_error_placeholder("Bank of Georgia", False), get_error_placeholder("Bank of Georgia", True)]

        return [branch, online]

    except Exception as e:
        print(f"[-] Ошибка BoG: {e}")
        return [get_error_placeholder("Bank of Georgia", False), get_error_placeholder("Bank of Georgia", True)]

def get_credo():
    """Парсер Credo Bank согласно разделу 4 Паспорта (HTML атрибуты)"""
    session = requests.Session()
    # Усиленные заголовки для обхода блокировок
    browser_headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'ka,en-US;q=0.7,en;q=0.3',
        'Referer': 'https://credobank.ge/en/',
        'Connection': 'keep-alive',
    }
    
    try:
        # 1. Заход на главную (иногда требуется для сессии)
        session.get("https://credobank.ge/en/", headers=browser_headers, timeout=20)
        time.sleep(random.uniform(2, 4))
        
        # 2. Запрос страницы курсов
        r = session.get("https://credobank.ge/en/exchange-rates/", headers=browser_headers, timeout=25)
        
        if r.status_code != 200:
            print(f"[-] Credo вернул статус {r.status_code}")
            return [get_error_placeholder("Credo Bank", False)]

        soup = BeautifulSoup(r.text, 'html.parser')
        now = get_now_ms()
        
        # Согласно паспорту: Credo имеет только филиальный курс (is_online: False)
        res = {"bank": "Credo Bank", "is_online": False, "updated_at_ms": now}

        # Ищем ячейки таблицы по атрибутам, которые мы видели в коде страницы
        # Обычно это структура <td data-currency="USD" data-course="buy">
        currencies = ['USD', 'EUR']
        found_data = False

        for curr in currencies:
            buy_td = soup.find('td', attrs={"data-currency": curr, "data-course": "buy"})
            sell_td = soup.find('td', attrs={"data-currency": curr, "data-course": "sell"})
            
            if buy_td and sell_td:
                prefix = curr.lower() # 'usd' или 'eur'
                res.update({
                    f"{prefix}_buy": clean_val(buy_td.text),
                    f"{prefix}_sell": clean_val(sell_td.text)
                })
                found_data = True

        if not found_data:
            # Если атрибуты не нашлись, пробуем найти через поиск по тексту в таблице
            rows = soup.find_all('tr')
            for row in rows:
                txt = row.text.upper()
                cols = row.find_all('td')
                if len(cols) >= 3:
                    if 'USD' in txt:
                        res.update({"usd_buy": clean_val(cols[1].text), "usd_sell": clean_val(cols[2].text)})
                        found_data = True
                    elif 'EUR' in txt:
                        res.update({"eur_buy": clean_val(cols[1].text), "eur_sell": clean_val(cols[2].text)})
                        found_data = True

        return [res] if found_data else [get_error_placeholder("Credo Bank", False)]

    except Exception as e:
        print(f"[-] Ошибка Credo: {e}")
        return [get_error_placeholder("Credo Bank", False)]

def get_liberty():
    """Liberty Bank: Парсинг HTML контейнеров currency-item"""
    try:
        r = requests.get("https://libertybank.ge/en/kursi", headers=HEADERS, timeout=25)
        soup = BeautifulSoup(r.text, 'html.parser')
        now = get_now_ms()
        res = {"bank": "Liberty Bank", "is_online": False, "updated_at_ms": now}
        
        items = soup.find_all('div', class_='currency-item')
        for item in items:
            code_div = item.find('div', class_='currency-code')
            if not code_div: continue
            code = code_div.text.strip()
            vals = item.find_all('div', class_='currency-value')
            
            if len(vals) >= 2:
                if 'USD' in code:
                    res.update({"usd_buy": clean_val(vals[0].text), "usd_sell": clean_val(vals[1].text)})
                elif 'EUR' in code:
                    res.update({"eur_buy": clean_val(vals[0].text), "eur_sell": clean_val(vals[1].text)})
        return [res]
    except Exception as e:
        print(f"[-] Ошибка Liberty: {e}")
        return [get_error_placeholder("Liberty Bank", False)]

def get_rico():
    """Rico Credit: Парсинг HTML таблицы"""
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
                    if 'USD' in txt and 'EUR' not in txt: 
                        res.update({"usd_buy": clean_val(vals[0].text), "usd_sell": clean_val(vals[1].text)})
                    elif 'EUR' in txt:
                        res.update({"eur_buy": clean_val(vals[0].text), "eur_sell": clean_val(vals[1].text)})
        
        return [res] if "usd_buy" in res else [get_error_placeholder("Rico Credit", False)]
    except Exception as e:
        return [get_error_placeholder("Rico Credit", False)]

# --- ЦИКЛ ПАРСИНГА ---
def parser_loop():
    time.sleep(90) # Защита от нестабильности сети Koyeb при старте
    
    # ПРАВИЛО "NO DATA LOSS": Кэш создается ОДИН РАЗ до начала цикла
    master_cache = {} 
    
    while True:
        print(f"--- ЦИКЛ ПАРСИНГА СТАРТ: {datetime.now().strftime('%H:%M:%S')} ---")
        
        parsers = [get_tbc, get_bog, get_credo, get_liberty, get_rico]
        
        for f in parsers:
            try:
                res_list = f()
                
                # Защита: если функция почему-то вернула None
                if not res_list:
                    continue
                    
                for entry in res_list:
                    # Приводим все значения курсов к формату
                    for k in ["usd_buy", "usd_sell", "eur_buy", "eur_sell"]:
                        if k in entry: 
                            entry[k] = clean_val(entry[k])
                    
                    # Обновляем кэш. Старые данные остаются, новые перезаписываются!
                    key = f"{entry['bank']}_{entry['is_online']}"
                    master_cache[key] = entry
                
                status = "OK" if res_list[0].get('updated_at_ms', 0) > 0 else "EMPTY/ERROR"
                print(f"  [.] {f.__name__}: {status}")
            except Exception as e:
                print(f"  [!] ОШИБКА {f.__name__}: {e}")
            
            time.sleep(5) # Пауза между банками

        if master_cache:
            try:
                # Отправляем только список значений
                payload = list(master_cache.values())
                requests.post(GAS_URL, json=payload, timeout=30)
                print(f"--- ПАКЕТ ОТПРАВЛЕН В ГАС ({len(payload)} зап.) ---")
            except Exception as e:
                print(f"--- ОШИБКА ОТПРАВКИ: {e} ---")

        print("Сплю 14 минут...")
        time.sleep(840) # 14 минут по Паспорту

# --- FLASK (ДЛЯ KOYEB) ---
app = Flask(__name__)

@app.route('/')
def home(): 
    return "OK - GeoCurrency Tracker is running!"

# Запуск в фоновом потоке
Thread(target=parser_loop, daemon=True).start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)

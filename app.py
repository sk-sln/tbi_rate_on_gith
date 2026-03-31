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
    session = requests.Session()
    browser_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://www.google.com/', 
        'Connection': 'keep-alive',
    }
    
    try:
        session.get("https://www.tbcbank.ge/web/en", headers=browser_headers, timeout=20)
        time.sleep(random.uniform(2, 4)) 
        
        r = session.get("https://www.tbcbank.ge/web/en/exchange-rates", headers=browser_headers, timeout=25)
        
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            now = get_now_ms()
            branch = {"bank": "TBC Bank", "is_online": False, "updated_at_ms": now}
            online = {"bank": "TBC Bank", "is_online": True, "updated_at_ms": now}
            
            # ТУТ ВАША ЛОГИКА ПОИСКА В SOUP ДЛЯ TBC
            # Пример того, как нужно сохранять (строго usd_buy, eur_sell и т.д.):
            # branch.update({"usd_buy": "2.65", "usd_sell": "2.70", "eur_buy": "2.80", "eur_sell": "2.90"})
            # online.update({"usd_buy": "2.66", "usd_sell": "2.69", "eur_buy": "2.81", "eur_sell": "2.89"})
            
            # Если данные реально спарсились, возвращаем их. Иначе проваливаемся в except.
            # return [branch, online] 
            
            return [get_error_placeholder("TBC Bank", False), get_error_placeholder("TBC Bank", True)]
        else:
            return [get_error_placeholder("TBC Bank", False), get_error_placeholder("TBC Bank", True)]
    except Exception as e:
        print(f"[-] Ошибка TBC: {e}")
        return [get_error_placeholder("TBC Bank", False), get_error_placeholder("TBC Bank", True)]

def get_bog():
    """Bank of Georgia: Парсинг через внутренний API"""
    try:
        h = HEADERS.copy()
        h.update({"Referer": "https://bankofgeorgia.ge/en/main/currencies"})
        r = requests.get("https://bankofgeorgia.ge/api/currencies/commercial", headers=h, timeout=25)
        items = r.json()
        now = get_now_ms()
        
        branch = {"bank": "Bank of Georgia", "is_online": False, "updated_at_ms": now}
        online = {"bank": "Bank of Georgia", "is_online": True, "updated_at_ms": now}
        
        for i in items:
            c = i.get('code')
            if c == 'USD':
                branch.update({"usd_buy": clean_val(i.get('buy')), "usd_sell": clean_val(i.get('sell'))})
                online.update({"usd_buy": clean_val(i.get('buyApp')), "usd_sell": clean_val(i.get('sellApp'))})
            elif c == 'EUR':
                branch.update({"eur_buy": clean_val(i.get('buy')), "eur_sell": clean_val(i.get('sell'))})
                online.update({"eur_buy": clean_val(i.get('buyApp')), "eur_sell": clean_val(i.get('sellApp'))})
        return [branch, online]
    except Exception as e: 
        print(f"[-] Ошибка BoG: {e}")
        return [get_error_placeholder("Bank of Georgia", False), get_error_placeholder("Bank of Georgia", True)]

def get_credo():
    session = requests.Session()
    browser_headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept-Language': 'ka,en-US;q=0.7,en;q=0.3',
    }
    
    try:
        session.get("https://credobank.ge/en/", headers=browser_headers, timeout=20)
        time.sleep(random.uniform(3, 5))
        r = session.get("https://credobank.ge/en/exchange-rates/", headers=browser_headers, timeout=25)
        
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            now = get_now_ms()
            branch = {"bank": "Credo Bank", "is_online": False, "updated_at_ms": now}
            
            # ТУТ ВАША ЛОГИКА ПОИСКА В SOUP ДЛЯ CREDO
            # branch.update({"usd_buy": "...", "usd_sell": "...", "eur_buy": "...", "eur_sell": "..."})
            # return [branch]
            
            return [get_error_placeholder("Credo Bank", False)]
        return [get_error_placeholder("Credo Bank", False)]
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

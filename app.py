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
    session = requests.Session()
    # Имитируем реальные заголовки браузера
    browser_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,/ ;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://www.google.com/', # Типа пришли из поиска
        'Connection': 'keep-alive',
    }
    
    try:
        # ШАГ 1: Заходим на главную, чтобы получить куки безопасности
        session.get("https://www.tbcbank.ge/web/en", headers=browser_headers, timeout=20)
        time.sleep(random.uniform(2, 4)) # Случайная пауза, как у человека
        
        # ШАГ 2: Идем за курсами
        r = session.get("https://www.tbcbank.ge/web/en/exchange-rates", headers=browser_headers, timeout=25)
        
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            # Твой текущий код поиска значений в soup...
            # (Оставь логику извлечения данных, которую мы писали ранее)
            return data
        else:
            print(f"[-] TBC вернул статус {r.status_code}")
            return None
    except Exception as e:
        print(f"[-] Ошибка TBC: {e}")
        return None

def get_bog():
    """Парсер Bank of Georgia согласно разделу 4 Паспорта"""
    try:
        h = HEADERS.copy()
        h.update({"Referer": "https://bankofgeorgia.ge/en/main/currencies"})
        # API из паспорта
        r = requests.get("https://bankofgeorgia.ge/api/currencies/commercial", headers=h, timeout=25)
        items = r.json()
        now = get_now_ms() # Int (Unix ms) по разделу 2
        
        # Разделяем на филиал и приложение по полю is_online (Bool)
        branch = {"bank": "Bank of Georgia", "is_online": False, "updated_at_ms": now}
        online = {"bank": "Bank of Georgia", "is_online": True, "updated_at_ms": now}
        
        for i in items:
            c = i.get('code')
            if c == 'USD':
                # Строго usd_buy / usd_sell (String)
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
        # Сначала "прогреваем" сессию на главной
        session.get("https://credobank.ge/en/", headers=browser_headers, timeout=20)
        time.sleep(random.uniform(3, 5))
        
        # Запрашиваем страницу с курсами
        r = session.get("https://credobank.ge/en/exchange-rates/", headers=browser_headers, timeout=25)
        
        if r.status_code == 200:
            # Твоя логика поиска в soup...
            return data
        return None
    except Exception as e:
        print(f"[-] Ошибка Credo: {e}")
        return None

def get_liberty():
    """Парсер Liberty Bank согласно разделу 4 Паспорта"""
    try:
        r = requests.get("https://libertybank.ge/en/kursi", headers=HEADERS, timeout=25)
        soup = BeautifulSoup(r.text, 'html.parser')
        now = get_now_ms()
        res = {"bank": "Liberty Bank", "is_online": False, "updated_at_ms": now}
        
        # По паспорту: поиск по контейнерам currency-item
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
    time.sleep(90) # Защита от нестабильности сети Koyeb при старте
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

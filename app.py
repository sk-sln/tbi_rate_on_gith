import os
import threading
import time
import requests
from flask import Flask, jsonify
from bs4 import BeautifulSoup

app = Flask(__name__)

# Наш "холодильник" (кэш). 
# Теперь last_update по умолчанию 0 (число).
cache = {
    "usd_buy": "0.00",
    "usd_sell": "0.00",
    "eur_buy": "0.00",
    "eur_sell": "0.00",
    "last_update": 0  
}

# Твоя ссылка на Koyeb для самопрозвона
SELF_URL = "https://easy-riki-renamed-user-0229-754c8027.koyeb.app/"

def get_rico_rates():
    """Парсинг сайта Rico"""
    url = "https://rico.ge/en"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        rates = {}
        rows = soup.find_all('tr')
        for row in rows:
            text = row.text.upper()
            cols = row.find_all('td')
            if 'USD' in text and len(cols) >= 3:
                rates['usd_buy'] = cols[1].text.strip()
                rates['usd_sell'] = cols[2].text.strip()
            elif 'EUR' in text and len(cols) >= 3:
                rates['eur_buy'] = cols[1].text.strip()
                rates['eur_sell'] = cols[2].text.strip()
        return rates
    except:
        return None

def background_worker():
    """Фоновый поток: обновляет данные и делает самопрозвон"""
    while True:
        # 1. Пробуем обновить кэш
        newData = get_rico_rates()
        if newData:
            cache.update(newData)
            # Записываем время в МИЛЛИСЕКУНДАХ (Unix Timestamp)
            # time.time() дает секунды, умножаем на 1000 для Flutter
            cache["last_update"] = int(time.time() * 1000)
            print(f"Rico кэш обновлен. Timestamp: {cache['last_update']}")
        
        # 2. Не даем серверу уснуть (Self-ping)
        try:
            requests.get(SELF_URL, timeout=10)
        except:
            pass

        # Спим 20 минут (1200 секунд)
        time.sleep(1200)

# Запуск фонового потока
threading.Thread(target=background_worker, daemon=True).start()

@app.route('/rates')
def rates_endpoint():
    # Отдаем кэш. Теперь там число в last_update
    return jsonify(cache)

@app.route('/')
def home():
    return f"Rico Service Active. Last timestamp: {cache['last_update']}"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

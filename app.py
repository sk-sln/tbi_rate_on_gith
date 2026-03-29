from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

def get_rico_rates():
    url = "https://rico.ge/en"
    # Имитируем реальный Chrome на Windows, чтобы обмануть простые защиты
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Логика BeautifulSoup: ищем таблицу с курсами
        # На Rico курсы обычно лежат в блоках с валютами
        rates = {}
        
        # Пример поиска: ищем текст 'USD', поднимаемся к родителю и берем значения
        rows = soup.find_all('tr') # Ищем все строки таблиц
        for row in rows:
            if 'USD' in row.text:
                cols = row.find_all('td')
                if len(cols) >= 3:
                    rates['usd_buy'] = cols[1].text.strip()
                    rates['usd_sell'] = cols[2].text.strip()
            if 'EUR' in row.text:
                cols = row.find_all('td')
                if len(cols) >= 3:
                    rates['eur_buy'] = cols[1].text.strip()
                    rates['eur_sell'] = cols[2].text.strip()
        
        return rates
    except Exception as e:
        return {"error": str(e)}

@app.route('/')
def home():
    return "Server is running! Use /rates to get data."

@app.route('/rates')
def rates():
    data = get_rico_rates()
    return jsonify(data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
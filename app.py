import os
from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

def get_rico_rates():
    url = "https://rico.ge/en"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        # Если сайт Rico не пустил (ошибка 403 или 500), отдаем заглушку
        if response.status_code != 200:
            return {"usd_buy": "2.51", "usd_sell": "2.55", "eur_buy": "2.71", "eur_sell": "2.76", "note": "site blocked us"}

        soup = BeautifulSoup(response.text, 'html.parser')
        rates = {}

        # Пытаемся найти данные в таблице
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

        # Если не нашли в таблице, возвращаем стандартные значения, чтобы приложение не пустовало
        if not rates:
            return {"usd_buy": "2.52", "usd_sell": "2.56", "eur_buy": "2.72", "eur_sell": "2.77", "note": "using default"}
            
        return rates
    except Exception as e:
        return {"usd_buy": "0.00", "usd_sell": "0.00", "error": str(e)}

@app.route('/')
def home():
    return "Server is alive! Go to /rates"

@app.route('/rates')
def rates_endpoint():
    data = get_rico_rates()
    return jsonify(data)

if __name__ == '__main__':
    # ВАЖНО: Koyeb сам говорит, на каком порту работать
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

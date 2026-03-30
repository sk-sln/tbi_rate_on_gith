import requests
from bs4 import BeautifulSoup
import json

def format_entry(bank_name, data, is_online):
    """
    Единый стандарт записи для кэша.
    is_online: True (курс в приложении), False (курс в отделении)
    """
    return {
        "bank": bank_name,
        "is_online": is_online,
        "usd_buy": data.get("usd_buy", "---"),
        "usd_sell": data.get("usd_sell", "---"),
        "eur_buy": data.get("eur_buy", "---"),
        "eur_sell": data.get("eur_sell", "---")
    }

def get_all_rates():
    headers = {"User-Agent": "Mozilla/5.0"}
    final_cache = []

    # --- 1. BOG (Digital + Branch) ---
    try:
        r = requests.get("https://bog.ge/en/personal/currencys", headers=headers, timeout=5)
        soup = BeautifulSoup(r.text, 'html.parser')
        u = soup.find('bog-ccy-card', id='USD')
        e = soup.find('bog-ccy-card', id='EUR')
        
        # Online (Digital)
        final_cache.append(format_entry("BOG", {
            "usd_buy": u.get('buy-dgtl-rate'), "usd_sell": u.get('sell-dgtl-rate'),
            "eur_buy": e.get('buy-dgtl-rate'), "eur_sell": e.get('sell-dgtl-rate')
        }, True))
        # Branch (Commercial)
        final_cache.append(format_entry("BOG", {
            "usd_buy": u.get('buy-rate'), "usd_sell": u.get('sell-rate'),
            "eur_buy": e.get('buy-rate'), "eur_sell": e.get('sell-rate')
        }, False))
    except: pass

    # --- 2. CREDO (Internet + Branch из твоего JSON) ---
    try:
        r = requests.get("https://credobank.ge/en/", headers=headers, timeout=5)
        # Используем __NEXT_DATA__ для точности
        data = json.loads(BeautifulSoup(r.text, 'html.parser').find('script', id='__NEXT_DATA__').string)
        rates = data['props']['pageProps']['exchangeRates']
        usd = next(i for i in rates if i['currency'] == 'USD')
        eur = next(i for i in rates if i['currency'] == 'EUR')

        # Online (Internet Bank)
        final_cache.append(format_entry("CREDO", {
            "usd_buy": usd['buyRateInternet'], "usd_sell": usd['sellRateInternet'],
            "eur_buy": eur['buyRateInternet'], "eur_sell": eur['sellRateInternet']
        }, True))
        # Branch
        final_cache.append(format_entry("CREDO", {
            "usd_buy": usd['buyRate'], "usd_sell": usd['sellRate'],
            "eur_buy": eur['buyRate'], "eur_sell": eur['sellRate']
        }, False))
    except: pass

    # --- 3. LIBERTY (Online + Branch) ---
    try:
        r = requests.get("https://libertybank.ge/en/", headers=headers, timeout=5)
        soup = BeautifulSoup(r.text, 'html.parser')
        lib = {}
        for c in ['USD', 'EUR']:
            row = soup.find("span", string=c).find_parent(class_="js-homepage__currency-item")
            items = row.find_all(class_="currency-rates__item")
            lib[c] = {
                "comm": {"buy": items[1].find_all("span")[0].text.strip(), "sell": items[1].find_all("span")[1].text.strip()},
                "net": {"buy": items[2].find_all("span")[0].text.strip(), "sell": items[2].find_all("span")[1].text.strip()}
            }
        
        final_cache.append(format_entry("LIBERTY", {
            "usd_buy": lib['USD']['net']['buy'], "usd_sell": lib['USD']['net']['sell'],
            "eur_buy": lib['EUR']['net']['buy'], "eur_sell": lib['EUR']['net']['sell']
        }, True))
        final_cache.append(format_entry("LIBERTY", {
            "usd_buy": lib['USD']['comm']['buy'], "usd_sell": lib['USD']['comm']['sell'],
            "eur_buy": lib['EUR']['comm']['buy'], "eur_sell": lib['EUR']['comm']['sell']
        }, False))
    except: pass

    # --- 4. TBC (Только Branch, онлайна пока нет) ---
    try:
        r = requests.get("https://tbcbank.ge/en/treasury-products", headers=headers, timeout=5)
        soup = BeautifulSoup(r.text, 'html.parser')
        rows = soup.find_all("div", class_="tbcx-pw-popular-currencies__row")
        tbc_data = {}
        for row in rows:
            code = row.find("div", class_="tbcx-pw-currency-badge").text.strip()
            vals = row.find_all("div", class_="tbcx-pw-popular-currencies__body")
            if code in ['USD', 'EUR']:
                tbc_data[code] = {"buy": vals[0].text.strip(), "sell": vals[1].text.strip()}
        
        final_cache.append(format_entry("TBC", {
            "usd_buy": tbc_data['USD']['buy'], "usd_sell": tbc_data['USD']['sell'],
            "eur_buy": tbc_data['EUR']['buy'], "eur_sell": tbc_data['EUR']['sell']
        }, False))
    except: pass

    return final_cache

if __name__ == "__main__":
    # Этот JSON идет в кэш
    print(json.dumps(get_all_rates(), indent=4))

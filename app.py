import requests
from bs4 import BeautifulSoup

def get_rates():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    target_currencies = ['USD', 'EUR']
    results = {}

    # --- 1. LIBERTY BANK ---
    try:
        r_lib = requests.get("https://libertybank.ge/en/", headers=headers, timeout=10)
        soup_lib = BeautifulSoup(r_lib.text, 'html.parser')
        for curr in target_currencies:
            # Поиск строки валюты по тексту (USD/EUR)
            row = soup_lib.find("span", string=curr).find_parent(class_="js-homepage__currency-item")
            items = row.find_all(class_="currency-rates__item")
            # Индекс [1] - Commercial, [2] - Internet Bank (Mobile)
            comm = items[1].find_all("span", class_="currency-rates__currency")
            net = items[2].find_all("span", class_="currency-rates__currency")
            
            results[f'LIBERTY_{curr}'] = {
                "branch": {"buy": comm[0].text.strip(), "sell": comm[1].text.strip()},
                "online": {"buy": net[0].text.strip(), "sell": net[1].text.strip()}
            }
    except Exception:
        pass

    # --- 2. BANK OF GEORGIA (BoG) ---
    try:
        # Используем прямую страницу курсов для стабильности
        r_bog = requests.get("https://bog.ge/en/personal/currencys", headers=headers, timeout=10)
        soup_bog = BeautifulSoup(r_bog.text, 'html.parser')
        for curr in target_currencies:
            card = soup_bog.find('bog-ccy-card', id=curr)
            if card:
                results[f'BOG_{curr}'] = {
                    "branch": {"buy": card.get('buy-rate'), "sell": card.get('sell-rate')},
                    "online": {"buy": card.get('buy-dgtl-rate'), "sell": card.get('sell-dgtl-rate')}
                }
    except Exception:
        pass

    # --- 3. TBC BANK ---
    try:
        r_tbc = requests.get("https://tbcbank.ge/en/treasury-products", headers=headers, timeout=10)
        soup_tbc = BeautifulSoup(r_tbc.text, 'html.parser')
        rows = soup_tbc.find_all("div", class_="tbcx-pw-popular-currencies__row")
        for row in rows:
            badge = row.find("div", class_="tbcx-pw-currency-badge")
            if badge:
                curr_name = badge.text.strip()
                if curr_name in target_currencies:
                    values = row.find_all("div", class_="tbcx-pw-popular-currencies__body")
                    if len(values) >= 2:
                        results[f'TBC_{curr_name}'] = {
                            "branch": {"buy": values[0].text.strip(), "sell": values[1].text.strip()},
                            "online": {"buy": "---", "sell": "---"} # Онлайн-курс на сайте TBC динамический
                        }
    except Exception:
        pass

    return results

def print_table(data):
    for curr in ['USD', 'EUR']:
        print(f"\n--- {curr} RATES ---")
        print(f"{'BANK':<12} | {'TYPE':<10} | {'BUY':<8} | {'SELL':<8}")
        print("-" * 45)
        for bank in ['BOG', 'LIBERTY', 'TBC']:
            key = f'{bank}_{curr}'
            if key in data:
                d = data[key]
                print(f"{bank:<12} | Branch     | {d['branch']['buy']:<8} | {d['branch']['sell']:<8}")
                print(f"{'':<12} | Online     | {d['online']['buy']:<8} | {d['online']['sell']:<8}")
            else:
                print(f"{bank:<12} | Error      | No data  | No data")

if __name__ == "__main__":
    print("Fetching data from banks...")
    currency_data = get_rates()
    print_table(currency_data)

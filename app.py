import requests
from bs4 import BeautifulSoup

def get_all_rates(target_currencies=['USD', 'EUR']):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    results = {}

    # --- 1. Сбор данных с LIBERTY ---
    try:
        r_lib = requests.get("https://libertybank.ge/en/", headers=headers, timeout=10)
        soup_lib = BeautifulSoup(r_lib.text, 'html.parser')
        
        for curr in target_currencies:
            # Ищем строку с названием валюты (USD/EUR)
            row = soup_lib.find("span", string=curr).find_parent(class_="js-homepage__currency-item")
            items = row.find_all(class_="currency-rates__item")
            
            # По твоей структуре: индекс [1] - Commercial, [2] - Internet Bank
            comm = items[1].find_all("span", class_="currency-rates__currency")
            net = items[2].find_all("span", class_="currency-rates__currency")
            
            results[f'liberty_{curr}'] = {
                "branch": {"buy": comm[0].text.strip(), "sell": comm[1].text.strip()},
                "online": {"buy": net[0].text.strip(), "sell": net[1].text.strip()}
            }
    except:
        pass

    # --- 2. Сбор данных с BOG ---
    try:
        r_bog = requests.get("https://bog.ge/en/personal/currencys", headers=headers, timeout=10)
        soup_bog = BeautifulSoup(r_bog.text, 'html.parser')
        
        for curr in target_currencies:
            # Ищем кастомный тег bog-ccy-card с нужным ID
            card = soup_bog.find('bog-ccy-card', id=curr)
            if card:
                results[f'bog_{curr}'] = {
                    "branch": {"buy": card.get('buy-rate'), "sell": card.get('sell-rate')},
                    "online": {"buy": card.get('buy-dgtl-rate'), "sell": card.get('sell-dgtl-rate')}
                }
    except:
        pass

    return results

if __name__ == "__main__":
    rates = get_all_rates(['USD', 'EUR'])
    
    for c in ['USD', 'EUR']:
        print(f"\n📈 КУРС {c}:")
        print(f"{'Банк':<15} | {'Тип':<10} | {'Покупка':<8} | {'Продажа':<8}")
        print("-" * 50)
        for bank in ['liberty', 'bog']:
            data = rates.get(f'{bank}_{c}')
            if data:
                print(f"{bank.upper():<15} | Branch     | {data['branch']['buy']:<8} | {data['branch']['sell']:<8}")
                print(f"{'':<15} | Online     | {data['online']['buy']:<8} | {data['online']['sell']:<8}")

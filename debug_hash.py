import requests
from bs4 import BeautifulSoup
import os

def check_hash():
    url = "https://hashbank.ge/en"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    
    print(f"--- ДИАГНОСТИКА HASH BANK ---")
    try:
        r = requests.get(url, headers=headers, timeout=15)
        print(f"Статус ответа: {r.status_code}")
        
        if "__NEXT_DATA__" in r.text:
            print("РЕЗУЛЬТАТ: УСПЕХ! Тег __NEXT_DATA__ найден в HTML.")
            # Выведем кусочек для уверенности
            start = r.text.find("__NEXT_DATA__")
            print(f"Фрагмент: {r.text[start:start+100]}...")
        else:
            print("РЕЗУЛЬТАТ: ОТКАЗ. Тег не найден. Сайт заблокировал requests или изменил структуру.")
            print(f"Длина полученного текста: {len(r.text)} символов.")
            if "Cloudflare" in r.text or "403" in str(r.status_code):
                print("Причина: Блокировка (Cloudflare/Forbidden)")
                
    except Exception as e:
        print(f"Ошибка при запросе: {e}")

if __name__ == "__main__":
    check_hash()

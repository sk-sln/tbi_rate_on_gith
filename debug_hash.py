import requests
from bs4 import BeautifulSoup

def check():
    url = "https://hashbank.ge/en"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    print("--- ЗАПУСК ТЕСТА HASH BANK ---")
    try:
        r = requests.get(url, headers=headers, timeout=15)
        print(f"Статус: {r.status_code}")
        if "__NEXT_DATA__" in r.text:
            print("РЕЗУЛЬТАТ: УСПЕХ! Данные видны через простой запрос.")
        else:
            print("РЕЗУЛЬТАТ: ОТКАЗ. Нужен браузер Playwright.")
    except Exception as e:
        print(f"ОШИБКА: {e}")

if __name__ == "__main__":
    check()

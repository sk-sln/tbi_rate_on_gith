import json
import os
import time

# --- НАСТРОЙКИ ---
CACHE_FILE = "cache.json"

def make_standard_entry(bank_name, usd_buy, usd_sell, eur_buy, eur_sell, is_online):
    """Формирует чистый словарь для Flutter"""
    return {
        "bank": bank_name,
        "is_online": is_online,
        "usd_buy": str(usd_buy).strip().replace(',', '.'),
        "usd_sell": str(usd_sell).strip().replace(',', '.'),
        "eur_buy": str(eur_buy).strip().replace(',', '.'),
        "eur_sell": str(eur_sell).strip().replace(',', '.')
    }

def save_cache_atomic(data):
    """Атомарная запись: сначала в темп, потом замена"""
    temp_file = CACHE_FILE + ".tmp"
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        
        # Мгновенная замена (на уровне ОС это одна операция)
        os.replace(temp_file, CACHE_FILE)
        print(f"[{time.strftime('%H:%M:%S')}] Кэш успешно обновлен.")
    except Exception as e:
        print(f"Ошибка при записи кэша: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)

def main_sync():
    """Основной цикл парсинга (замени логику парсеров на свою)"""
    print("ГАС запущен. Начинаю сбор данных...")
    
    while True:
        final_results = []
        
        # --- ПРИМЕР: CREDO ---
        try:
            # Тут будет твой реальный парсинг (requests/beautifulsoup)
            # Имитируем получение данных:
            credo_online = make_standard_entry("CREDO", "2.691", "2.705", "3.054", "3.133", True)
            credo_branch = make_standard_entry("CREDO", "2.685", "2.715", "3.040", "3.150", False)
            final_results.extend([credo_online, credo_branch])
        except Exception as e:
            print(f"Ошибка парсинга CREDO: {e}")

        # --- ПРИМЕР: BOG ---
        try:
            bog_online = make_standard_entry("BOG", "2.670", "2.690", "3.010", "3.100", True)
            final_results.append(bog_online)
        except Exception as e:
            print(f"Ошибка парсинга BOG: {e}")

        # Сохраняем всё, что удалось собрать
        if final_results:
            save_cache_atomic(final_results)
        
        # Интервал обновления (например, раз в 15 минут)
        print("Сплю 15 минут...")
        time.sleep(900)

if __name__ == "__main__":
    main_sync()

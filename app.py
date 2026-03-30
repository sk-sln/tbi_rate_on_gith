# Универсальная функция для добавления данных в кэш
def update_cache(name, rates, is_online=False):
    if rates:
        banks_cache[name] = {
            'usd_buy': rates.get('usd_buy', '—'),
            'usd_sell': rates.get('usd_sell', '—'),
            'eur_buy': rates.get('eur_buy', '—'),
            'eur_sell': rates.get('eur_sell', '—'),
            'time': int(time.time() * 1000),
            'is_online': is_online  # Тот самый ТЭГ
        }

def parse_bog():
    try:
        url = "https://bankofgeorgia.ge/en/retail"
        html = get_data(url)
        
        # Регулярка для вытягивания всех 4 параметров из одного тега
        pattern = r'id="USD".*?buy-rate="([0-9.]+)".*?sell-rate="([0-9.]+)".*?buy-dgtl-rate="([0-9.]+)".*?sell-dgtl-rate="([0-9.]+)"'
        match = re.search(pattern, html)
        
        if match:
            # Наличный курс
            update_cache("Bank of Georgia", {
                'usd_buy': match.group(1), 'usd_sell': match.group(2)
            }, is_online=False)
            
            # Онлайн курс
            update_cache("BoG Online", {
                'usd_buy': match.group(3), 'usd_sell': match.group(4)
            }, is_online=True)
            
            print("✅ BoG Split: Branch & Online updated")
    except Exception as e:
        print(f"BOG error: {e}")

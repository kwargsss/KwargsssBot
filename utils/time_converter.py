import re


def parse_time(time_str: str) -> int:
    if not time_str:
        return 0

    time_str = time_str.lower().replace(" ", "")
    
    multipliers = {
        'с': 1, 'сек': 1, 'секунд': 1, 'секунды': 1, 'секунда': 1,
        'м': 60, 'мин': 60, 'минута': 60, 'минуты': 60, 'минут': 60,
        'ч': 3600, 'час': 3600, 'часа': 3600, 'часов': 3600,
        'д': 86400, 'день': 86400, 'дня': 86400, 'дней': 86400
    }

    matches = re.findall(r"(\d+)([a-zа-яё]+)", time_str)
    
    total_seconds = 0
    for amount, unit in matches:
        found_mult = 0
        for key, mult in multipliers.items():
            if unit.startswith(key):
                found_mult = mult
                break
        
        if found_mult:
            total_seconds += int(amount) * found_mult
            
    return total_seconds
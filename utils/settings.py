cooldown_second = {
	"like": 3600,
    "work": 7200,
    "love": 43200,
}

def format_cooldown(seconds: float) -> str:
    seconds = int(seconds)
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    units = {"h": "ч", "m": "м", "s": "с"}

    parts = []
    if hours:
        parts.append(f"{hours}{units['h']}")
    if minutes:
        parts.append(f"{minutes}{units['m']}")
    if sec or not parts:
        parts.append(f"{sec}{units['s']}")

    return " ".join(parts)
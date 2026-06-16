"""Ukrainian language helpers for email and other user-facing text."""


def to_vocative(name: str) -> str:
    """Convert a Ukrainian first name to vocative case (кличний відмінок).

    The vocative is used for direct address: "Привіт, Анастасіє!" rather
    than the dictionary form "Анастасія". Covers the most common patterns
    in Ukrainian first names. Falls back to the original form for names
    that don't match any rule.

    Examples:
        Анастасія -> Анастасіє
        Олена -> Олено
        Ірина -> Ірино
        Стас -> Стасе
        Віктор -> Вікторе
        Андрій -> Андрію
        Ілля -> Ілле

    Args:
        name: a first name OR a full name. If full name is passed, only
              the first word is converted (e.g. "Анастасія Сидоренко" ->
              "Анастасіє Сидоренко" would be wrong; we return only "Анастасіє").

    Returns:
        The name in vocative case, or the original if no rule matched.
    """
    if not name:
        return name

    # Take only the first word — full_name may include surname
    parts = name.strip().split()
    first = parts[0]

    # Rules ordered from most specific to most general (-ія before -я before -а)
    if first.endswith("ія"):
        return first[:-1] + "є"          # Анастасія -> Анастасіє, Юлія -> Юліє
    if first.endswith("я"):
        return first[:-1] + "е"          # Ілля -> Ілле, Льоня -> Льоне
    if first.endswith("а"):
        return first[:-1] + "о"          # Олена -> Олено, Ірина -> Ірино
    if first.endswith("й"):
        return first[:-1] + "ю"          # Андрій -> Андрію, Олексій -> Олексію
    if first.endswith(("р", "с", "к", "н", "т", "д", "в", "л", "м", "п", "б", "г", "ф")):
        return first + "е"               # Віктор -> Вікторе, Стас -> Стасе, Олег -> Олеже (примітивно, але хоч щось)

    # Не розпізнали — повертаємо як є (краще ніж зіпсувати)
    return first

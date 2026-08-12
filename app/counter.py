def count_text(text: str) -> dict:
    """Подсчёт слов и символов в тексте."""
    return {
        "words": len(text.split()),
        "chars": len(text),
        "chars_no_spaces": len(text.replace(" ", "").replace("\t", "").replace("\n", "").replace("\r", "")),
    }

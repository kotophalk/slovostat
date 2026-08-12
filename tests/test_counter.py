from app.counter import count_text


def test_empty_string():
    assert count_text("") == {"words": 0, "chars": 0, "chars_no_spaces": 0}


def test_russian_text():
    result = count_text("Привет мир")
    assert result == {"words": 2, "chars": 10, "chars_no_spaces": 9}


def test_mixed_text():
    result = count_text("Hello мир")
    assert result == {"words": 2, "chars": 9, "chars_no_spaces": 8}


def test_multiple_spaces_and_newlines():
    result = count_text("  слово   два\n\nтри  ")
    assert result["words"] == 3
    assert result["chars"] == 20
    assert result["chars_no_spaces"] == 11

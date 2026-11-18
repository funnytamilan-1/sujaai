from app.main import normalize_phone

def test_normalize_phone():
    assert normalize_phone("+91 98765-43210") == "919876543210"
    assert normalize_phone("123") is None
    assert normalize_phone(9876543210.0) == "9876543210"
    assert normalize_phone(None) is None

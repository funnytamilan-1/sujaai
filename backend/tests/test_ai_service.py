from app import ai_service

def test_clean_text_removes_nulls_and_excess_whitespace():
    assert ai_service.clean_text("Policy\x00  details\n\n\nclaim") == "Policy details\n\nclaim"

def test_chunk_text_returns_bounded_chunks():
    text = " ".join(["insurance"] * 420)
    chunks = ai_service.chunk_text(text)
    assert len(chunks) >= 2
    assert all(0 < len(chunk) <= 1800 for chunk in chunks)

def test_retrieval_uses_lexical_fallback_when_encoder_unavailable(monkeypatch):
    def unavailable():
        raise ImportError("optional sentence-transformers is not installed")
    monkeypatch.setattr(ai_service, "_encoder", unavailable)
    rows = [
        {"id": 1, "text": "Health insurance waiting period information", "embedding_json": None},
        {"id": 2, "text": "Motor vehicle policy renewal guidance", "embedding_json": None},
    ]
    result = ai_service.retrieve("health insurance", rows)
    assert result
    assert result[0]["id"] == 1

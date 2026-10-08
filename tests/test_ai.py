from backend.app.ai import upstream_error


def test_ocr_limit_errors_distinguish_budget_rate_and_openai():
    assert "Kuota total relay" in upstream_error(429, "relay_budget")
    assert "satu menit" in upstream_error(429, "relay_rate")
    assert "OpenAI" in upstream_error(429, "upstream_rate")
    assert "Silakan coba" in upstream_error(429, "untrusted-code")

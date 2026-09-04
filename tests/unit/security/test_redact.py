from keel.security.redact import redact, scan


def test_openai_style_key_is_detected_and_redacted() -> None:
    text = "here is my key sk-abcdefghijklmnopqrstuvwxyz0123456789"

    redacted, matches = redact(text)

    assert "sk-abcdefghijklmnopqrstuvwxyz0123456789" not in redacted
    assert any(m.label == "openai_api_key" for m in matches)
    assert "[REDACTED:openai_api_key]" in redacted


def test_aws_access_key_is_detected() -> None:
    matches = scan("AKIAIOSFODNN7EXAMPLE")

    assert any(m.label == "aws_access_key_id" for m in matches)


def test_private_key_block_is_detected() -> None:
    matches = scan(
        "-----BEGIN RSA PRIVATE KEY-----\nMIIBOgIBAAJBAK...\n-----END RSA PRIVATE KEY-----"
    )

    assert any(m.label == "private_key_block" for m in matches)


def test_email_is_detected_as_sensitive_data_not_secret() -> None:
    matches = scan("contact jane.doe@example.com for access")

    assert any(m.label == "email" and m.category == "sensitive_data" for m in matches)


def test_valid_credit_card_number_passes_luhn_and_is_flagged() -> None:
    matches = scan("card on file: 4111 1111 1111 1111")

    assert any(m.label == "credit_card_candidate" for m in matches)


def test_a_16_digit_number_failing_luhn_is_not_flagged_as_a_card() -> None:
    matches = scan("order id: 1234 5678 9012 3456")

    assert not any(m.label == "credit_card_candidate" for m in matches)


def test_plain_text_with_nothing_sensitive_is_untouched() -> None:
    text = "the quick brown fox jumps over the lazy dog"

    redacted, matches = redact(text)

    assert redacted == text
    assert matches == []


def test_multiple_matches_all_redacted_without_corrupting_offsets() -> None:
    text = "key one: sk-aaaaaaaaaaaaaaaaaaaaaaaa and key two: sk-bbbbbbbbbbbbbbbbbbbbbbbb"

    redacted, matches = redact(text)

    assert len(matches) == 2
    assert redacted.count("[REDACTED:openai_api_key]") == 2
    assert "sk-aaaaaaaaaaaaaaaaaaaaaaaa" not in redacted
    assert "sk-bbbbbbbbbbbbbbbbbbbbbbbb" not in redacted

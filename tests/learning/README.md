# Learning tests

Tests here pin *observed* behavior of external dependencies (vendor SDKs, pydantic
edge cases) that Keel relies on. They exist so a contract mismatch surfaces as a
failing test with a name, not as a mid-implementation rollback.

They are marked `@pytest.mark.learning` and excluded from CI by default because
they may need network or credentials. Run them locally with:

    pytest -m learning tests/learning

Each test should say, in its docstring, which Keel component depends on the
behavior it pins.

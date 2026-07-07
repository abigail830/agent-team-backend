from app.guardrails.sql_rules import validate_sql


def test_allows_select():
    result = validate_sql("SELECT 1", max_rows=100)
    assert result.ok
    assert "LIMIT 100" in result.normalized_sql


def test_denies_insert():
    result = validate_sql("INSERT INTO t VALUES (1)", max_rows=100)
    assert not result.ok


def test_denies_multiple_statements():
    result = validate_sql("SELECT 1; SELECT 2", max_rows=100)
    assert not result.ok


def test_caps_existing_limit():
    result = validate_sql("SELECT * FROM t LIMIT 5000", max_rows=2000)
    assert result.ok
    assert "LIMIT 2000" in result.normalized_sql

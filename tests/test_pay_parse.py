from handlers.pay import parse_codes


def test_parse_single():
    assert parse_codes("SALE-ABC123") == ["SALE-ABC123"]


def test_parse_multi_mixed_case_spaces():
    assert parse_codes("sale-a, SALE-B ;sale-c") == ["SALE-A", "SALE-B", "SALE-C"]

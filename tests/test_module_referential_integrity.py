from modular_data_ci.modules.referential_integrity import ReferentialIntegrityModule
from modular_data_ci.results import CheckStatus
from tests.module_fixtures import make_context, run_module


def context():
    return make_context(
        "CREATE TABLE customers (id INTEGER)",
        "INSERT INTO customers VALUES (1), (2)",
        "CREATE TABLE orders (id INTEGER, customer_id INTEGER)",
        "INSERT INTO orders VALUES (10, 1), (11, 2), (12, 3), (13, 3), (14, NULL)",
    )


PARAMS = {
    "table": "orders",
    "column": "customer_id",
    "references": {"table": "customers", "column": "id"},
}


def test_orphans_found():
    outcome = run_module(ReferentialIntegrityModule, context(), **PARAMS)
    assert outcome.status is CheckStatus.FAILURE
    assert outcome.message == ("2 row(s) in orders with customer_id missing from customers.id")
    assert outcome.details["sample"] == [3]


def test_where_filters_child_rows():
    outcome = run_module(ReferentialIntegrityModule, context(), where="id < 12", **PARAMS)
    assert outcome.status is CheckStatus.SUCCESS

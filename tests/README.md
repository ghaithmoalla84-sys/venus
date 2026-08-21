# Venus Coffee Test Suite

## Overview

The Venus Coffee test suite contains **207 tests** across unit and integration categories. Tests use `pytest` with `pytest-qt` for Qt UI testing and `pytest-cov` for coverage measurement.

## Structure

```
tests/
├── conftest.py              # Shared fixtures (temp_db, qt_app, db_conn)
├── pytest.ini               # Pytest configuration with markers
├── fixtures/
│   ├── constants.py         # Test constants (dates, names)
│   └── helpers.py           # Helper functions (insert_group, etc.)
├── unit/
│   ├── test_database.py
│   ├── test_dashboard.py
│   ├── test_creditors.py
│   ├── test_comprehensive.py
│   ├── test_cash.py
│   ├── test_sales.py
│   ├── test_reports.py
│   ├── test_purchase_invoices.py
│   ├── test_performance.py
│   ├── test_transfers.py
│   ├── test_settings.py
│   ├── test_widgets.py
│   ├── test_multi_currency.py
│   ├── test_inventory.py
│   ├── test_data_recovery.py
│   └── test_logging.py
└── integration/
    ├── test_full_day_workflow.py
    ├── test_debt_lifecycle.py
    ├── test_purchase_to_sale.py
    └── test_reopen_complex.py
```

## How to Run Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=venus --cov-report=html --cov-report=term

# Run specific test file
pytest tests/unit/test_comprehensive.py -v

# Run specific test
pytest tests/unit/test_comprehensive.py::TestCashOperations::test_open_day -v

# Run with markers
pytest tests/ -m "not integration" -v
```

## How to Add New Tests

1. **Choose the right directory**: `unit/` for isolated logic, `integration/` for multi-step workflows.
2. **Follow naming convention**: `test_*.py` files, `Test*` classes, `test_*` methods.
3. **Use existing fixtures**: `temp_db` for database, `qt_app` for Qt widgets, `db_conn` for direct SQL.
4. **Mark appropriately**: Use `@pytest.mark.integration`, `@pytest.mark.slow`, etc.
5. **Isolate tests**: Each test gets a fresh `temp_db` via the `clean_db` fixture.

## Fixture Documentation

### `temp_db` (function-scoped)
Creates a temporary SQLite database with the full schema. Automatically cleaned between tests.

### `qt_app` (session-scoped)
Provides a single `QApplication` instance for all Qt tests.

### `db_conn` (function-scoped)
Yields a `sqlite3.Row`-enabled connection to the temp database.

### `patch_database_path` (autouse)
Automatically patches `venus.core.database.DATABASE_PATH` to use the temp database.

### `clean_db` (autouse)
Deletes all data from tables before each test and re-inserts default settings.

## Common Mocking Patterns

### Mocking QMessageBox
```python
from unittest.mock import patch
from PyQt5.QtWidgets import QMessageBox

with patch.object(QMessageBox, 'warning') as mock_warn, \
     patch.object(QMessageBox, 'information'):
    widget.some_action()
assert mock_warn.called
```

### Mocking widget attributes
```python
screen.supplier_combo = type('obj', (object,), {'current_value': value, 'refresh': lambda: None})()
```

### Patching database path
```python
from venus.core.database import patch_db_path
patch_db_path("/path/to/test.db")
```

## Markers

| Marker | Description |
|--------|-------------|
| `slow` | Tests taking > 1 second |
| `integration` | Requires full database and multiple components |
| `ui` | Requires Qt application |
| `smoke` | Quick sanity checks |
| `db` | Database-focused tests |
| `accounting` | Critical accounting logic tests |

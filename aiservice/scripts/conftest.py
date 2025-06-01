import pytest

def pytest_addoption(parser):
    parser.addoption(
        "--e2e-json-file",
        action="store",
        default=None,
        help="Specify the JSON file name from aiservice/scripts/ to use for E2E title generation tests (e.g., my_test_data.json)"
    ) 
import importlib


def test_main_module_imports():
    module = importlib.import_module("fabric_admin_console.__main__")
    assert hasattr(module, "main")

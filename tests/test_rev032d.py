import importlib.util
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('homologar_moeda_rev032d',ROOT/'src/homologar_moeda_rev032d.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def test_numeric_validation():
    assert m.number(1.0) and not m.number(True) and not m.number(float('nan')) and not m.number(0)

def test_categories_unique():
    assert len(m.CATS)==14 and len(set(m.CATS))==14

def test_readonly_outputs(tmp_path):
    assert m.sha(ROOT/'parametros/economia_rev032d.json')

def test_missing_config_rejected(tmp_path):
    with pytest.raises(FileNotFoundError):m.run({'rev032c_config':'missing.json'},tmp_path)

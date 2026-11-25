import importlib.util,json,tempfile,shutil
from pathlib import Path
import pytest
SRC=Path(__file__).resolve().parents[1]/'src'/'reconciliar_moeda_rev032c.py'
spec=importlib.util.spec_from_file_location('rev032c_controlled',SRC);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def test_conversion_ratio():
    assert m.convert_price(100,2025,2026,100,110)==pytest.approx(110)

def test_conversion_rejects_bad_indices():
    with pytest.raises(ValueError):m.convert_price(100,2025,2026,0,110)

def test_config_stays_pending():
    c=json.loads((SRC.parents[1]/'parametros/economia_rev032c.json').read_text(encoding='utf-8'))
    assert c['monetary']['indexation_2025_2026']['status']=='PENDING'
    assert c['monetary']['indexation_2025_2026']['index_may_2025'] is None

def test_frozen_cost_categories():
    assert len(m.CATS)==14 and 'residual_credit' in m.CATS

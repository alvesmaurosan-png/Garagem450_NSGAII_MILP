import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('rev032e_module',ROOT/'src/consolidar_matriz_rev032e.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def test_categories():assert len(m.CATS)==14 and len(set(m.CATS))==14
def test_all_gaps_mapped():assert set(m.DETAILS)==set(m.CATS)
def test_no_implicit_zero():assert all(x[2] and x[3] for x in m.DETAILS.values())
def test_economic_gates_declared():
 import json
 c=json.loads((ROOT/'parametros/economia_rev032e.json').read_text(encoding='utf-8'))
 assert c['allow_cost_flow_release'] is False and c['allow_f1_lcoe'] is False

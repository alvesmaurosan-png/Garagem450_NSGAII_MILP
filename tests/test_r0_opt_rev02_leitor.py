import importlib.util
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('r0_opt_rev02_leitor',ROOT/'r0_opt_rev02_leitor.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def sample(tmp_path):
    data={'status':m.EXPECTED,'annual_integer_feasibility_certified':True,'n_bev':100,
          'selected_vehicle_ids':list(range(100)),
          'days':[{'day':i,'status':'MILP_INTEGER_FEASIBLE','milp_status':0,'pcc_peak_kw':2500.,'soc_start_kwh':1.,'soc_end_kwh':1.} for i in range(365)]}
    p=tmp_path/'result.json';p.write_text(json.dumps(data));return p,data

def test_valid(tmp_path):
    p,_=sample(tmp_path);r=m.inspect_certificate(p)
    assert r['status']=='READ_ONLY_CERTIFICATE_CONSISTENT'
    assert r['F2_peak_from_daily_records_kw']==2500
    assert r['F1_brl_per_pkm'] is None
    assert r['annual_grid_bill_brl'] is None

def test_missing_day(tmp_path):
    p,d=sample(tmp_path);d['days'].pop();p.write_text(json.dumps(d))
    assert m.inspect_certificate(p)['status']=='CERTIFICATE_DATA_INCONSISTENT'

def test_uncertified(tmp_path):
    p,d=sample(tmp_path);d['annual_integer_feasibility_certified']=False;p.write_text(json.dumps(d))
    assert m.inspect_certificate(p)['F2_peak_from_daily_records_kw'] is None

def test_pcc_violation(tmp_path):
    p,d=sample(tmp_path);d['days'][4]['pcc_peak_kw']=2600;p.write_text(json.dumps(d))
    assert m.inspect_certificate(p)['status']=='CERTIFICATE_DATA_INCONSISTENT'

def test_soc_violation(tmp_path):
    p,d=sample(tmp_path);d['days'][4]['soc_end_kwh']=2;p.write_text(json.dumps(d))
    assert m.inspect_certificate(p)['status']=='CERTIFICATE_DATA_INCONSISTENT'

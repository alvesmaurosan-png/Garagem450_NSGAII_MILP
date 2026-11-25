"""Testes REV02.3; executar python -m pytest -q."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from otimizar_recarga_rev023 import build_data, solve_model


def fixture():
    vehicles=pd.DataFrame([{'vehicle_id':'A','distance_km':100.0,'pkm':2300.0,'traction_energy_kwh':123.0,'return_min':600.0},
                           {'vehicle_id':'B','distance_km':80.0,'pkm':1840.0,'traction_energy_kwh':98.4,'return_min':620.0}])
    blocks=pd.DataFrame([{'vehicle_id':vid,'block_id':vid+'1','start_min':100.0,'end_min':350.0,'distance_km':km/2}
                         for vid,km in [('A',100.0),('B',80.0)]]+
                        [{'vehicle_id':vid,'block_id':vid+'2','start_min':360.0,'end_min':end,'distance_km':km/2}
                         for vid,km,end in [('A',100.0,600.0),('B',80.0,620.0)]])
    return vehicles,blocks


def test_preserva_servico_e_energia():
    v,b=fixture()
    vids,tr,allowed,km,pkm=build_data(v,b)
    assert vids==['A','B']
    assert np.allclose(tr.sum(axis=1),[123.0,98.4])
    assert np.allclose(km,[100,80])
    assert np.allclose(pkm,[2300,1840])
    assert not allowed[:,7].any()  # 01:45 dentro do serviço


def test_milp_soc_portas_e_pico():
    v,b=fixture()
    _,tr,allowed,_,_=build_data(v,b)
    result,solution=solve_model(tr,allowed,time_limit=30,mip_gap=0.001,peak_slack_kw=1.0)
    assert solution is not None, result
    x,z,soc=solution
    assert np.all(x[~allowed]<1e-8)
    assert np.allclose(x.sum(axis=1),tr.sum(axis=1),atol=1e-5)
    assert np.allclose(soc[:,0],soc[:,-1],atol=1e-6)
    assert soc.min()>=.15-1e-6 and soc.max()<=.90+1e-6
    assert np.max((z>.5).sum(axis=0))<=result['ports_incumbent']
    assert result['peak_dc_kw_incumbent']<=result['peak_cap_dc_kw']+1e-5

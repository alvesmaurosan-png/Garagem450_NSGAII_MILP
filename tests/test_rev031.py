import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from rev031_conexao_acdc import energy_screen, solve_relaxed_dispatch, frozen_schedule
from otimizar_recarga_rev023a import prepare

def test_energy_screen_infeasible():
    a=energy_screen(83386.664545,2500,.95)
    assert not a['grid_only_energy_feasible_necessary_condition']
    assert a['minimum_ac_energy_deficit_kwh']==pytest.approx(83386.664545/.95-60000)

def test_lp_relaxation_small():
    traction=np.array([[5.,0.,0.,0.],[5.,0.,0.,0.]])
    allowed=np.array([[False,True,True,True],[False,True,True,True]])
    d=prepare(traction,allowed,360)
    r,agg=solve_relaxed_dispatch(d,.95,10,2)
    assert r['status_code']==0
    assert r['audit']['valid']
    assert r['max_pcc_excess_kw']==pytest.approx(0,abs=1e-5)

def test_frozen_validations(tmp_path):
    p=tmp_path/'s.csv'
    pd.DataFrame({'vehicle_id':['A','B'],'slot':[0,0], 'charge_dc_kwh':[2.,3.], 'port_active':[1,1]}).to_csv(p,index=False)
    a=frozen_schedule(p,2,5)
    assert a.loc[0,'charging_vehicles']==2
    with pytest.raises(ValueError):frozen_schedule(p,2,6)

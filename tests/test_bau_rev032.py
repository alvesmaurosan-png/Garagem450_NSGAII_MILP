import sys, json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from bau_rev032 import physical, economic, load_frozen


def config():
    return {'physical':{'acdc_efficiency':.95,'step_min':15,'auxiliary_kw':0,
      'engineering_margin_fraction':.1,'power_factor':.95,
      'transformer_max_utilization':.8,'transformer_standard_kva':[5000,6000,7500],
      'existing_connection_kw':2500,'contracted_demand_kw':None},
      'annualization':{'equivalent_days_per_year':365,'daily_pkm':1559262.83308,'daily_km':67794.036228},
      'economics':{'years':2,'first_year':2038,'real_discount_rate':.08,
      'initial_costs_brl_2026':{},'annual_costs_brl_2026':{}}}


def test_balanco_e_dimensionamento():
    c=config();d=pd.DataFrame({'slot':list(range(96)),'dc_kwh':[100.]*96,
      'dc_kw':[400.]*96,'ports_active':[3]*96})
    x,s=physical(d,c)
    assert s['daily_dc_kwh']==9600
    assert s['daily_ac_kwh']==pytest.approx(9600/.95)
    assert s['peak_pcc_import_kw']==pytest.approx(400/.95)
    assert s['reinforcement_delta_kw']==0
    assert s['transformer_selected_kva']==5000


def test_bloqueio_economico():
    c=config();cats=('fleet_purchase','fleet_maintenance','fleet_replacement','charger_purchase',
      'charger_maintenance','charger_replacement','electrical_installation','grid_connection',
      'grid_reinforcement','grid_energy','grid_demand','grid_charges','system_opex','residual_credit')
    c['economics']['initial_costs_brl_2026']={k:None for k in cats}
    c['economics']['annual_costs_brl_2026']={k:[None,None] for k in cats}
    p={'annual_pkm':1000,'annual_dc_kwh':500,'peak_pcc_import_kw':100}
    out,ledger=economic(c,p)
    assert out['status']=='BLOCKED_MISSING_COSTS'
    assert ledger is None and out['F2_kw']==100
    c['economics']['initial_costs_brl_2026']={k:0 for k in cats}
    c['economics']['annual_costs_brl_2026']={k:[0,0] for k in cats}
    c['economics']['initial_costs_brl_2026']['fleet_purchase']=1000
    c['economics']['annual_costs_brl_2026']['grid_energy']=[100,100]
    out,ledger=economic(c,p)
    assert out['status']=='COMPUTED_EXPLORATORY'
    assert out['F1_brl_per_pkm']>out['LCOE_brl_per_dc_kwh']*0
    assert len(ledger)==14*3


def test_rejeita_agenda_duplicada(tmp_path):
    p=tmp_path/'f.csv'
    pd.DataFrame([{'vehicle_id':'A','slot':0,'charge_dc_kwh':1,'port_active':1}]*2).to_csv(p,index=False)
    with pytest.raises(ValueError,match='Duplicatas'):load_frozen(p)

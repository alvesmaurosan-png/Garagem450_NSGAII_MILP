import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('audit_rev022',ROOT/'src'/'auditar_recarga_rev022.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_overlap_midnight_and_conservation():
    events=pd.DataFrame([
        {'vehicle_id':'A','event_type':'CHARGE','start_min':-30,'end_min':30,'energy_charge_dc_kwh':60},
        {'vehicle_id':'B','event_type':'CHARGE','start_min':0,'end_min':60,'energy_charge_dc_kwh':60},
        {'vehicle_id':'C','event_type':'SERVICE','start_min':10,'end_min':20,'energy_charge_dc_kwh':0},
    ])
    seg,hourly,m=module.audit(events)
    assert m['max_simultaneous_charging_vehicles']==2
    assert np.isclose(m['peak_aggregate_dc_kw'],120)
    assert np.isclose(m['energy_dc_within_day_kwh'],90)
    assert np.isclose(hourly.loc[0,'energy_dc_kwh'],90)
    assert np.isclose(hourly.energy_dc_kwh.iloc[1:].sum(),0)


def test_same_vehicle_overlap_rejected():
    events=pd.DataFrame([
        {'vehicle_id':'A','event_type':'CHARGE','start_min':0,'end_min':60,'energy_charge_dc_kwh':60},
        {'vehicle_id':'A','event_type':'CHARGE','start_min':30,'end_min':90,'energy_charge_dc_kwh':60},
    ])
    try:
        module.audit(events)
    except ValueError as e:
        assert 'sobrepostos' in str(e)
    else:
        raise AssertionError('Sobreposicao nao detectada')

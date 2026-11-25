"""Testes REV02.1; executar: python -m pytest -q tests/test_service_day_rev021.py"""
import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'src' / 'build_service_day_rev021.py'
spec = importlib.util.spec_from_file_location('rev021', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_rev021_invariantes(tmp_path):
    inp = tmp_path / 'rev02'
    out = tmp_path / 'rev021'
    inp.mkdir()
    vs, bs = [], []
    for i in range(450):
        vid = f'SYN_{i+1:03d}'
        # Inclui um serviço que começa no dia anterior.
        end = 60.0 if i == 0 else 900.0
        start = end - 410.0
        vs.append(dict(vehicle_id=vid, traction_energy_kwh=196.8,
                       distance_km=160.0, pkm=3680.0, return_min=end))
        bs.append(dict(vehicle_id=vid, block_id=f'{vid}_B1',
                       start_min=start, end_min=start+200, distance_km=80.0))
        bs.append(dict(vehicle_id=vid, block_id=f'{vid}_B2',
                       start_min=start+210, end_min=end, distance_km=80.0))
    pd.DataFrame(vs).to_csv(inp / 'veiculos_servico_24h_REV02.csv', index=False)
    pd.DataFrame(bs).to_csv(inp / 'blocos_servico_24h_REV02.csv', index=False)
    report = mod.generate(inp, out)
    ev = pd.read_csv(out / 'eventos_cronologicos_REV021.csv')
    windows = pd.read_csv(out / 'janelas_recarga_REV021.csv')
    audits = pd.read_csv(out / 'auditoria_veiculos_REV021.csv')
    assert report['vehicles'] == 450
    assert len(audits) == 450
    assert (ev.end_min > ev.start_min).all()
    assert (ev.energy_traction_kwh >= 0).all()
    assert (ev.energy_charge_dc_kwh >= 0).all()
    assert np.allclose(audits.energy_residual_kwh, 0, atol=1e-5)
    assert (windows.available_end_min >= windows.available_start_min).all()
    assert (windows.energy_scheduled_kwh <= windows.energy_capacity_kwh + 1e-6).all()
    assert ((ev.event_type == 'CHARGE') & (ev.energy_traction_kwh > 0)).sum() == 0
    assert ((ev.event_type == 'SERVICE') & (ev.energy_charge_dc_kwh > 0)).sum() == 0
    assert (ev.loc[ev.day_index == 0, 'start_min'] >= 0).all()
    assert (ev.loc[ev.day_index == 0, 'end_min'] <= 1440).all()
    assert ev.loc[(ev.vehicle_id == 'SYN_001') & (ev.day_index == -1) & (ev.event_type == 'SERVICE')].shape[0] > 0
    for vid, group in ev.groupby('vehicle_id'):
        group = group.sort_values(['start_min', 'end_min'])
        assert (group.start_min.iloc[1:].to_numpy() >= group.end_min.iloc[:-1].to_numpy() - 1e-6).all()
        assert np.allclose(group.soc_start.iloc[1:].to_numpy(), group.soc_end.iloc[:-1].to_numpy(), atol=1e-6)
    assert report['gate_D2'].startswith('NOT_APPROVED')

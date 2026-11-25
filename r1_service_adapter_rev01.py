#!/usr/bin/env python3
"""Adaptador de dados de serviço para R1; não resolve MILP e não altera REV02."""
from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd

DT = 15.0
DAY = 1440.0
BATTERY = 350.0
SOC_MIN = 0.15
SOC_MAX = 0.90
POWER = 138.0
TURN = 10.0


def run(root: Path, output: Path):
    base = root / 'resultados' / 'servico_REV02'
    v = pd.read_csv(base / 'veiculos_servico_24h_REV02.csv')
    b = pd.read_csv(base / 'blocos_servico_24h_REV02.csv')
    required_v = {'vehicle_id','traction_energy_kwh','distance_km','pkm','return_min'}
    required_b = {'vehicle_id','block_id','start_min','end_min','distance_km'}
    if not required_v.issubset(v.columns) or not required_b.issubset(b.columns):
        raise ValueError('Colunas obrigatorias ausentes')
    if len(v) != 450 or v.vehicle_id.nunique() != 450 or len(b) != 900:
        raise ValueError('Esperados 450 veiculos unicos e 900 blocos')
    if b.block_id.duplicated().any() or set(v.vehicle_id) != set(b.vehicle_id):
        raise ValueError('IDs inconsistentes')
    if v[['traction_energy_kwh','distance_km','pkm','return_min']].isna().any().any() or b[['start_min','end_min','distance_km']].isna().any().any():
        raise ValueError('NaN nas entradas obrigatorias')
    if (v.traction_energy_kwh < 0).any() or (v.distance_km <= 0).any() or (b.distance_km <= 0).any() or (b.end_min <= b.start_min).any():
        raise ValueError('Dados negativos ou intervalos invalidos')
    # Representacao periodica em um dia civil: cada bloco repetido por deslocamentos inteiros.
    rows = []
    issues = []
    for veh in v.itertuples(index=False):
        vid = str(veh.vehicle_id)
        blocks = b[b.vehicle_id == vid].sort_values('start_min')
        if len(blocks) != 2:
            raise ValueError(f'{vid}: esperado exatamente dois blocos')
        if abs(blocks.distance_km.sum() - veh.distance_km) > 0.002:
            raise ValueError(f'{vid}: distancia inconsistente')
        if abs(float(blocks.end_min.iloc[-1]) - float(veh.return_min)) > 0.002:
            raise ValueError(f'{vid}: retorno inconsistente')
        if float(blocks.end_min.iloc[0]) > float(blocks.start_min.iloc[1]) + 1e-7:
            raise ValueError(f'{vid}: blocos sobrepostos')
        start0 = float(blocks.start_min.iloc[0]); endlast = float(blocks.end_min.iloc[-1])
        window_start = endlast + TURN
        window_end = start0 + DAY - TURN
        if window_end < window_start:
            issues.append({'vehicle_id':vid,'issue':'NO_CHARGE_WINDOW'})
        if (window_end - window_start) * POWER / 60.0 < float(veh.traction_energy_kwh) - 1e-7:
            issues.append({'vehicle_id':vid,'issue':'INSUFFICIENT_INDIVIDUAL_CHARGE_WINDOW'})
        if float(veh.traction_energy_kwh) > (SOC_MAX - SOC_MIN) * BATTERY + 1e-7:
            issues.append({'vehicle_id':vid,'issue':'TRACTION_EXCEEDS_USABLE_BATTERY'})
        for t in range(96):
            left = t * DT; right = left + DT
            traction = 0.0
            # Proporcional a intersecao temporal, inclusive servicos atravessando 00:00.
            for block in blocks.itertuples(index=False):
                st, en = float(block.start_min), float(block.end_min)
                block_e = float(veh.traction_energy_kwh) * float(block.distance_km) / float(veh.distance_km)
                for shift in (-2*DAY, -DAY, 0.0, DAY, 2*DAY):
                    overlap = max(0.0, min(right, en + shift) - max(left, st + shift))
                    traction += block_e * overlap / (en - st)
            # Disponibilidade conservadora: slot inteiramente dentro da janela da garagem.
            available = False
            for shift in (-2*DAY, -DAY, 0.0, DAY, 2*DAY):
                if left >= window_start + shift - 1e-8 and right <= window_end + shift + 1e-8:
                    available = True
                    break
            rows.append((vid,t,traction,int(available),POWER if available else 0.0))
    df = pd.DataFrame(rows, columns=['vehicle_id','slot','traction_kwh','charge_allowed','max_charge_dc_kw'])
    check = df.groupby('vehicle_id').traction_kwh.sum()
    target = v.set_index('vehicle_id').traction_energy_kwh
    residual = (check - target).abs()
    if residual.max() > 1e-5:
        raise AssertionError(f'Energia nao conservada: {residual.max()} kWh')
    output.mkdir(parents=True, exist_ok=True)
    df.to_csv(output / 'r1_vehicle_slots_15min_rev01.csv',index=False,float_format='%.9f')
    v[['vehicle_id','traction_energy_kwh','distance_km','pkm']].to_csv(output / 'r1_vehicle_daily_requirements_rev01.csv',index=False)
    pd.DataFrame(issues,columns=['vehicle_id','issue']).to_csv(output/'r1_precheck_issues_rev01.csv',index=False)
    report = {'status':'ADAPTER_CREATED_NOT_MILP_FEASIBILITY', 'vehicles':len(v), 'service_blocks':len(b), 'slots':96, 'vehicle_slot_rows':len(df), 'traction_kwh_day':float(v.traction_energy_kwh.sum()), 'max_abs_traction_reconciliation_kwh':float(residual.max()), 'precheck_issues':len(issues), 'charge_policy':'MILP_DECISION_NOT_FIXED', 'notes':['Slots parcialmente disponiveis foram conservadoramente bloqueados','Nenhum teste de portas, PCC, PV, BESS ou CHP-BIO foi executado','SOC individual e ciclicidade devem ser impostos no MILP']}
    (output/'r1_adapter_report_rev01.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',type=Path,default=Path.cwd())
    ap.add_argument('--output',type=Path,default=Path('resultados/R1_IMPLEMENTACAO_CONTROLADA_REV01/adapter_service'))
    a=ap.parse_args()
    run(a.root.resolve(),a.output.resolve())

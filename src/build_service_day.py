"""Gate D2 / REV02: piloto sintético de serviço, independente de cenários.
Executar na raiz do projeto: python src/build_service_day.py
Não modifica dados de origem nem os arquivos da REV01.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / 'dados' / 'processados' / 'dia_sintetico_450_sessoes_REV01.csv'
OUT = ROOT / 'resultados' / 'servico_REV02'
SEED = 4502026
FLEET = 450
PARAM = dict(energy_kwh_per_km=1.23, passengers_mean=23.0,
             battery_nominal_kwh=350.0, soc_initial=0.90,
             soc_min=0.15, soc_max=0.90, charging_efficiency_dc=1.0,
             service_km_min=120.0, service_km_max=180.0,
             avg_speed_kmh=25.0, minimum_turnaround_min=10.0)


def main():
    if not INPUT.is_file():
        raise FileNotFoundError(f'Arquivo REV01 não encontrado: {INPUT}')
    src = pd.read_csv(INPUT, encoding='utf-8-sig')
    required = {'vehicle_id', 'return_min', 'earliest_min', 'charge_start_min',
                'charge_end_min', 'deadline_min', 'energy_dc_kwh', 'power_dc_kw'}
    if not required.issubset(src.columns):
        raise ValueError(f'Colunas ausentes: {sorted(required - set(src.columns))}')
    if len(src) != FLEET or src.vehicle_id.nunique() != FLEET:
        raise ValueError('Esperados 450 IDs únicos na agenda REV01')
    if not (src.power_dc_kw.gt(0).all() and src.energy_dc_kwh.ge(0).all()):
        raise ValueError('Potência/energia DC inválida na REV01')
    rng = np.random.default_rng(SEED)
    # Serviço independente das energias da REV01. Semente fixa, ordem dos IDs fixa.
    src = src.sort_values('vehicle_id', kind='stable').reset_index(drop=True)
    distances = rng.uniform(PARAM['service_km_min'], PARAM['service_km_max'], FLEET)
    rows, blocks = [], []
    for i, a in src.iterrows():
        km = float(distances[i]); e = km * PARAM['energy_kwh_per_km']
        duration = km / PARAM['avg_speed_kmh'] * 60.0
        # O bloco termina no retorno da REV01; não movemos a janela observada.
        finish = float(a.return_min)
        begin = finish - duration
        timeline_ok = begin >= 0 and finish <= float(a.earliest_min) + 1e-7
        # Energia requerida para repor a tração do dia, antes de perdas auxiliares.
        recharge = float(a.energy_dc_kwh) * PARAM['charging_efficiency_dc']
        initial = PARAM['soc_initial'] * PARAM['battery_nominal_kwh']
        min_e = PARAM['soc_min'] * PARAM['battery_nominal_kwh']
        max_e = PARAM['soc_max'] * PARAM['battery_nominal_kwh']
        after_service = initial - e
        after_charge = after_service + recharge
        traction_ok = after_service >= min_e - 1e-6
        charge_ok = after_charge <= max_e + 1e-6
        balance_gap = recharge - e
        # Divisão de serviço em dois blocos consecutivos, com pausa sintética de 10 min.
        # O tempo de viagem agregado permanece duration; pausa fica antes do segundo bloco.
        pause = PARAM['minimum_turnaround_min']
        block1_duration = duration * 0.5
        block2_duration = duration * 0.5
        block1_start = begin - pause
        block1_end = block1_start + block1_duration
        block2_start = block1_end + pause
        block2_end = block2_start + block2_duration
        timeline_ok = timeline_ok and block1_start >= 0
        for number, st, en, bkm in [(1, block1_start, block1_end, km/2),
                                    (2, block2_start, block2_end, km/2)]:
            blocks.append(dict(vehicle_id=a.vehicle_id, block_id=f'{a.vehicle_id}_B{number}',
                               start_min=round(st, 6), end_min=round(en, 6),
                               distance_km=round(bkm, 6), passengers_mean=PARAM['passengers_mean'],
                               pkm=round(bkm * PARAM['passengers_mean'], 6),
                               mandatory=True, synthetic=True,
                               temporal_status='IN_DAY' if st >= 0 and en <= 1440 else 'OUTSIDE_DAY'))
        rows.append(dict(vehicle_id=a.vehicle_id, return_min=finish,
                         service_start_min=round(block1_start, 6),
                         service_end_min=round(block2_end, 6),
                         charge_earliest_min=float(a.earliest_min),
                         charge_start_min=float(a.charge_start_min),
                         charge_end_min=float(a.charge_end_min),
                         charge_deadline_min=float(a.deadline_min),
                         distance_km=round(km, 6), passengers_mean=PARAM['passengers_mean'],
                         pkm=round(km * PARAM['passengers_mean'], 6),
                         traction_energy_kwh=round(e, 6),
                         charging_energy_dc_kwh=recharge,
                         energy_balance_gap_kwh=round(balance_gap, 6),
                         soc_initial=PARAM['soc_initial'],
                         soc_after_service=round(after_service / PARAM['battery_nominal_kwh'], 6),
                         soc_after_charge=round(after_charge / PARAM['battery_nominal_kwh'], 6),
                         temporal_feasible=bool(timeline_ok),
                         traction_soc_feasible=bool(traction_ok),
                         fixed_charge_soc_feasible=bool(charge_ok),
                         daily_energy_balanced=bool(abs(balance_gap) <= 0.01),
                         status='PASS' if (timeline_ok and traction_ok and charge_ok and abs(balance_gap) <= .01) else 'PENDING_RECONCILIATION'))
    service = pd.DataFrame(rows)
    trips = pd.DataFrame(blocks)
    OUT.mkdir(parents=True, exist_ok=True)
    service.to_csv(OUT / 'veiculos_servico_24h_REV02.csv', index=False, float_format='%.6f')
    trips.to_csv(OUT / 'blocos_servico_24h_REV02.csv', index=False, float_format='%.6f')
    summary = dict(generator='D2_REV02_SYNTHETIC_PILOT', seed=SEED,
                   input_sha256=hashlib.sha256(INPUT.read_bytes()).hexdigest(),
                   assumptions=PARAM, vehicles=len(service), service_blocks=len(trips),
                   total_distance_km=float(service.distance_km.sum()),
                   total_pkm=float(service.pkm.sum()),
                   total_traction_kwh=float(service.traction_energy_kwh.sum()),
                   rev01_charging_dc_kwh=float(service.charging_energy_dc_kwh.sum()),
                   total_energy_balance_gap_kwh=float(service.energy_balance_gap_kwh.sum()),
                   temporal_feasible_vehicles=int(service.temporal_feasible.sum()),
                   traction_soc_feasible_vehicles=int(service.traction_soc_feasible.sum()),
                   fixed_charge_soc_feasible_vehicles=int(service.fixed_charge_soc_feasible.sum()),
                   energy_balanced_vehicles=int(service.daily_energy_balanced.sum()),
                   fully_reconciled_vehicles=int(service.status.eq('PASS').sum()),
                   gate_D2='NOT_APPROVED_PENDING_SERVICE_CHARGE_SOC_RECONCILIATION',
                   note='Do not treat independent service blocks as empirically observed or fully feasible.')
    (OUT / 'validacao_servico_24h_REV02.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print('\nREV02 PILOTO GERADO. Gate D2 permanece pendente.')

if __name__ == '__main__':
    main()

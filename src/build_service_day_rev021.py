"""REV02.1: cronologia contínua de serviço, recarga DC e SOC por veículo.

Executar da raiz: python src/build_service_day_rev021.py
Entradas imutáveis: blocos_servico_24h_REV02.csv e veiculos_servico_24h_REV02.csv.
Saídas novas: resultados/servico_REV021/. Sem MILP, sem PCC e sem alocação de portas.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import math
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
IN_DIR = ROOT / 'resultados' / 'servico_REV02'
OUT_DIR = ROOT / 'resultados' / 'servico_REV021'
BATTERY_KWH = 350.0
SOC_START = 0.90
SOC_MIN = 0.15
SOC_MAX = 0.90
CHARGE_POWER_KW = 138.0
CHARGE_EFFICIENCY = 1.0  # eficiência DC -> bateria, provisória
TURNAROUND_MIN = 10.0
TOL = 1e-7
DAY = 1440.0
# Aquecimento: dois ciclos anteriores, dia de referência e dois posteriores.
CYCLES = range(-2, 3)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _split_at_day_boundaries(start: float, end: float):
    """Particiona evento em segmentos que não atravessam limites de dias."""
    if end <= start + TOL:
        return
    cur = start
    while cur < end - TOL:
        next_boundary = (math.floor(cur / DAY) + 1) * DAY
        nxt = min(end, next_boundary)
        if nxt <= cur + TOL:
            raise AssertionError('Partição temporal sem progresso')
        yield cur, nxt
        cur = nxt


def generate(input_dir: Path = IN_DIR, output_dir: Path = OUT_DIR) -> dict:
    vpath = input_dir / 'veiculos_servico_24h_REV02.csv'
    bpath = input_dir / 'blocos_servico_24h_REV02.csv'
    if not vpath.exists() or not bpath.exists():
        raise FileNotFoundError('Execute primeiro python src/build_service_day.py (REV02).')
    vehicles = pd.read_csv(vpath)
    blocks = pd.read_csv(bpath)
    required_v = {'vehicle_id', 'traction_energy_kwh', 'distance_km', 'pkm', 'return_min'}
    required_b = {'vehicle_id', 'block_id', 'start_min', 'end_min', 'distance_km'}
    if not required_v.issubset(vehicles) or not required_b.issubset(blocks):
        raise ValueError('Colunas obrigatórias ausentes nos arquivos REV02.')
    if vehicles.vehicle_id.duplicated().any() or blocks.block_id.duplicated().any():
        raise ValueError('IDs duplicados nas entradas.')
    if set(vehicles.vehicle_id) != set(blocks.vehicle_id):
        raise ValueError('Conjuntos de veículos inconsistentes.')
    if len(vehicles) != 450 or len(blocks) != 900:
        raise ValueError('Esperados 450 veículos e 900 blocos de serviço.')
    if (blocks.end_min <= blocks.start_min).any():
        raise ValueError('Bloco com duração inválida.')
    if (vehicles.traction_energy_kwh < 0).any():
        raise ValueError('Energia de tração negativa.')

    all_events, all_windows, all_conflicts, all_summary = [], [], [], []
    for _, vehicle in vehicles.sort_values('vehicle_id').iterrows():
        vid = str(vehicle.vehicle_id)
        b = blocks.loc[blocks.vehicle_id == vid].sort_values('start_min')
        if len(b) != 2:
            raise ValueError(f'{vid}: esperado exatamente dois blocos de serviço.')
        base = []
        total_km = float(b.distance_km.sum())
        if abs(total_km - float(vehicle.distance_km)) > 0.002:
            raise ValueError(f'{vid}: quilômetros não conservados na REV02.')
        for _, block in b.iterrows():
            st, en = float(block.start_min), float(block.end_min)
            if st < -DAY or en > 2 * DAY:
                raise ValueError(f'{vid}: bloco fora do intervalo suportado.')
            e = float(vehicle.traction_energy_kwh) * float(block.distance_km) / total_km
            base.append((st, en, str(block.block_id), e))
        if base[0][1] > base[1][0] + TOL:
            raise ValueError(f'{vid}: blocos sobrepostos.')
        # Pausa entre blocos NÃO é automaticamente disponibilidade na garagem.
        if abs(base[-1][1] - float(vehicle.return_min)) > 0.002:
            raise ValueError(f'{vid}: fim do serviço difere do retorno informado.')
        if base[-1][1] + TURNAROUND_MIN > base[0][0] + DAY - TURNAROUND_MIN + TOL:
            raise ValueError(f'{vid}: serviço e margem operacional impedem janela diária.')

        # Serviço repetido a cada 24h: hipótese sintética explícita, não observação.
        # Inicialização de SOC no primeiro serviço do ciclo -2; aquecimento sem reset.
        soc_kwh = SOC_START * BATTERY_KWH
        min_kwh, max_kwh = SOC_MIN * BATTERY_KWH, SOC_MAX * BATTERY_KWH
        charge_deficit = 0.0
        soc_violations = 0
        events = []
        windows = []
        conflicts = []
        for cycle in CYCLES:
            shift = cycle * DAY
            first_start = base[0][0] + shift
            last_end = base[-1][1] + shift
            next_start = base[0][0] + (cycle + 1) * DAY
            for st, en, bid, energy in base:
                s, e = st + shift, en + shift
                start_soc = soc_kwh / BATTERY_KWH
                soc_kwh -= energy
                end_soc = soc_kwh / BATTERY_KWH
                if soc_kwh < min_kwh - 1e-6:
                    soc_violations += 1
                    conflicts.append(dict(vehicle_id=vid, cycle=cycle, type='SOC_BELOW_MIN',
                                          start_min=s, end_min=e, deficit_kwh=min_kwh - soc_kwh))
                events.append(dict(vehicle_id=vid, cycle=cycle, event_type='SERVICE',
                                   block_id=bid, start_min=s, end_min=e,
                                   energy_traction_kwh=energy, energy_charge_dc_kwh=0.0,
                                   soc_start=start_soc, soc_end=end_soc))
            # O serviço completo termina em last_end. Antes de next_start, o veículo
            # fica na garagem; 10 min em cada extremidade são indisponíveis.
            ws = last_end + TURNAROUND_MIN
            we = next_start - TURNAROUND_MIN
            if we < ws - TOL:
                conflicts.append(dict(vehicle_id=vid, cycle=cycle, type='NO_CHARGE_WINDOW',
                                      start_min=ws, end_min=we, deficit_kwh=0.0))
                ws = we
            window_duration = max(0.0, we - ws)
            capacity = CHARGE_POWER_KW * window_duration / 60.0 * CHARGE_EFFICIENCY
            needed = max(0.0, max_kwh - soc_kwh)
            delivered = min(needed, capacity)
            deficit = max(0.0, needed - delivered)
            if deficit > 1e-6:
                charge_deficit += deficit
                conflicts.append(dict(vehicle_id=vid, cycle=cycle, type='CHARGE_WINDOW_SHORTFALL',
                                      start_min=ws, end_min=we, deficit_kwh=deficit))
            charge_end = ws + delivered / (CHARGE_POWER_KW * CHARGE_EFFICIENCY) * 60.0
            windows.append(dict(vehicle_id=vid, cycle=cycle, available_start_min=ws,
                                available_end_min=we, available_minutes=window_duration,
                                energy_capacity_kwh=capacity, energy_required_kwh=needed,
                                energy_scheduled_kwh=delivered, deficit_kwh=deficit))
            if delivered > TOL:
                initial = soc_kwh / BATTERY_KWH
                soc_kwh += delivered
                events.append(dict(vehicle_id=vid, cycle=cycle, event_type='CHARGE',
                                   block_id='', start_min=ws, end_min=charge_end,
                                   energy_traction_kwh=0.0, energy_charge_dc_kwh=delivered,
                                   soc_start=initial, soc_end=soc_kwh / BATTERY_KWH))
            # A janela ociosa é implícita; SOC constante até próximo serviço.
            if soc_kwh > max_kwh + 1e-6:
                raise AssertionError(f'{vid}: SOC acima do máximo.')

        # Eventos ordenados cronologicamente e segmentados nas fronteiras do dia.
        events.sort(key=lambda x: (x['start_min'], x['end_min']))
        for left, right in zip(events, events[1:]):
            if right['start_min'] < left['end_min'] - TOL:
                raise AssertionError(f'{vid}: eventos sobrepostos.')
            if abs(left['soc_end'] - right['soc_start']) > 1e-7:
                raise AssertionError(f'{vid}: SOC descontínuo entre eventos.')
        segmented = []
        for ev in events:
            duration = ev['end_min'] - ev['start_min']
            if duration <= 0:
                raise AssertionError('Evento sem duração.')
            for s, e in _split_at_day_boundaries(ev['start_min'], ev['end_min']):
                f0 = (s - ev['start_min']) / duration
                f1 = (e - ev['start_min']) / duration
                part = dict(ev)
                part.update(start_min=s, end_min=e,
                            energy_traction_kwh=ev['energy_traction_kwh'] * (f1 - f0),
                            energy_charge_dc_kwh=ev['energy_charge_dc_kwh'] * (f1 - f0),
                            soc_start=ev['soc_start'] + (ev['soc_end'] - ev['soc_start']) * f0,
                            soc_end=ev['soc_start'] + (ev['soc_end'] - ev['soc_start']) * f1,
                            day_index=math.floor(s / DAY))
                segmented.append(part)

        def soc_at(t):
            for ev in events:
                if ev['start_min'] - TOL <= t <= ev['end_min'] + TOL:
                    frac = min(1.0, max(0.0, (t - ev['start_min']) / (ev['end_min'] - ev['start_min'])))
                    return ev['soc_start'] + (ev['soc_end'] - ev['soc_start']) * frac
            earlier = [ev for ev in events if ev['end_min'] < t]
            if earlier:
                return earlier[-1]['soc_end']
            raise AssertionError(f'{vid}: sem estado inicial em t={t}')

        s0, s24 = soc_at(0.0), soc_at(DAY)
        day_events = [e for e in segmented if e['day_index'] == 0]
        day_traction = sum(e['energy_traction_kwh'] for e in day_events)
        day_charge = sum(e['energy_charge_dc_kwh'] for e in day_events)
        residual = BATTERY_KWH * (s24 - s0) - (day_charge - day_traction)
        if abs(residual) > 1e-5:
            raise AssertionError(f'{vid}: conservação energética falhou: {residual}')
        cyclic = abs(s24 - s0) <= 1e-6
        day_min_soc = min([s0, s24] + [e['soc_start'] for e in day_events] + [e['soc_end'] for e in day_events])
        valid_soc = day_min_soc >= SOC_MIN - 1e-7 and max([s0,s24]+[e['soc_start'] for e in day_events]+[e['soc_end'] for e in day_events]) <= SOC_MAX + 1e-7
        all_summary.append(dict(vehicle_id=vid, soc_at_00=s0, soc_at_24=s24,
                                soc_delta=s24-s0, day_traction_kwh=day_traction,
                                day_charge_dc_kwh=day_charge,
                                energy_residual_kwh=residual,
                                soc_within_bounds=valid_soc,
                                periodic_soc=cyclic,
                                status='PASS_INDIVIDUAL_PILOT' if valid_soc and cyclic else 'PENDING'))
        all_events.extend(segmented)
        all_windows.extend(windows)
        all_conflicts.extend(conflicts)

    out_events = pd.DataFrame(all_events)
    out_windows = pd.DataFrame(all_windows)
    out_vehicles = pd.DataFrame(all_summary)
    out_conflicts = pd.DataFrame(all_conflicts, columns=['vehicle_id','cycle','type','start_min','end_min','deficit_kwh'])
    output_dir.mkdir(parents=True, exist_ok=True)
    out_events.to_csv(output_dir / 'eventos_cronologicos_REV021.csv', index=False, float_format='%.9f')
    out_windows.to_csv(output_dir / 'janelas_recarga_REV021.csv', index=False, float_format='%.9f')
    out_vehicles.to_csv(output_dir / 'auditoria_veiculos_REV021.csv', index=False, float_format='%.9f')
    out_conflicts.to_csv(output_dir / 'conflitos_REV021.csv', index=False, float_format='%.9f')
    summary = {
        'generator': 'D2_REV021_CONTINUOUS_DAILY_SYNTHETIC_PILOT',
        'input_sha256': {vpath.name: _sha(vpath), bpath.name: _sha(bpath)},
        'assumptions': {'day_minutes': 1440, 'cycles': list(CYCLES), 'battery_kwh': BATTERY_KWH,
                        'soc_initial_at_warmup_start': SOC_START, 'soc_min': SOC_MIN,
                        'soc_max': SOC_MAX, 'charge_power_dc_kw': CHARGE_POWER_KW,
                        'dc_battery_efficiency': CHARGE_EFFICIENCY,
                        'turnaround_each_side_min': TURNAROUND_MIN,
                        'service_repeated_every_1440_min': True,
                        'service_energy_uniform_within_each_block': True,
                        'charging_policy': 'GREEDY_EARLIEST_AVAILABLE_TO_SOC_MAX',
                        'no_charger_port_allocation': True, 'no_pcc_constraint': True},
        'vehicles': len(out_vehicles),
        'events_all_days': len(out_events),
        'windows_all_days': len(out_windows),
        'day_traction_kwh': float(out_vehicles.day_traction_kwh.sum()),
        'day_charge_dc_kwh': float(out_vehicles.day_charge_dc_kwh.sum()),
        'day_soc_bounded_vehicles': int(out_vehicles.soc_within_bounds.sum()),
        'day_periodic_soc_vehicles': int(out_vehicles.periodic_soc.sum()),
        'day_individual_pilot_pass': int(out_vehicles.status.eq('PASS_INDIVIDUAL_PILOT').sum()),
        'max_abs_energy_residual_kwh': float(out_vehicles.energy_residual_kwh.abs().max()),
        'conflicts_by_type': {str(k): int(v) for k, v in out_conflicts.type.value_counts().items()},
        'gate_D2': 'NOT_APPROVED_REQUIRES_CHARGER_ASSIGNMENT_PCC_AND_FULL_SERVICE_VALIDATION',
        'warning': 'SOC start at -2 cycles is a warmup assumption; not a certified periodic fixed point.'
    }
    (output_dir / 'validacao_servico_REV021.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    return summary


if __name__ == '__main__':
    print(json.dumps(generate(), indent=2, ensure_ascii=False))

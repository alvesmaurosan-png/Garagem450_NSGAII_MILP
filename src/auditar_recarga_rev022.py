from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'resultados' / 'servico_REV021'
OUT = ROOT / 'resultados' / 'recarga_REV022'
DAY = 1440.0
TOL = 1e-7


def audit(events: pd.DataFrame):
    required = {'vehicle_id','event_type','start_min','end_min','energy_charge_dc_kwh'}
    missing = required - set(events.columns)
    if missing:
        raise ValueError(f'Colunas ausentes: {sorted(missing)}')
    charges = events.loc[events['event_type'].eq('CHARGE')].copy()
    if charges.empty:
        raise ValueError('Nenhum evento CHARGE encontrado')
    for col in ('start_min','end_min','energy_charge_dc_kwh'):
        charges[col] = pd.to_numeric(charges[col], errors='raise')
    if not np.isfinite(charges[['start_min','end_min','energy_charge_dc_kwh']].to_numpy()).all():
        raise ValueError('Valores nao finitos em eventos de recarga')
    if ((charges.end_min - charges.start_min) <= 0).any() or (charges.energy_charge_dc_kwh < 0).any():
        raise ValueError('Duracao ou energia invalida')
    charges['power_dc_kw'] = charges.energy_charge_dc_kwh * 60 / (charges.end_min - charges.start_min)
    if (charges.power_dc_kw > 138 + 1e-5).any():
        raise ValueError('Recarga acima de 138 kW DC')
    charges['clipped_start'] = charges.start_min.clip(lower=0,upper=DAY)
    charges['clipped_end'] = charges.end_min.clip(lower=0,upper=DAY)
    active = charges.loc[charges.clipped_end - charges.clipped_start > TOL].copy()
    # Sweep-line: half-open intervals [start,end); end before start at a tie.
    boundaries = [(0.0,0.0,0),(DAY,0.0,0)]
    for r in active.itertuples(index=False):
        boundaries.append((float(r.clipped_start),float(r.power_dc_kw),1))
        boundaries.append((float(r.clipped_end),-float(r.power_dc_kw),-1))
    # Aggregate equal timestamps to avoid artificial transient peaks.
    changes = {}
    for t,dp,dc in boundaries:
        a,b=changes.get(t,(0.0,0))
        changes[t]=(a+dp,b+dc)
    times=sorted(changes)
    power=0.0; count=0; segments=[]
    for i,t in enumerate(times[:-1]):
        dp,dc=changes[t]
        power+=dp; count+=dc
        nxt=times[i+1]
        if nxt>t:
            if power < -1e-5 or count<0:
                raise ValueError('Inconsistencia na varredura de eventos')
            segments.append((t,nxt,max(0.0,power),count))
    seg=pd.DataFrame(segments,columns=['start_min','end_min','power_dc_kw','concurrent_vehicles'])
    if len(seg)==0:
        raise ValueError('Nao ha intervalos no dia')
    hours=[]
    for h in range(24):
        left=60*h; right=left+60
        overlap=np.maximum(0,np.minimum(seg.end_min.to_numpy(),right)-np.maximum(seg.start_min.to_numpy(),left))
        e=float(np.dot(overlap,seg.power_dc_kw.to_numpy())/60)
        hours.append({'hour':h,'energy_dc_kwh':e,'average_power_dc_kw':e})
    hourly=pd.DataFrame(hours)
    expected=float(((active.clipped_end-active.clipped_start)*active.power_dc_kw/60).sum())
    observed=float(hourly.energy_dc_kwh.sum())
    if not np.isclose(expected,observed,rtol=0,atol=1e-5):
        raise AssertionError(f'Conservacao falhou: {expected} != {observed}')
    # Charging overlap per vehicle is invalid, regardless of charger assignment.
    overlap_vehicles=[]
    for vid,g in active.sort_values(['vehicle_id','clipped_start']).groupby('vehicle_id'):
        if (g.clipped_start.to_numpy()[1:] < g.clipped_end.to_numpy()[:-1]-TOL).any():
            overlap_vehicles.append(str(vid))
    if overlap_vehicles:
        raise ValueError(f'Eventos CHARGE sobrepostos no mesmo veiculo: {overlap_vehicles[:10]}')
    metrics={
        'generator':'REV022_FIXED_SCHEDULE_CHARGING_AUDIT',
        'day_minutes':1440,
        'charge_events_all_cycles':int(len(charges)),
        'charge_events_intersecting_day':int(len(active)),
        'charging_vehicles_in_day':int(active.vehicle_id.nunique()),
        'max_simultaneous_charging_vehicles':int(seg.concurrent_vehicles.max()),
        'minimum_138kw_ports_for_fixed_schedule':int(seg.concurrent_vehicles.max()),
        'peak_aggregate_dc_kw':float(seg.power_dc_kw.max()),
        'energy_dc_within_day_kwh':observed,
        'max_hourly_average_dc_kw':float(hourly.average_power_dc_kw.max()),
        'max_energy_residual_kwh':abs(expected-observed),
        'scope':'Fixed REV021 charging events; no port assignment, AC conversion, PCC or dispatch optimization'
    }
    return seg,hourly,metrics


def main():
    events=pd.read_csv(SOURCE/'eventos_cronologicos_REV021.csv')
    seg,hourly,metrics=audit(events)
    OUT.mkdir(parents=True,exist_ok=True)
    seg.to_csv(OUT/'potencia_segmentos_REV022.csv',index=False)
    hourly.to_csv(OUT/'recarga_horaria_REV022.csv',index=False)
    (OUT/'auditoria_recarga_REV022.json').write_text(json.dumps(metrics,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(metrics,indent=2,ensure_ascii=False))


if __name__=='__main__':
    main()

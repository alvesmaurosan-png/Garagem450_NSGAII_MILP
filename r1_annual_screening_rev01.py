import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path('resultados/R1_G5_1_REV01')
PV = 1625.964844738918
PCC = 2500.0
ETA = .9727
CHP = 120*100*6*.35*.95
TOL = 1e-6

def main():
    d = pd.read_csv('dados/originais/D28_solar_8760_modelo.csv')
    utc = pd.to_datetime(d.UTC, utc=True, errors='raise')
    local = pd.to_datetime(d.data_local, utc=True, errors='raise')
    expected = pd.date_range('2025-01-01', periods=8760, freq='h', tz='UTC')
    if len(d)!=8760 or not np.array_equal(utc.array.asi8, expected.asi8) or not np.array_equal(utc.array.asi8, local.array.asi8):
        raise ValueError('Serie temporal inconsistente')
    p = d.pv_proxy_kw_por_kWp_media_h.to_numpy(float)
    e = d.pv_proxy_kWh_por_kWp_h.to_numpy(float)
    if not np.isfinite(p).all() or (p<0).any() or not np.allclose(p,e,rtol=0,atol=1e-9):
        raise ValueError('Potencia/energia PV inconsistente')
    v = pd.read_csv('resultados/R1_IMPLEMENTACAO_CONTROLADA_REV01/adapter_service/r1_vehicle_slots_15min_rev01.csv')
    if len(v)!=43200 or v.vehicle_id.nunique()!=450 or v.duplicated(['vehicle_id','slot']).any() or not v.groupby('vehicle_id').slot.apply(lambda s: set(s)==set(range(96))).all():
        raise ValueError('Grade veicular invalida')
    tr = v.traction_kwh.to_numpy(float)
    if not np.isfinite(tr).all() or (tr<0).any(): raise ValueError('Tracao invalida')
    demand = float(tr.sum()/ETA)
    order = np.roll(np.arange(8760),-3)
    h = pd.DataFrame({'synthetic_local':pd.date_range('2025-01-01',periods=8760,freq='h'), 'source_utc':d.UTC.iloc[order].to_numpy(), 'source_status':d.status_A701.iloc[order].to_numpy(), 'wrapped':order<3, 'pv_kw':p[order]*PV})
    assert abs(h.pv_kw.sum()-p.sum()*PV)<TOL
    daily = pd.DataFrame({'day':pd.date_range('2025-01-01',periods=365,freq='D'), 'pv_kwh':h.pv_kw.to_numpy().reshape(365,24).sum(axis=1)})
    daily['estimated_hours'] = (h.source_status!='observado').to_numpy().reshape(365,24).sum(axis=1)
    scenarios = {}
    for tag,f in [('100',1),('96',.96),('50',.5),('0',0)]:
        lb = np.maximum(0,demand-daily.pv_kwh.to_numpy()-CHP*f)
        deficit = np.maximum(0,lb-PCC*24)
        daily['grid_lb_'+tag]=lb
        daily['deficit_'+tag]=deficit
        bad=deficit>TOL
        runs=[]
        if bad.all(): runs=[list(range(365))]
        elif bad.any():
            for i in range(365):
                if bad[i] and not bad[(i-1)%365]:
                    r=[]; j=i
                    while bad[j]:
                        r.append(j); j=(j+1)%365
                    runs.append(r)
        worst=sorted(runs,key=lambda r:float(deficit[r].sum()),reverse=True)
        scenarios[tag]={'critical_days':int(bad.sum()),'sum_daily_deficits_kwh':float(deficit.sum()),'max_daily_deficit_kwh':float(deficit.max()),'longest_cyclic_run_days':max(map(len,runs),default=0),'worst_runs':[{'start':str(daily.day.iloc[r[0]].date()),'end':str(daily.day.iloc[r[-1]].date()),'days':len(r),'deficit_kwh':float(deficit[r].sum())} for r in worst[:10]],'annual_energy_margin_kwh':float(365*(PCC*24+CHP*f-demand)+daily.pv_kwh.sum())}
    report={'status':'SCREENING_ONLY','annual_feasibility_certified':False,'calendar':'synthetic local cyclic rotation of 3 hours','pv_kwp':PV,'traction_dc_kwh_day':float(tr.sum()),'demand_ac_kwh_day':demand,'pv_annual_kwh':float(h.pv_kw.sum()),'pv_daily_min_kwh':float(daily.pv_kwh.min()),'pv_daily_mean_kwh':float(daily.pv_kwh.mean()),'pv_daily_max_kwh':float(daily.pv_kwh.max()),'source_status_counts':{str(k):int(n) for k,n in d.status_A701.value_counts().items()},'scenarios':scenarios,'limitations':['Daily deficits assume zero net storage transfer including vehicle batteries and gas storage.','CHP fractions are energy sensitivity assumptions, not outage schedules or universal bounds.','No temporal MILP or physical biomass validation.']}
    ROOT.mkdir(parents=True,exist_ok=True)
    h.to_csv(ROOT/'pv_local_hourly.csv',index=False)
    daily.to_csv(ROOT/'daily_screening.csv',index=False)
    daily.nsmallest(15,'pv_kwh').to_csv(ROOT/'critical_days.csv',index=False)
    (ROOT/'screening_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(report,indent=2,ensure_ascii=False))
if __name__=='__main__': main()

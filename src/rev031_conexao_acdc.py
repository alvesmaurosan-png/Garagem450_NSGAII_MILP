"""REV03.1: diagnóstico rede AC -> recarga DC (24h), sem geração/armazenamento.
Preserva REV02.3a. Duas análises distintas:
  frozen: agenda de 29 portas previamente auditada, SEM reescalonamento.
  lp: reescalonamento LP com SOC periódico, relaxando a contagem discreta de portas.
A inviabilidade energética da rede isolada é independente dessa relaxação.
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import linprog

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from otimizar_recarga_rev023 import build_data, BATTERY, SOC_MIN, SOC_MAX, PORT_KW, ETA
from otimizar_recarga_rev023a import prepare, decode, validate


def hash_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def energy_screen(dc_kwh, pcc_kw, acdc_eff, hours=24):
    if not (0<acdc_eff<=1) or pcc_kw<=0: raise ValueError('Eficiência/PCC inválidos')
    ac_needed=dc_kwh/acdc_eff
    grid_max=pcc_kw*hours
    return {'dc_energy_kwh':float(dc_kwh),'ac_energy_required_kwh':float(ac_needed),
            'grid_energy_max_kwh':float(grid_max),'minimum_ac_energy_deficit_kwh':float(max(0,ac_needed-grid_max)),
            'grid_only_energy_feasible_necessary_condition':bool(ac_needed<=grid_max+1e-7)}


def solve_relaxed_dispatch(d, efficiency, pcc_kw, dc_ports, target='min_pcc_violation'):
    """LP com variável de ultrapassagem uniforme s>=0; objetivo min s.
    Portas: somente teto agregado (relaxação), NÃO número de conexões.
    """
    if not (0<efficiency<=1) or pcc_kw<=0 or dc_ports<1:raise ValueError('Parâmetros inválidos')
    A=d['A'];m=d['m'];size=d['size'];T=d['T'];step=d['step']
    from scipy.sparse import coo_matrix, vstack, hstack
    # Variável adicional s (kW AC) com P <= efficiency*(pcc+s)
    # Restrições agregadas por slot: P <= min(dc_ports*PORT_KW, efficiency*(pcc+s)).
    rr=[];cc=[];vv=[];bb=[]
    ix=d['ix']
    for t in range(T):
        r=len(bb)
        for i in range(d['n']):
            k=int(ix[i,t])
            if k>=0: rr.append(r);cc.append(k);vv.append(60/step/efficiency)
        rr.append(r);cc.append(size);vv.append(-1.)
        bb.append(float(pcc_kw))
    Aextra=coo_matrix((vv,(rr,cc)),shape=(T,size+1)).tocsr()
    Acap=[];ac_r=[];ac_c=[];ac_v=[]
    for t in range(T):
        r=t
        for i in range(d['n']):
            k=int(ix[i,t])
            if k>=0:ac_r.append(r);ac_c.append(k);ac_v.append(60/step)
        Acap.append(float(dc_ports*PORT_KW))
    Aport=coo_matrix((ac_v,(ac_r,ac_c)),shape=(T,size+1)).tocsr()
    aub=vstack([hstack([d['Aub'],coo_matrix((d['Aub'].shape[0],1))],format='csr'),Aextra,Aport],format='csr')
    bub=np.r_[d['bub'],bb,Acap]
    aeq=hstack([d['Aeq'],coo_matrix((d['Aeq'].shape[0],1))],format='csr')
    obj=np.zeros(size+1);obj[-1]=1
    bounds=d['bounds']+[(0,None)]
    res=linprog(obj,A_ub=aub,b_ub=bub,A_eq=aeq,b_eq=d['beq'],bounds=bounds,method='highs')
    if not res.success:return {'status':res.message,'status_code':int(res.status)},None
    x,initial,_=decode(d,res.x)
    audit,soc=validate(d,x,initial)
    ac_kw=x.sum(axis=0)*60/step/efficiency
    dc_kw=x.sum(axis=0)*60/step
    if not audit['valid']:raise RuntimeError(f'Auditoria LP falhou: {audit}')
    if np.max(dc_kw)>dc_ports*PORT_KW+1e-5:raise RuntimeError('Teto DC violado')
    if np.max(ac_kw-pcc_kw)>res.x[-1]+1e-5:raise RuntimeError('Slack violado')
    agg=pd.DataFrame({'slot':np.arange(T),'start_min':np.arange(T)*step,
        'dc_kw':dc_kw,'ac_kw':ac_kw,'grid_import_kw_capped':np.minimum(ac_kw,pcc_kw),
        'pcc_excess_kw':np.maximum(ac_kw-pcc_kw,0),'charging_vehicles':(x>1e-6).sum(axis=0),
        'dc_energy_kwh':x.sum(axis=0),'traction_energy_kwh':d['traction'].sum(axis=0)})
    summary={'status':res.message,'status_code':int(res.status),'peak_dc_kw':float(dc_kw.max()),
        'peak_ac_kw':float(ac_kw.max()),'max_pcc_excess_kw':float(np.maximum(ac_kw-pcc_kw,0).max()),
        'optimized_uniform_excess_kw':float(res.x[-1]),
        'ac_energy_kwh':float(ac_kw.sum()*step/60),
        'energy_above_pcc_kwh':float(np.maximum(ac_kw-pcc_kw,0).sum()*step/60),
        'max_concurrent_charging_vehicles':int((x>1e-6).sum(axis=0).max()),
        'discrete_29_port_constraint_enforced':False,'audit':audit}
    return summary,agg


def frozen_schedule(path, expected_vehicles, expected_energy):
    df=pd.read_csv(path)
    need={'vehicle_id','slot','charge_dc_kwh','port_active'}
    if not need.issubset(df):raise ValueError(f'CSV congelado sem colunas: {need-set(df.columns)}')
    if df.duplicated(['vehicle_id','slot']).any():raise ValueError('Duplicatas de veículo/slot')
    if df['slot'].min()<0 or df['slot'].max()>95:raise ValueError('Slots fora de 24h/15min')
    if abs(df.charge_dc_kwh.sum()-expected_energy)>0.01:raise ValueError('Energia congelada inconsistente')
    if len(df.vehicle_id.unique())!=expected_vehicles:raise ValueError('Veículos ausentes')
    if ((df.charge_dc_kwh>1e-6)&(df.port_active!=1)).any():raise ValueError('Porta não contabilizada')
    if df.charge_dc_kwh.max()>PORT_KW*.25+1e-5:raise ValueError('Limite individual violado')
    agg=df.groupby('slot').agg(dc_energy_kwh=('charge_dc_kwh','sum'),charging_vehicles=('port_active','sum')).reindex(range(96),fill_value=0)
    if agg.charging_vehicles.max()>29:raise ValueError('Mais de 29 portas')
    return agg.reset_index()


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--acdc-efficiency',type=float,default=.95,help='Hipótese exploratória, não homologada')
    ap.add_argument('--pcc-kw',type=float,default=2500)
    ap.add_argument('--ports',type=int,default=29)
    ap.add_argument('--skip-lp',action='store_true')
    args=ap.parse_args()
    if not (0<args.acdc_efficiency<=1) or args.pcc_kw<=0 or args.ports!=29:ap.error('REV03.1 exige eficiência válida, PCC positivo e 29 portas congeladas')
    inp=ROOT/'resultados'/'servico_REV02'
    vp=inp/'veiculos_servico_24h_REV02.csv';bp=inp/'blocos_servico_24h_REV02.csv'
    freeze=ROOT/'resultados'/'recarga_REV023a'/'veiculos_best_peak_REV023a.csv'
    for p in [vp,bp,freeze]:
        if not p.is_file():raise FileNotFoundError(f'Entrada ausente: {p}')
    vids,tr,allowed,km,pkm=build_data(pd.read_csv(vp),pd.read_csv(bp),15)
    dc_energy=float(tr.sum());screen=energy_screen(dc_energy,args.pcc_kw,args.acdc_efficiency)
    frozen=frozen_schedule(freeze,len(vids),dc_energy)
    frozen['start_min']=frozen.slot*15
    frozen['dc_kw']=frozen.dc_energy_kwh*4
    frozen['ac_kw']=frozen.dc_kw/args.acdc_efficiency
    frozen['pcc_excess_kw']=np.maximum(frozen.ac_kw-args.pcc_kw,0)
    frozen['grid_import_kw_capped']=np.minimum(frozen.ac_kw,args.pcc_kw)
    frozen_info={'peak_dc_kw':float(frozen.dc_kw.max()),'peak_ac_kw':float(frozen.ac_kw.max()),
        'peak_pcc_excess_kw':float(frozen.pcc_excess_kw.max()),
        'energy_above_pcc_kwh':float(frozen.pcc_excess_kw.sum()*.25),
        'max_ports_active':int(frozen.charging_vehicles.max()),'daily_dc_kwh':float(frozen.dc_energy_kwh.sum())}
    out=ROOT/'resultados'/'conexao_REV031'
    out.mkdir(parents=True,exist_ok=True)
    frozen.to_csv(out/'agenda_congelada_acdc_REV031.csv',index=False)
    summary={'generator':'REV031_ACDC_GRID_ONLY_DIAGNOSTIC','scenario':'450_BEV_grid_only',
        'frozen_reference':'REV02.3a peak 29 portas','n_vehicles':len(vids),
        'service_total_km':float(km.sum()),'service_total_pkm':float(pkm.sum()),
        'parameters':{'pcc_kw':args.pcc_kw,'acdc_efficiency_exploratory':args.acdc_efficiency,
                      'port_dc_kw':PORT_KW,'frozen_ports':29,'step_min':15,
                      'battery_dc_efficiency_provisional':ETA},
        'input_sha256':{p.name:hash_file(p) for p in [vp,bp,freeze]},
        'necessary_energy_screen':screen,'frozen_schedule':frozen_info,
        'grid_only_feasible':False if not screen['grid_only_energy_feasible_necessary_condition'] else None,
        'grid_only_feasibility_basis':'ENERGY_IMPOSSIBILITY_CERTIFICATE' if not screen['grid_only_energy_feasible_necessary_condition'] else 'NOT_DETERMINED'}
    if not args.skip_lp:
        d=prepare(tr,allowed,15)
        lp,agg=solve_relaxed_dispatch(d,args.acdc_efficiency,args.pcc_kw,args.ports)
        summary['relaxed_dispatch_lp']=lp
        if agg is not None:agg.to_csv(out/'despacho_lp_relaxado_REV031.csv',index=False)
    (out/'auditoria_REV031.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(summary,indent=2,ensure_ascii=False))

if __name__=='__main__':main()

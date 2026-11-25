"""REV02.3 — programação periódica de recarga, LP + MILP, sem PV/BESS/CHP.

Requer: numpy, pandas, scipy>=1.11. Executar da raiz:
    python src/otimizar_recarga_rev023.py
    python src/otimizar_recarga_rev023.py --time-limit 300 --mip-gap 0.02

Etapa A: minimiza pico DC por LP (limite inferior sem portas discretas).
Etapa B: minimiza número de portas via MILP, com pico limitado ao ótimo LP
          mais tolerância explícita. Se inviável, ampliar --peak-slack-kw.
Não certifica disponibilidade física de portas nem potência AC/PCC.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import linprog, milp, Bounds, LinearConstraint
from scipy.sparse import coo_matrix, vstack, csr_matrix

ROOT = Path(__file__).resolve().parents[1]
DAY = 1440.0
BATTERY = 350.0
SOC_MIN = .15
SOC_MAX = .90
PORT_KW = 138.0
ETA = 1.0
TURNAROUND = 10.0

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def build_data(vehicles, blocks, step=15):
    """Conservador: recarga somente em slots inteiramente dentro da janela.
    Tração distribuída por interseção exata de blocos com cada slot.
    SOC inicial é variável, com SOC(0)=SOC(24h) imposto.
    """
    if 1440 % step:
        raise ValueError('step deve dividir 1440')
    vids = sorted(vehicles.vehicle_id.astype(str).tolist())
    if len(vids) != len(set(vids)):
        raise ValueError('IDs de veículos duplicados')
    bmap = {v: d.sort_values('start_min') for v,d in blocks.groupby('vehicle_id')}
    n, T = len(vids), 1440 // step
    traction = np.zeros((n,T))
    allowed = np.zeros((n,T),dtype=bool)
    service_km = np.zeros(n)
    service_pkm = np.zeros(n)
    for i, vid in enumerate(vids):
        v = vehicles.loc[vehicles.vehicle_id == vid]
        if len(v) != 1 or vid not in bmap:
            raise ValueError(f'{vid}: veículo ou blocos ausentes')
        v = v.iloc[0]
        b = bmap[vid]
        if len(b)!=2:
            raise ValueError(f'{vid}: esperado dois blocos')
        km = float(b.distance_km.sum())
        if km <= 0 or abs(km-float(v.distance_km))>0.002:
            raise ValueError(f'{vid}: distância inconsistente')
        service_km[i], service_pkm[i] = km, float(v.pkm)
        energy = float(v.traction_energy_kwh)
        periods = []
        for _, r in b.iterrows():
            s,e=float(r.start_min),float(r.end_min)
            if e<=s:
                raise ValueError('Duração inválida')
            periods.append((s,e,energy*float(r.distance_km)/km))
        if periods[0][1] > periods[1][0] + 1e-7:
            raise ValueError(f'{vid}: serviço sobreposto')
        first,last=periods[0][0],periods[-1][1]
        for cycle in (-2,-1,0,1,2):
            shift=cycle*DAY
            for s,e,en in periods:
                s+=shift;e+=shift
                left=max(0,int(np.floor(s/step)))
                right=min(T,int(np.ceil(e/step)))
                for t in range(left,right):
                    overlap=max(0.0,min(e,(t+1)*step)-max(s,t*step))
                    traction[i,t]+=en*overlap/(e-s)
            ws=last+shift+TURNAROUND
            we=first+(cycle+1)*DAY-TURNAROUND
            for t in range(T):
                if t*step >= ws-1e-8 and (t+1)*step <= we+1e-8:
                    allowed[i,t]=True
    return vids, traction, allowed, service_km, service_pkm

def solve_model(traction, allowed, step=15, time_limit=300, mip_gap=.02, peak_slack_kw=1.0):
    """Variáveis x[i,t] = energia DC no slot, y[i] = energia inicial,
    z[i,t] binária = porta ocupada, P = pico, N = número de portas.
    LP A minimiza P; MILP B minimiza N sob P<=P*_LP+folga.
    """
    n,T=traction.shape
    assert allowed.shape==(n,T)
    cap=PORT_KW*step/60
    lo=SOC_MIN*BATTERY; hi=SOC_MAX*BATTERY
    if np.any(traction.sum(axis=1)>hi-lo+1e-7):
        raise ValueError('Serviço diário supera autonomia útil sem recarga intermediária; verificar blocos')
    # LP: x[i,t] para slots disponíveis; y[i]; P.
    positions=np.argwhere(allowed)
    m=len(positions)
    if m==0: raise ValueError('Sem janelas de recarga')
    ix={(int(i),int(t)):k for k,(i,t) in enumerate(positions)}
    y0=m; pidx=m+n; size=pidx+1
    rows=[]; cols=[]; vals=[]; lower=[]; upper=[]
    def add(items,low,up):
        r=len(lower)
        for c,a in items:
            if a: rows.append(r);cols.append(c);vals.append(float(a))
        lower.append(low);upper.append(up)
    for i in range(n):
        keys=[ix[i,t] for t in range(T) if (i,t) in ix]
        add([(k,1) for k in keys],float(traction[i].sum())/ETA,float(traction[i].sum())/ETA)
        # SOC em cada fronteira: y + eta * carga acumulada - tração acumulada.
        # Só avaliar após instantes em que muda o estado (slots com consumo/recarga).
        cum=[]; cum_e=0.0
        for t in range(T):
            if (i,t) in ix: cum.append(ix[i,t])
            cum_e+=traction[i,t]
            if traction[i,t]>1e-10 or (i,t) in ix:
                add([(y0+i,1)]+[(k,ETA) for k in cum],lo+cum_e,hi+cum_e)
    for t in range(T):
        add([(ix[i,t],60/step) for i in range(n) if (i,t) in ix]+[(pidx,-1)],-np.inf,0)
    A=coo_matrix((vals,(rows,cols)),shape=(len(lower),size)).tocsr()
    # scipy linprog usa A_ub, A_eq
    L=np.asarray(lower);U=np.asarray(upper)
    eq=np.isfinite(L)&np.isfinite(U)&(abs(L-U)<1e-8)
    ub=np.isfinite(U)&~eq
    lb=np.isfinite(L)&~eq
    A_ub=vstack([A[ub],-A[lb]],format='csr')
    b_ub=np.r_[U[ub],-L[lb]]
    c=np.zeros(size);c[pidx]=1
    bounds=[(0,cap)]*m+[(lo,hi)]*n+[(0,None)]
    lp=linprog(c,A_ub=A_ub,b_ub=b_ub,A_eq=A[eq],b_eq=U[eq],bounds=bounds,method='highs')
    if not lp.success:
        return {'lp_status':lp.message,'milp_status':'NOT_RUN'},None
    peak_lb=float(lp.x[pidx]); max_peak=peak_lb+peak_slack_kw
    # MILP: reuse LP constraints, append z binary, N integer; cap x <= cap*z;
    # sum_i z[i,t] <= N; peak <= peak_lb+slack.
    z0=size; Nidx=size+m; full=Nidx+1
    extra_r=[];extra_c=[];extra_v=[];extra_l=[];extra_u=[]
    def extra(items,l,u):
        r=len(extra_l)
        for j,v in items:
            extra_r.append(r);extra_c.append(j);extra_v.append(float(v))
        extra_l.append(l);extra_u.append(u)
    for k in range(m):extra([(k,1),(z0+k,-cap)],-np.inf,0)
    for t in range(T):
        extra([(z0+ix[i,t],1) for i in range(n) if (i,t) in ix]+[(Nidx,-1)],-np.inf,0)
    extra([(pidx,1)],-np.inf,max_peak)
    A0=csr_matrix((A.shape[0],m+1))
    M=vstack([__import__('scipy').sparse.hstack([A,A0],format='csr'),coo_matrix((extra_v,(extra_r,extra_c)),shape=(len(extra_l),full)).tocsr()],format='csr')
    obj=np.zeros(full);obj[Nidx]=1
    integrality=np.zeros(full,dtype=int);integrality[z0:z0+m]=1;integrality[Nidx]=1
    low=np.r_[np.zeros(m),np.full(n,lo),0,np.zeros(m),0]
    high=np.r_[np.full(m,cap),np.full(n,hi),np.inf,np.ones(m),n]
    res=milp(obj,integrality=integrality,bounds=Bounds(low,high),constraints=LinearConstraint(M,np.r_[L,extra_l],np.r_[U,extra_u]),options={'time_limit':float(time_limit),'mip_rel_gap':float(mip_gap)})
    summary={'lp_status':lp.message,'lp_peak_dc_kw':peak_lb,'peak_cap_dc_kw':max_peak,
             'milp_status':res.message,'milp_status_code':int(res.status),
             'milp_gap':float(res.mip_gap) if getattr(res,'mip_gap',None) is not None else None,
             'milp_dual_bound':float(res.mip_dual_bound) if getattr(res,'mip_dual_bound',None) is not None else None,
             'n_vehicles':n,'slots':T,'eligible_vehicle_slots':m}
    if res.x is None:
        return summary,None
    x=np.zeros((n,T));z=np.zeros((n,T))
    for k,(i,t) in enumerate(positions):
        x[i,t]=res.x[k];z[i,t]=res.x[z0+k]
    initial=res.x[y0:y0+n]
    soc=np.c_[initial,initial[:,None]+np.cumsum(ETA*x-traction,axis=1)]/BATTERY
    peak=float((x*60/step).sum(axis=0).max())
    ports=int(round(res.x[Nidx]))
    summary.update({'ports_incumbent':ports,'peak_dc_kw_incumbent':peak,
                    'daily_charge_dc_kwh':float(x.sum()),'daily_traction_kwh':float(traction.sum()),
                    'soc_min_observed':float(soc.min()),'soc_max_observed':float(soc.max()),
                    'max_periodic_soc_error':float(np.abs(soc[:,-1]-soc[:,0]).max()),
                    'max_energy_balance_error_kwh':float(np.abs(x.sum(axis=1)*ETA-traction.sum(axis=1)).max()),
                    'certified_port_optimum':bool(res.status==0 and (res.mip_gap is None or res.mip_gap<1e-8))})
    assert (x[~allowed]<1e-7).all()
    assert soc.min()>=SOC_MIN-1e-5 and soc.max()<=SOC_MAX+1e-5
    assert peak<=max_peak+1e-5
    assert np.max(np.abs(soc[:,-1]-soc[:,0]))<1e-5
    assert np.max((z>0.5).sum(axis=0))<=ports
    return summary,(x,z,soc)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--step-min',type=int,default=15)
    ap.add_argument('--time-limit',type=float,default=300)
    ap.add_argument('--mip-gap',type=float,default=.02)
    ap.add_argument('--peak-slack-kw',type=float,default=1.0)
    args=ap.parse_args()
    inp=ROOT/'resultados'/'servico_REV02'
    out=ROOT/'resultados'/'recarga_REV023'
    vp=inp/'veiculos_servico_24h_REV02.csv';bp=inp/'blocos_servico_24h_REV02.csv'
    v=pd.read_csv(vp);b=pd.read_csv(bp)
    vids,traction,allowed,km,pkm=build_data(v,b,args.step_min)
    summary,solution=solve_model(traction,allowed,args.step_min,args.time_limit,args.mip_gap,args.peak_slack_kw)
    summary.update({'generator':'REV023_LP_PEAK_THEN_MILP_PORTS','input_sha256':{vp.name:sha(vp),bp.name:sha(bp)},
                    'service_total_km':float(km.sum()),'service_total_pkm':float(pkm.sum()),
                    'assumptions':{'step_min':args.step_min,'battery_kwh':BATTERY,'soc_min':SOC_MIN,'soc_max':SOC_MAX,
                                   'port_dc_kw':PORT_KW,'battery_dc_efficiency':ETA,'turnaround_each_side_min':TURNAROUND,
                                   'periodic_service':True,'periodic_soc':True,'charge_only_full_eligible_slots':True,
                                   'peak_slack_kw':args.peak_slack_kw,'no_ac_pcc_pv_bess_chp':True}})
    out.mkdir(parents=True,exist_ok=True)
    if solution:
        x,z,soc=solution
        pd.DataFrame({'slot':np.arange(x.shape[1]),'start_min':np.arange(x.shape[1])*args.step_min,
                      'end_min':(np.arange(x.shape[1])+1)*args.step_min,
                      'dc_kw':x.sum(axis=0)*60/args.step_min,'ports_active':(z>.5).sum(axis=0),
                      'traction_kwh':traction.sum(axis=0),'charge_dc_kwh':x.sum(axis=0)}).to_csv(out/'agregado_15min_REV023.csv',index=False)
        active=np.argwhere((x>1e-7)|(traction>1e-7))
        pd.DataFrame([{'vehicle_id':vids[i],'slot':int(t),'start_min':int(t*args.step_min),
                       'charge_dc_kwh':float(x[i,t]),'traction_kwh':float(traction[i,t]),
                       'port_active':int(z[i,t]>.5),'soc_start':float(soc[i,t]),'soc_end':float(soc[i,t+1])}
                      for i,t in active]).to_csv(out/'veiculos_15min_REV023.csv',index=False)
    (out/'auditoria_REV023.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(summary,indent=2,ensure_ascii=False))
    if solution is None:raise SystemExit('Nenhuma solução MILP obtida: verifique status e folga do pico.')

if __name__=='__main__':main()

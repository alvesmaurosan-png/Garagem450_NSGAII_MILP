"""REV02.3a: LP, limite superior construtivo e busca MILP por portas fixas.
Nao modifica REV02.3 nem suas saidas. SciPy/HiGHS.
"""
from __future__ import annotations
import argparse, json, math, time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import linprog, milp, Bounds, LinearConstraint
from scipy.sparse import coo_matrix, hstack, vstack
from otimizar_recarga_rev023 import (ROOT, build_data, sha, BATTERY, SOC_MIN, SOC_MAX, PORT_KW, ETA, TURNAROUND)


def prepare(traction, allowed, step=15):
    n,T=traction.shape
    if allowed.shape!=(n,T) or step<=0 or 1440%step: raise ValueError('Dimensoes/step invalidos')
    if np.any(traction<0) or np.any(traction.sum(axis=1)>(SOC_MAX-SOC_MIN)*BATTERY+1e-7):
        raise ValueError('Tracao negativa ou superior a autonomia util')
    positions=np.argwhere(allowed);m=len(positions)
    if not m: raise ValueError('Sem janelas')
    ix=np.full((n,T),-1,dtype=int)
    ix[positions[:,0],positions[:,1]]=np.arange(m)
    cap=PORT_KW*step/60
    lo,hi=SOC_MIN*BATTERY,SOC_MAX*BATTERY
    y0=m;pidx=m+n;size=pidx+1
    rows=[];cols=[];vals=[];L=[];U=[]
    def add(items,l,u):
        r=len(L)
        for k,a in items:
            if a:rows.append(r);cols.append(k);vals.append(float(a))
        L.append(l);U.append(u)
    for i in range(n):
        ks=ix[i,ix[i]>=0].tolist()
        e=float(traction[i].sum())
        add([(k,1) for k in ks],e/ETA,e/ETA)
        cum=[];te=0.
        for t in range(T):
            k=ix[i,t]
            if k>=0:cum.append(int(k))
            te+=traction[i,t]
            if traction[i,t]>1e-10 or k>=0:
                add([(y0+i,1)]+[(j,ETA) for j in cum],lo+te,hi+te)
    for t in range(T):
        add([(int(ix[i,t]),60/step) for i in range(n) if ix[i,t]>=0]+[(pidx,-1)],-np.inf,0.)
    A=coo_matrix((vals,(rows,cols)),shape=(len(L),size)).tocsr()
    L=np.array(L);U=np.array(U)
    eq=np.isfinite(L)&np.isfinite(U)&(np.abs(L-U)<1e-8)
    ub=np.isfinite(U)&~eq;lb=np.isfinite(L)&~eq
    Aub=vstack([A[ub],-A[lb]],format='csr')
    bub=np.r_[U[ub],-L[lb]]
    c=np.zeros(size);c[pidx]=1
    bounds=[(0,cap)]*m+[(lo,hi)]*n+[(0,None)]
    return dict(n=n,T=T,m=m,positions=positions,ix=ix,cap=cap,y0=y0,pidx=pidx,size=size,
                A=A,L=L,U=U,Aub=Aub,bub=bub,Aeq=A[eq],beq=U[eq],c=c,bounds=bounds,
                traction=traction,allowed=allowed,step=step)


def validate(d,x,initial,peak_cap=None,port_limit=None,z=None,tol=2e-5):
    tr=d['traction'];allowed=d['allowed'];step=d['step']
    soc=np.c_[initial,initial[:,None]+np.cumsum(ETA*x-tr,axis=1)]/BATTERY
    power=x.sum(axis=0)*60/step
    active=(x>1e-6).sum(axis=0)
    err=float(np.max(np.abs(ETA*x.sum(axis=1)-tr.sum(axis=1))))
    periodic=float(np.max(np.abs(soc[:,-1]-soc[:,0])))
    violations=[]
    if np.any(x < -tol) or np.any(x > d['cap']+tol):violations.append('individual_energy_bounds')
    if np.any(x[~allowed]>tol):violations.append('outside_garage')
    if soc.min()<SOC_MIN-tol or soc.max()>SOC_MAX+tol:violations.append('soc_bounds')
    if err>tol or periodic>tol:violations.append('periodicity')
    if peak_cap is not None and power.max()>peak_cap+tol:violations.append('peak_cap')
    if port_limit is not None and active.max()>port_limit:violations.append('port_count')
    if z is not None:
        if np.max(np.abs(z-np.rint(z)))>1e-4:violations.append('noninteger_z')
        if np.any(x>d['cap']*z+tol):violations.append('link_x_z')
        if port_limit is not None and np.any(z.sum(axis=0)>port_limit+1e-4):violations.append('port_z_limit')
    return {'valid':not violations,'violations':violations,'peak_dc_kw':float(power.max()),
            'ports_from_positive_lp':int(active.max()),'soc_min':float(soc.min()),
            'soc_max':float(soc.max()),'max_energy_residual_kwh':err,
            'max_periodic_soc_residual':periodic,'daily_dc_kwh':float(x.sum())},soc


def decode(d,vec,with_z=False):
    x=np.zeros((d['n'],d['T']))
    p=d['positions'];x[p[:,0],p[:,1]]=vec[:d['m']]
    y=vec[d['y0']:d['y0']+d['n']]
    z=None
    if with_z:
        z=np.zeros_like(x);z[p[:,0],p[:,1]]=vec[d['size']:d['size']+d['m']]
    return x,y,z


def fixed_milp(d,ports,peak_cap=None,time_limit=60.,mip_gap=.02):
    m=d['m'];size=d['size'];n=d['n'];T=d['T'];ix=d['ix'];cap=d['cap']
    er=[];ec=[];ev=[];el=[];eu=[]
    def add(items,l,u):
        r=len(el)
        for k,a in items:
            if a:er.append(r);ec.append(k);ev.append(float(a))
        el.append(l);eu.append(u)
    for k in range(m):add([(k,1),(size+k,-cap)],-np.inf,0)
    for t in range(T):
        add([(size+int(ix[i,t]),1) for i in range(n) if ix[i,t]>=0],-np.inf,float(ports))
    if peak_cap is not None:add([(d['pidx'],1)],-np.inf,float(peak_cap))
    extra=coo_matrix((ev,(er,ec)),shape=(len(el),size+m)).tocsr()
    M=vstack([hstack([d['A'],coo_matrix((d['A'].shape[0],m))],format='csr'),extra],format='csr')
    lower=np.r_[np.zeros(m),np.full(n,SOC_MIN*BATTERY),0,np.zeros(m)]
    upper=np.r_[np.full(m,cap),np.full(n,SOC_MAX*BATTERY),np.inf,np.ones(m)]
    integrality=np.r_[np.zeros(size,dtype=int),np.ones(m,dtype=int)]
    # Constante objetivo zero: busca de factibilidade; nao certifica otimalidade do numero de portas.
    c=np.zeros(size+m)
    start=time.monotonic()
    res=milp(c,integrality=integrality,bounds=Bounds(lower,upper),
             constraints=LinearConstraint(M,np.r_[d['L'],el],np.r_[d['U'],eu]),
             options={'time_limit':float(time_limit),'mip_rel_gap':float(mip_gap)})
    record={'ports_tested':int(ports),'status_code':int(res.status),'solver_message':res.message,
            'elapsed_seconds':round(time.monotonic()-start,3),'peak_cap_dc_kw':peak_cap,
            'mip_gap':float(res.mip_gap) if getattr(res,'mip_gap',None) is not None else None}
    sol=None
    if res.x is not None:
        x,y,z=decode(d,res.x,True)
        audit,soc=validate(d,x,y,peak_cap,ports,z)
        record['audit']=audit
        if audit['valid']:
            record['classification']='FEASIBLE_CERTIFIED_BY_AUDIT'
            sol=(x,z,soc)
        else:record['classification']='INVALID_INCUMBENT'
    elif res.status==2:
        record['classification']='INFEASIBLE_CERTIFIED'
    else:record['classification']='INCONCLUSIVE'
    return record,sol


def run_search(d,lp_peak,lp_solution,peak_cap,seconds_per_test,max_tests,mip_gap):
    x,y,_=decode(d,lp_solution)
    audit,soc=validate(d,x,y,peak_cap)
    if not audit['valid']:raise RuntimeError('LP nao passou na auditoria: '+str(audit['violations']))
    upper=audit['ports_from_positive_lp']
    lower=math.ceil((lp_peak-1e-7)/PORT_KW)
    # O limite inferior por energia diaria e redundante aqui, mas registrado para auditoria.
    lower=max(lower,math.ceil(float(d['traction'].sum())/(d['T']*d['cap']*ETA)-1e-8))
    if lower>upper:raise RuntimeError('Limites inconsistentes')
    # O LP fornece um incumbente construtivo que respeita tambem peak_cap.
    best=(x,(x>1e-6).astype(float),soc)
    history=[];inconclusive=[];certified_infeasible_below=lower-1
    for _ in range(max_tests):
        if lower>=upper:break
        mid=(lower+upper)//2
        rec,sol=fixed_milp(d,mid,peak_cap,seconds_per_test,mip_gap)
        history.append(rec)
        if sol is not None:
            upper=mid;best=sol
        elif rec['classification']=='INFEASIBLE_CERTIFIED':
            lower=mid+1;certified_infeasible_below=max(certified_infeasible_below,mid)
        else:
            inconclusive.append(mid)
            # Sem prova, nao descartar nenhum lado; encerrar esta busca monotona.
            break
    return {'lower_bound_ports':lower,'upper_bound_ports':upper,
            'minimum_certified':bool(lower==upper),
            'classification':'CERTIFIED_MINIMUM' if lower==upper else 'BEST_KNOWN_WITH_OPEN_GAP',
            'lp_constructive_upper_ports':audit['ports_from_positive_lp'],
            'lp_constructive_audit':audit,'tests':history,
            'inconclusive_ports':inconclusive,
            'note':'Certificacao relativa ao modelo discretizado de 15 min e ao regime de pico especificado'},best


def save_solution(path,d,vids,solution,tag):
    x,z,soc=solution;T=d['T'];step=d['step']
    pd.DataFrame({'slot':np.arange(T),'start_min':np.arange(T)*step,
                  'dc_kw':x.sum(axis=0)*60/step,'charging_vehicles':(x>1e-6).sum(axis=0),
                  'energy_dc_kwh':x.sum(axis=0),'traction_kwh':d['traction'].sum(axis=0)}).to_csv(path/f'agregado_{tag}.csv',index=False)
    p=np.argwhere((x>1e-6)|(d['traction']>1e-6))
    pd.DataFrame([{'vehicle_id':vids[i],'slot':int(t),'charge_dc_kwh':float(x[i,t]),
                   'traction_kwh':float(d['traction'][i,t]),'soc_start':float(soc[i,t]),
                   'soc_end':float(soc[i,t+1]),'port_active':int(x[i,t]>1e-6)} for i,t in p]).to_csv(path/f'veiculos_{tag}.csv',index=False)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--step-min',type=int,default=15)
    ap.add_argument('--time-per-test',type=float,default=60)
    ap.add_argument('--max-tests',type=int,default=5)
    ap.add_argument('--mip-gap',type=float,default=.02)
    ap.add_argument('--peak-slack-kw',type=float,default=175)
    ap.add_argument('--regime',choices=['both','peak','free'],default='both')
    args=ap.parse_args()
    if args.time_per_test<=0 or args.max_tests<0 or args.peak_slack_kw<0:ap.error('Limites invalidos')
    inp=ROOT/'resultados'/'servico_REV02'
    vp=inp/'veiculos_servico_24h_REV02.csv';bp=inp/'blocos_servico_24h_REV02.csv'
    vehicles=pd.read_csv(vp);blocks=pd.read_csv(bp)
    vids,tr,allowed,km,pkm=build_data(vehicles,blocks,args.step_min)
    d=prepare(tr,allowed,args.step_min)
    lp=linprog(d['c'],A_ub=d['Aub'],b_ub=d['bub'],A_eq=d['Aeq'],b_eq=d['beq'],bounds=d['bounds'],method='highs')
    if not lp.success:raise RuntimeError('LP falhou: '+lp.message)
    peak=float(lp.x[d['pidx']])
    out=ROOT/'resultados'/'recarga_REV023a';out.mkdir(parents=True,exist_ok=True)
    summary={'generator':'REV023a_FIXED_PORT_FEASIBILITY_SEARCH','lp_status':lp.message,
             'lp_peak_dc_kw':peak,'n_vehicles':len(vids),'slots':d['T'],
             'eligible_vehicle_slots':d['m'],'service_total_km':float(km.sum()),
             'service_total_pkm':float(pkm.sum()),
             'input_sha256':{vp.name:sha(vp),bp.name:sha(bp)},
             'assumptions':{'step_min':args.step_min,'port_kw_dc':PORT_KW,'battery_kwh':BATTERY,
                            'soc_min':SOC_MIN,'soc_max':SOC_MAX,'eta':ETA,'turnaround_min':TURNAROUND,
                            'no_pv_bess_chp_pcc':True,'charging_only_full_slots':True}}
    x,y,_=decode(d,lp.x)
    lp_audit,soc=validate(d,x,y)
    summary['lp_audit']=lp_audit
    if not lp_audit['valid']:raise RuntimeError('LP nao validado')
    save_solution(out,d,vids,(x,(x>1e-6).astype(float),soc),'lp_REV023a')
    regimes={'peak':peak+args.peak_slack_kw,'free':None}
    for name,cap in regimes.items():
        if args.regime not in ('both',name):continue
        result,sol=run_search(d,peak,lp.x,cap,args.time_per_test,args.max_tests,args.mip_gap)
        result['peak_cap_dc_kw']=cap
        summary[name]=result
        save_solution(out,d,vids,sol,f'best_{name}_REV023a')
        (out/'auditoria_REV023a.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
        print(name,':',result['classification'],'[',result['lower_bound_ports'],',',result['upper_bound_ports'],']')
    (out/'auditoria_REV023a.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('peak','free')},indent=2,ensure_ascii=False))

if __name__=='__main__':main()

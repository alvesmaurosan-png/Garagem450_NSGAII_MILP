"""REV03.1: fixed G4 load, chronological solar, cyclic annual storage. No NSGA-II."""
import argparse, json, time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import coo_matrix


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--bess',type=float,default=60000)
    ap.add_argument('--tempo',type=float,default=300)
    ap.add_argument('--somente-lp',action='store_true')
    a=ap.parse_args()
    if not 0<=a.bess<=60000 or a.tempo<=0: ap.error('BESS deve estar entre 0 e 60000 kWh; tempo positivo')
    v=pd.read_csv('resultados/R1_REV04_G4/r1_vehicle_states_g4.csv')
    q=v.pivot(index='vehicle_id',columns='slot',values='charge_dc_kw').sort_index()
    assert q.shape==(450,96) and list(q.columns)==list(range(96)) and np.isfinite(q.to_numpy()).all()
    solar=pd.read_csv('resultados/R1_G5_1_REV01/pv_local_hourly.csv').pv_kw.to_numpy()/1625.964844738918
    assert len(solar)==8760 and np.isfinite(solar).all() and (solar>=0).all()
    d=np.tile(q.sum(axis=0).to_numpy()/0.9727,365); s=np.repeat(solar,4)*1526.58
    T=len(d); W=10; N=T*W; dt=.25; b=a.bess; pcs=min(15000,.55*b); m=15; g=1500; inf=np.inf
    # grid, PV, charge, discharge, stored energy, CHP gross, gas production, gas storage, mode, active modules
    lb=np.zeros((T,W)); ub=np.tile([2500,0,pcs,pcs,.9*b,75*m,g,8*g,1,m],(T,1)); ub[:,1]=s; lb[:,4]=.1*b
    ii=[]; jj=[]; vv=[]; lo=[]; hi=[]
    def add(z,l,h):
        r=len(lo); lo.append(l); hi.append(h)
        for j,x in z.items(): ii.append(r); jj.append(j); vv.append(x)
    for t in range(T):
        j=t*W; k=((t-1)%T)*W
        add({j:1,j+1:1,j+2:-1,j+3:1,j+5:.95},d[t],d[t])
        add({j+4:1,k+4:-1,j+2:-dt*.922,j+3:dt/.922},0,0)
        add({j+7:1,k+7:-1,j+6:-dt,j+5:dt/2.1},0,0)
        add({j+2:1,j+8:-pcs},-inf,0); add({j+3:1,j+8:pcs},-inf,pcs)
        add({j+5:1,j+9:-75},-inf,0); add({j+5:1,j+9:-37.5},0,inf)
    for day in range(365):
        add({t*W+9:1 for t in range(day*96,(day+1)*96)},0,.96*m*96)
    add({(T-1)*W+4:1},.5*b,.5*b)
    A=coo_matrix((vv,(ii,jj)),shape=(len(lo),N)).tocsc(); lo=np.array(lo); hi=np.array(hi); lb=lb.ravel(); ub=ub.ravel()
    c=np.zeros(N); c[0::W]=.8*dt; c[6::W]=.9*dt
    integ=np.zeros(N,dtype=np.uint8); integ[8::W]=1; integ[9::W]=1
    out=Path('resultados')/('R1_CRONO_REV03_'+time.strftime('%Y%m%d_%H%M%S')); out.mkdir()
    report={'bess_kwh':b,'pcs_kw':pcs,'pv_kwp':1526.58,'chp_modules':m,'pcc_kw':2500,'gas_nm3h':g,'demand_kwh':float(d.sum()*dt),'pv_available_kwh':float(s.sum()*dt),'natureza':'ANO SOLAR SINTETICO, DIA G4 REPETIDO; SEM CERTIFICACAO REAL','runs':[]}
    for name,integer in [('LP',np.zeros(N,dtype=np.uint8)),('MILP',integ)]:
        if name=='MILP' and (a.somente_lp or report['runs'][0]['status']==2): break
        print(name,'iniciado',flush=True)
        res=milp(c,integrality=integer,bounds=Bounds(lb,ub),constraints=LinearConstraint(A,lo,hi),options={'time_limit':a.tempo,'mip_rel_gap':.02})
        rec={'model':name,'status':int(res.status),'message':str(res.message),'valid_incumbent':False}
        if res.x is not None:
            z=res.x; y=A@z; mask=integer>0
            err=max(float(np.max(lo-y)),float(np.max(y-hi)),float(np.max(lb-z)),float(np.max(z-ub)),float(np.max(abs(z[mask]-np.round(z[mask])))) if mask.any() else 0)
            rec['max_violation']=err; rec['valid_incumbent']=bool(err<=1e-4)
            if rec['valid_incumbent']:
                df=pd.DataFrame(z.reshape(T,W),columns=['grid_kw','pv_kw','charge_kw','discharge_kw','bess_kwh','chp_gross_kw','gas_prod_nm3h','gas_store_nm3','bess_mode','chp_active']); df['demand_kw']=d
                df.to_csv(out/f'despacho_{name}.csv',index=False)
                rec.update(grid_kwh=float(df.grid_kw.sum()*dt),peak_kw=float(df.grid_kw.max()),pv_kwh=float(df.pv_kw.sum()*dt),chp_net_kwh=float(df.chp_gross_kw.sum()*dt*.95),substrate_t=float(df.gas_prod_nm3h.sum()*dt/100),soc_min_kwh=float(df.bess_kwh.min()),soc_max_kwh=float(df.bess_kwh.max()))
        report['runs'].append(rec); (out/'diagnostico.json').write_text(json.dumps(report,indent=2),encoding='utf-8'); print(json.dumps(rec,indent=2),flush=True)
    print(out,flush=True)

if __name__=='__main__': main()

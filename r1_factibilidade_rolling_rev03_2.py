"""REV03.2: annual LP reference + rolling integer dispatch + independent annual audit."""
import argparse, json, time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import coo_matrix

COLS=['grid_kw','pv_kw','charge_kw','discharge_kw','bess_kwh','chp_gross_kw','gas_prod_nm3h','gas_store_nm3','bess_mode','chp_active']
DT=.25; W=10; LIMIT=1382; TOL=1e-4

def solve(d,s,b,tempo,integer=False,initial=None,target=None,exact=False):
    T=len(d); pcs=min(15000,.55*b); inf=np.inf
    lb=np.zeros((T,W)); ub=np.tile([2500,0,pcs,pcs,.9*b,1125,1500,12000,1,15],(T,1)); ub[:,1]=s; lb[:,4]=.1*b
    ii=[]; jj=[]; vv=[]; lo=[]; hi=[]
    def add(z,l,h):
        r=len(lo); lo.append(l); hi.append(h)
        for j,x in z.items(): ii.append(r); jj.append(j); vv.append(x)
    for t in range(T):
        j=t*W; k=((t-1)%T)*W
        add({j:1,j+1:1,j+2:-1,j+3:1,j+5:.95},d[t],d[t])
        for col,terms,ix in [(4,{j+2:-DT*.922,j+3:DT/.922},0),(7,{j+6:-DT,j+5:DT/2.1},1)]:
            z={j+col:1,**terms}
            if t==0 and initial is not None: rhs=initial[ix]
            else: z[k+col]=-1; rhs=0
            add(z,rhs,rhs)
        add({j+2:1,j+8:-pcs},-inf,0); add({j+3:1,j+8:pcs},-inf,pcs)
        add({j+5:1,j+9:-75},-inf,0); add({j+5:1,j+9:-37.5},0,inf)
    for day in range(T//96): add({t*W+9:1 for t in range(day*96,(day+1)*96)},0,LIMIT)
    if initial is None: add({(T-1)*W+4:1},.5*b,.5*b)
    elif target is not None:
        for col,val in zip((4,7),target): add({(T-1)*W+col:1},val,val if exact else inf)
    A=coo_matrix((vv,(ii,jj)),shape=(len(lo),T*W)).tocsc(); lo=np.array(lo); hi=np.array(hi); lb=lb.ravel(); ub=ub.ravel()
    c=np.zeros(T*W); c[0::W]=.8*DT; c[6::W]=.9*DT
    integ=np.zeros(T*W,dtype=np.uint8)
    if integer: integ[8::W]=1; integ[9::W]=1
    res=milp(c,integrality=integ,bounds=Bounds(lb,ub),constraints=LinearConstraint(A,lo,hi),options={'time_limit':tempo,'mip_rel_gap':.02})
    rec={'status':int(res.status),'message':str(res.message),'valid_incumbent':False}
    if res.x is None: return None,rec
    z=res.x; y=A@z; mask=integ>0
    err=max(0.,float(np.max(lo-y)),float(np.max(y-hi)),float(np.max(lb-z)),float(np.max(z-ub)),float(np.max(abs(z[mask]-np.round(z[mask])))) if mask.any() else 0.)
    rec.update(max_violation=err,valid_incumbent=bool(err<=TOL))
    return (z.reshape(T,W) if err<=TOL else None),rec

def audit(z,d,s,b,initial):
    grid,pv,ch,dis,e,chp,g,v,mode,n=z.T; pcs=min(15000,.55*b)
    prev_e=np.r_[initial[0],e[:-1]]; prev_v=np.r_[initial[1],v[:-1]]
    def mx(x): return float(np.max(np.abs(x)))
    def pos(x): return max(0.,float(np.max(x)))
    errors={'power_balance':mx(grid+pv-ch+dis+.95*chp-d),'bess_balance':mx(e-prev_e-DT*.922*ch+DT/.922*dis),'gas_balance':mx(v-prev_v-DT*g+DT*chp/2.1),'bounds':max(pos(-z),pos(grid-2500),pos(pv-s),pos(ch-pcs),pos(dis-pcs),pos(.1*b-e),pos(e-.9*b),pos(g-1500),pos(v-12000),pos(mode-1),pos(n-15),pos(chp-1125)),'integer':max(mx(mode-np.round(mode)),mx(n-np.round(n))),'bess_mode':max(pos(ch-pcs*mode),pos(dis-pcs*(1-mode)),mx(np.minimum(ch,dis))),'chp_limits':max(pos(chp-75*n),pos(37.5*n-chp)),'availability':pos(n.reshape(-1,96).sum(axis=1)-LIMIT),'annual_closure':max(abs(e[-1]-initial[0]),abs(v[-1]-initial[1]),abs(initial[0]-.5*b))}
    return {'valid_incumbent':max(errors.values())<=TOL,'errors':errors,'grid_kwh':float(grid.sum()*DT),'peak_kw':float(grid.max()),'pv_kwh':float(pv.sum()*DT),'chp_net_kwh':float(chp.sum()*DT*.95),'substrate_t':float(g.sum()*DT/100),'soc_min_kwh':float(e.min()),'soc_max_kwh':float(e.max()),'demand_kwh':float(d.sum()*DT)}

def main():
    p=argparse.ArgumentParser(); p.add_argument('--bess',type=float,default=60000); p.add_argument('--tempo',type=float,default=30); p.add_argument('--tempo-lp',type=float,default=300); a=p.parse_args(); b=a.bess
    if not 0<b<=60000 or min(a.tempo,a.tempo_lp)<=0: p.error('parametros invalidos')
    v=pd.read_csv('resultados/R1_REV04_G4/r1_vehicle_states_g4.csv'); q=v.pivot(index='vehicle_id',columns='slot',values='charge_dc_kw').sort_index(); assert q.shape==(450,96) and list(q.columns)==list(range(96)) and np.isfinite(q.to_numpy()).all() and (q.to_numpy()>=0).all()
    solar=pd.read_csv('resultados/R1_G5_1_REV01/pv_local_hourly.csv').pv_kw.to_numpy()/1625.964844738918; assert len(solar)==8760 and np.isfinite(solar).all() and (solar>=0).all()
    d=np.tile(q.sum(axis=0).to_numpy()/0.9727,365); s=np.repeat(solar,4)*1526.58
    out=Path('resultados')/('R1_ROLLING_REV03_2_'+time.strftime('%Y%m%d_%H%M%S')); out.mkdir(); report={'bess_kwh':b,'pcs_kw':min(15000,.55*b),'pv_kwp':1526.58,'chp_modules':15,'daily_module_slots':LIMIT,'windows':[],'valid_incumbent':False}
    def save(): (out/'diagnostico.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('LP anual iniciado',flush=True); ref,rec=solve(d,s,b,a.tempo_lp); report['LP']=rec; save(); print(rec,flush=True)
    if ref is None: print(out); return
    pd.DataFrame(ref,columns=COLS).to_csv(out/'referencia_LP.csv',index=False)
    initial=ref[-1,[4,7]].copy(); state=initial.copy(); chunks=[]; start=0; T=len(d)
    while start<T:
        end=min(T,start+7*96); commit=min(end,start+3*96) if end<T else T
        target=initial if end==T else ref[end-1,[4,7]]
        z,rec=solve(d[start:end],s[start:end],b,a.tempo,True,state,target,end==T)
        rec.update(start_day=start//96+1,end_day=end//96,committed_days=(commit-start)//96 if z is not None else 0); report['windows'].append(rec); save(); print(json.dumps(rec),flush=True)
        if z is None:
            report['conclusion']='ROLLING_INCONCLUSIVO: janela sem incumbente valido; nao prova inviabilidade anual'; save(); print(out); return
        part=z[:commit-start]; chunks.append(part); state=part[-1,[4,7]].copy(); start=commit
        df=pd.DataFrame(np.concatenate(chunks),columns=COLS); df['demand_kw']=d[:start]; df.to_csv(out/'despacho_parcial.csv',index=False)
    z=np.concatenate(chunks); result=audit(z,d,s,b,initial); report.update(result); report['conclusion']='FACTIVEL_ANUAL_SINTETICO' if result['valid_incumbent'] else 'FALHA_AUDITORIA'; save(); df.to_csv(out/'despacho_anual.csv',index=False); print(json.dumps(result,indent=2),flush=True); print(out,flush=True)

if __name__=='__main__': main()

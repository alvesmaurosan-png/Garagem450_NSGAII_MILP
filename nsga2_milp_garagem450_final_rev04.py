"""REV03.2: annual LP reference + rolling integer dispatch + independent annual audit."""
import argparse, json, time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import coo_matrix

COLS=['grid_kw','pv_kw','charge_kw','discharge_kw','bess_kwh','chp_gross_kw','gas_prod_nm3h','gas_store_nm3','bess_mode','chp_active']
DT=.25; W=10; LIMIT=1382; TOL=1e-4

def solve(d,s,b,tempo,integer=False,initial=None,target=None,exact=False,*,pcs,m,gmax,eps):
    T=len(d); inf=np.inf
    lb=np.zeros((T,W)); ub=np.tile([eps,0,pcs,pcs,.9*b,75*m,gmax,8*gmax,1,m],(T,1)); ub[:,1]=s; lb[:,4]=.1*b
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
    for day in range(T//96): add({t*W+9:1 for t in range(day*96,(day+1)*96)},0,int(np.floor(.96*m*96)))
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

def audit(z,d,s,b,initial,*,pcs,m,gmax,eps):
    grid,pv,ch,dis,e,chp,g,v,mode,n=z.T
    prev_e=np.r_[initial[0],e[:-1]]; prev_v=np.r_[initial[1],v[:-1]]
    def mx(x): return float(np.max(np.abs(x)))
    def pos(x): return max(0.,float(np.max(x)))
    errors={'power_balance':mx(grid+pv-ch+dis+.95*chp-d),'bess_balance':mx(e-prev_e-DT*.922*ch+DT/.922*dis),'gas_balance':mx(v-prev_v-DT*g+DT*chp/2.1),'bounds':max(pos(-z),pos(grid-eps),pos(pv-s),pos(ch-pcs),pos(dis-pcs),pos(.1*b-e),pos(e-.9*b),pos(g-gmax),pos(v-8*gmax),pos(mode-1),pos(n-m),pos(chp-75*m)),'integer':max(mx(mode-np.round(mode)),mx(n-np.round(n))),'bess_mode':max(pos(ch-pcs*mode),pos(dis-pcs*(1-mode)),mx(np.minimum(ch,dis))),'chp_limits':max(pos(chp-75*n),pos(37.5*n-chp)),'availability':pos(n.reshape(-1,96).sum(axis=1)-int(np.floor(.96*m*96))),'annual_closure':max(abs(e[-1]-initial[0]),abs(v[-1]-initial[1]),abs(initial[0]-.5*b))}
    return {'valid_incumbent':max(errors.values())<=TOL,'errors':errors,'grid_kwh':float(grid.sum()*DT),'peak_kw':float(grid.max()),'pv_kwh':float(pv.sum()*DT),'chp_net_kwh':float(chp.sum()*DT*.95),'substrate_t':float(g.sum()*DT/100),'soc_min_kwh':float(e.min()),'soc_max_kwh':float(e.max()),'demand_kwh':float(d.sum()*DT)}


def fronts(vals):
    v=np.asarray(vals); dom=np.all(v[:,None]<=v[None,:],axis=2)&np.any(v[:,None]<v[None,:],axis=2)
    count=dom.sum(axis=0); layers=[]
    while np.any(count==0):
        f=np.flatnonzero(count==0); layers.append(f.tolist()); count[f]=-1; count-=dom[f].sum(axis=0)
    return layers

def crowd(f,vals):
    v=np.asarray(vals); c={i:0. for i in f}
    for k in range(v.shape[1]):
        order=sorted(f,key=lambda i:v[i,k]); span=v[order[-1],k]-v[order[0],k]
        if span<=0: continue
        c[order[0]]=c[order[-1]]=np.inf
        for j in range(1,len(order)-1): c[order[j]]+=(v[order[j+1],k]-v[order[j-1],k])/span
    return c

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--pop',type=int,default=24); ap.add_argument('--geracoes',type=int,default=20); ap.add_argument('--seed',type=int,default=42); ap.add_argument('--tempo-lp',type=float,default=120); ap.add_argument('--tempo',type=float,default=30); ap.add_argument('--validar',type=int,default=8); a=ap.parse_args()
    if a.pop<4 or a.geracoes<0 or a.validar<4 or min(a.tempo,a.tempo_lp)<=0: ap.error('parametros invalidos')
    p=json.loads(Path('premissas_sinteticas_rev01.json').read_text(encoding='utf-8-sig')); v=pd.read_csv('resultados/R1_REV04_G4/r1_vehicle_states_g4.csv'); q=v.pivot(index='vehicle_id',columns='slot',values='charge_dc_kw').sort_index(); occ=v.pivot(index='vehicle_id',columns='slot',values='occupied').reindex(q.index)
    assert q.shape==(450,96) and list(q.columns)==list(range(96)) and np.isfinite(q.to_numpy()).all() and (q.to_numpy()>=0).all() and np.isfinite(occ.to_numpy()).all()
    solar=pd.read_csv('resultados/R1_G5_1_REV01/pv_local_hourly.csv').pv_kw.to_numpy()/1625.964844738918; assert len(solar)==8760 and np.isfinite(solar).all() and (solar>=0).all()
    d=np.tile(q.sum(axis=0).to_numpy()/.9727,365); sun=np.repeat(solar,4); ports=int((occ.to_numpy()>.5).sum(axis=0).max()); dc=float(q.to_numpy().sum()*DT*365)
    D=lambda t:(1+p['taxa_real'])**(-t); af=sum(D(t) for t in range(1,21)); den=p['pkm_anual_requisito']*af
    out=Path('resultados')/('NSGAII_FINAL_REV04_'+time.strftime('%Y%m%d_%H%M%S')); out.mkdir(); rng=np.random.default_rng(a.seed)
    low=np.array([0,3750,0,0,0,0.]); high=np.array([1526.58,60000,15000,15,1500,2500.]); cache={}; records=[]; verified=[]
    def repair(x):
        x=np.round(np.clip(x,low,high),5); x[3]=round(x[3]); x[2]=min(x[2],.55*x[1]); return x
    def params(x): return dict(pcs=float(x[2]),m=int(x[3]),gmax=float(x[4]),eps=float(x[5]))
    def economics(x,z):
        pv,b,pcs,m,g,eps=x; totals=z.sum(axis=0)*DT; peak=float(z[:,0].max()); sub=totals[6]/100
        P=pv*4000; B=b*1500; C=pcs*900; H=m*75*8000; G=g*(24*365/100*500+1000); S=8*g*1500; ch=ports*250000
        cap=P+B+C+H+G+S+ch+p['capex_instalacao_conexao_brl']; op=totals[0]*.8+peak*360+P*.015+(B+C)*.025+ch*.02+G*.05+H*.04+S*.02+sub*90
        ve=cap+op*af+P*.15*D(12)+B*.6*D(12)+C*D(15)+H*.25*D(10)-(P+B+C+ch)*.1*D(20)
        fleet=4.5*p['custo_aquisicao_100_bev_brl']; maint=4.5*p['custo_manutencao_bev_anual_brl']; vf=fleet+maint*af+4.5*((p['custo_reposicao_100_bev_brl']-p['credito_residual_bev_brl'])*D(10)-p['credito_residual_bev_brl']*D(20))
        return dict(config='R1',n_bev=450,n_diesel=0,n_gas=0,pv_kwp=pv,bess_kwh=b,pcs_kw=pcs,chp_modules=int(m),gas_production_nm3h=g,gas_storage_nm3=8*g,pcc_target=eps,ports=ports,F1=(ve+vf)/den,F2=peak,LCOE=ve/(dc*af),VP_total=ve+vf,VP_frota=vf,VP_eletrico_tracao=ve,CAPEX=cap+fleet,OPEX=op+maint,grid_kwh=totals[0],pv_kwh=totals[1],chp_net_kwh=.95*totals[5],substrate_t=sub,charge_dc_kwh=dc,perdas_eletricas_kwh=totals[0]+totals[1]+.95*totals[5]-d.sum()*DT,CO2_operacional_t_ano=totals[0]*.1/1000,CO2_g_PKM=totals[0]*100/p['pkm_anual_requisito'])
    def ev(x):
        key=tuple(x)
        if key in cache:return cache[key]
        pv,b,pcs,m,g,eps=x; supply=eps*8760+sun.sum()*DT*pv+min(75*int(np.floor(.96*m*96))*365*DT,2.1*g*8760)*.95; deficit=max(0.,d.sum()*DT-supply)
        rec={'id':len(records),'x':list(map(float,x)),'status':'FILTRO_ENERGIA','deficit_kwh':float(deficit)}; r=None
        if deficit<=TOL:
            z,info=solve(d,sun*pv,b,a.tempo_lp,**params(x)); rec.update(info); rec['status']='LP_VALIDO' if z is not None else ('LP_INVIAVEL' if info['status']==2 else 'LP_INCONCLUSIVO')
            if z is not None:r=economics(x,z);rec.update(r)
        records.append(rec); cache[key]=r; print('avaliacao',rec['id'],rec['status'],flush=True); return r
    seeds=[repair(np.array([1526.58,b,min(15000,.55*b),15,1500,2500])) for b in (7500,15000,30000,60000)]
    pop=seeds+[repair(rng.uniform(low,high)) for _ in range(a.pop-4)]
    def rank(pool):
        vals=[(r['F1'],r['F2']) if (r:=ev(x)) is not None else (1e9,1e9) for x in pool]; layers=fronts(vals); ranks={i:k for k,f in enumerate(layers) for i in f}; cd={i:c for f in layers for i,c in crowd(f,vals).items()}; return layers,ranks,cd
    for gen in range(a.geracoes+1):
        layers,ranks,cd=rank(pop); pd.DataFrame(records).to_csv(out/'avaliacoes_LP.csv',index=False); print('geracao',gen,'LP validos',sum(r is not None for r in cache.values()),flush=True)
        if gen==a.geracoes:break
        def tournament():
            i,j=rng.integers(len(pop),size=2);return pop[min((i,j),key=lambda k:(ranks[k],-cd[k]))]
        children=[]
        for _ in range(a.pop):
            u,w=tournament(),tournament(); alpha=rng.random(6); children.append(repair(alpha*u+(1-alpha)*w+rng.normal(0,.08,6)*(high-low)*(rng.random(6)<.35)))
        pool=pop+children; layers,_,cd=rank(pool);pop=[pool[i] for f in layers for i in sorted(f,key=lambda i:cd[i],reverse=True)][:a.pop]
    good=[(np.array(k),r) for k,r in cache.items() if r is not None]; vals=[(r['F1'],r['F2']) for _,r in good]; layers=fronts(vals) if good else []; front=layers[0] if layers else []; pd.DataFrame([good[i][1] for i in front]).to_csv(out/'pareto_LP.csv',index=False)
    chosen=list(seeds); seen={tuple(x) for x in chosen}
    for f in layers:
        order=sorted(f,key=lambda i:vals[i][0]); picks=[order[0],order[-1]]+sorted(f,key=lambda i:crowd(f,vals)[i],reverse=True)
        for i in picks:
            x=good[i][0]
            if tuple(x) not in seen and len(chosen)<a.validar:chosen.append(x);seen.add(tuple(x))
        if len(chosen)>=a.validar:break
    validation=[]
    for i,x in enumerate(chosen):
        pv,b,*_=x; kw=params(x); s=sun*pv; ref,info=solve(d,s,b,a.tempo_lp,**kw); log={'id':i,'x':x.tolist(),'LP':info,'windows':[],'valid_incumbent':False}; validation.append(log)
        def save(): (out/'validacao.json').write_text(json.dumps(validation,indent=2),encoding='utf-8')
        save()
        if ref is None:continue
        initial=ref[-1,[4,7]].copy(); state=initial.copy(); chunks=[]; start=0
        while start<len(d):
            end=min(len(d),start+672); commit=min(end,start+288) if end<len(d) else end; target=initial if end==len(d) else ref[end-1,[4,7]]
            z,info=solve(d[start:end],s[start:end],b,a.tempo,True,state,target,end==len(d),**kw); info['start_day']=start//96+1;log['windows'].append(info);save();print('MILP',i,info['start_day'],info['valid_incumbent'],flush=True)
            if z is None:break
            part=z[:commit-start];chunks.append(part);state=part[-1,[4,7]].copy();start=commit
        if start!=len(d):log['conclusion']='INCONCLUSIVO';save();continue
        z=np.concatenate(chunks); result=audit(z,d,s,b,initial,**kw);log.update(result);save()
        if result['valid_incumbent']:
            r=economics(x,z);r['id_validacao']=i;verified.append(r);df=pd.DataFrame(z,columns=COLS);df['demand_kw']=d;df.to_csv(out/f'despacho_{i}.csv',index=False);pd.DataFrame(verified).to_csv(out/'avaliacoes_MILP.csv',index=False)
    if verified:
        f=fronts([(r['F1'],r['F2']) for r in verified])[0]; df=pd.DataFrame([verified[i] for i in f]).sort_values('F1');df.to_csv(out/'pareto_R1.csv',index=False); z=df[['F1','F2']].to_numpy();z=(z-z.min(0))/np.maximum(np.ptp(z,axis=0),1e-12); k=int(np.linalg.norm(z,axis=1).argmin());pd.DataFrame([dict(df.iloc[j],solucao=label) for label,j in [('min_F1',0),('min_F2',len(df)-1),('compromisso_ideal',k)]]).to_csv(out/'solucoes_representativas.csv',index=False)
    print(out,flush=True)

if __name__=='__main__':main()

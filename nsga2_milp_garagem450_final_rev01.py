import argparse,json,math,time
from pathlib import Path
import numpy as np,pandas as pd
from scipy.optimize import milp,Bounds,LinearConstraint
from scipy.sparse import lil_matrix
from nsga2_milp_exploratorio_rev03 import fronts,crowd

def main():
 a=argparse.ArgumentParser();a.add_argument('--pop',type=int,default=24);a.add_argument('--geracoes',type=int,default=20);a.add_argument('--seed',type=int,default=42);a.add_argument('--tempo',type=float,default=3);a.add_argument('--gas-station-capex',type=float,required=True);a.add_argument('--gas-maint-km',type=float,default=2.3);a.add_argument('--gas-compression',type=float,required=True);a=a.parse_args()
 p=json.loads(Path('premissas_sinteticas_rev01.json').read_text(encoding='utf-8-sig')); v=pd.read_csv('resultados/R1_REV04_G4/r1_vehicle_states_g4.csv'); solar=pd.read_csv('resultados/R1_G5_1_REV01/pv_local_hourly.csv').pv_kw.to_numpy()/1625.964844738918
 assert len(solar)==8760 and len(v)==43200
 q=v.pivot(index='vehicle_id',columns='slot',values='charge_dc_kw').sort_index(); tr=v.pivot(index='vehicle_id',columns='slot',values='traction_kwh').reindex(q.index); occ=v.pivot(index='vehicle_id',columns='slot',values='occupied').reindex(q.index)
 load=np.vstack([np.zeros(96),np.cumsum(q.to_numpy(),axis=0)])/0.9727; km=np.r_[0,np.cumsum(tr.sum(axis=1).to_numpy()/1.23)]*365; ports=np.r_[0,np.max(np.cumsum(occ.to_numpy()>0.5,axis=0),axis=1)]
 days=solar.reshape(365,24); order=np.argsort(days.sum(axis=1)); groups=np.array_split(order,4); profiles=[(np.repeat(days[g].mean(axis=0),4),len(g)) for g in groups]; profiles.append((np.repeat(days[order[0]],4),0))
 dt=.25; T=96; W=10; N=T*W; inf=np.inf
 # grid,pv,charge,discharge,soc,chp,gasprod,gassoc,bessmode,chpactive
 def dispatch(d,s,x):
  pv,b,pcs,m,g,eps=x; P=75*m; G=8*g; rows=[]; lo=[]; hi=[]; lb=np.zeros(N);ub=np.zeros(N); c=np.zeros(N); integ=np.zeros(N,int)
  def add(z,l,h):rows.append(z);lo.append(l);hi.append(h)
  for t in range(T):
   j=t*W;k=((t-1)%T)*W; ub[j:j+W]=[eps,s[t]*pv,pcs,pcs,.9*b,P,g,G,1,m];lb[j+4]=.1*b;integ[j+8:j+10]=1;c[j]=.8*dt;c[j+6]=.9*dt
   add({j:1,j+1:1,j+2:-1,j+3:1,j+5:.95},d[t],d[t]);add({j+4:1,k+4:-1,j+2:-dt*.922,j+3:dt/.922},0,0);add({j+7:1,k+7:-1,j+6:-dt,j+5:dt/2.1},0,0);add({j+2:1,j+8:-pcs},-inf,0);add({j+3:1,j+8:pcs},-inf,pcs);add({j+5:1,j+9:-75},-inf,0);add({j+5:1,j+9:-37.5},0,inf)
  add({t*W+9:1 for t in range(T)},0,.96*m*T);add({95*W+4:1},.5*b,.5*b)
  A=lil_matrix((len(rows),N));
  for i,r in enumerate(rows):
   for j,z in r.items():A[i,j]=z
  A=A.tocsr();res=milp(c,integrality=integ,bounds=Bounds(lb,ub),constraints=LinearConstraint(A,lo,hi),options={'time_limit':a.tempo,'mip_rel_gap':.02})
  if res.x is None:return None
  z=res.x;y=A@z
  if max(np.max(np.asarray(lo)-y),np.max(y-np.asarray(hi)),np.max(lb-z),np.max(z-ub),np.max(abs(z[integ>0]-np.round(z[integ>0]))))>1e-4:return None
  return z.reshape(T,W)
 disc=lambda t:(1+p['taxa_real'])**(-t); af=sum(disc(t) for t in range(1,21)); denom=p['pkm_anual_requisito']*af
 def evaluate(sc,x):
  n,pv,b,pcs,m,g,eps=x; n=int(n);m=int(m);nd=450-n if sc=='R0' else 0;ng=450-n if sc=='R2' else 0; gas=(km[-1]-km[n])*.6 if ng else 0;d=load[n]+gas/365/24*a.gas_compression; total=np.zeros(10);peak=0
  for s,w in profiles:
   z=dispatch(d,s,(pv,b,pcs,m,g,eps))
   if z is None:return None
   total+=z.sum(axis=0)*dt*w;peak=max(peak,z[:,0].max())
  cap=pv*4000+b*1500+pcs*900+ports[n]*250000; bio=g*24*365/100*500+g*1000; chp=m*75*8000; store=8*g*1500; station=a.gas_station_capex if ng else 0; ec=cap+bio+chp+store+station+p['capex_instalacao_conexao_brl']; op=total[0]*.8+peak*360+cap*.02+bio*.05+chp*.04+store*.02+total[6]*.9+station*.02; ve=ec+op*af+chp*.25*disc(10)-cap*.1*disc(20); fuel=nd/350*p['custo_diesel_combustivel_anual_brl']+gas*3.1; vf=n/100*p['custo_aquisicao_100_bev_brl']+nd/350*p['valor_oportunidade_350_diesel_brl']+ng*1500000; maint=n/100*p['custo_manutencao_bev_anual_brl']+nd/350*p['custo_manutencao_diesel_anual_brl']+(km[-1]-km[n])*a.gas_maint_km*(ng>0); fleet0=vf;vf+=maint*af+nd/350*p['custo_reposicao_350_diesel_brl']*(disc(6)+disc(18))+n/100*((p['custo_reposicao_100_bev_brl']-p['credito_residual_bev_brl'])*disc(10)-p['credito_residual_bev_brl']*disc(20))+ng*1500000*(disc(12)-4/12*disc(20)); energy=ve+fuel*af
  return dict(config=sc,n_bev=n,n_diesel=nd,n_gas=ng,pv_kwp=pv,bess_kwh=b,pcs_kw=pcs,chp_modules=m,gas_production_nm3h=g,gas_storage_nm3=8*g,pcc_target=eps,ports=int(ports[n]),f1=(energy+vf)/denom,f2=peak,lcoe=ve/(d.sum()*dt*365*af) if d.sum()>0 else None,vp_energy=energy,vp_fleet=vf,vp_total=energy+vf,capex_energy=ec,capex_fleet=fleet0,opex_annual=op+fuel+maint,grid_kwh=total[0],pv_kwh=total[1],chp_net_kwh=.95*total[5],substrate_t=total[6]/100,gas_bus_nm3=gas,charge_dc_kwh=q.iloc[:n].to_numpy().sum()*dt*365)
 out=Path('resultados')/('NSGAII_FINAL_REV01_'+time.strftime('%Y%m%d_%H%M%S'));out.mkdir(); reps=[]
 for sc in ['R0','R1','R2']:
  rng=np.random.default_rng(a.seed);low=np.array([1,0,0,0,0,0,100.]);high=np.array([450,1526.58,60000,15000,60,1500,2500.]);cache={}
  def repair(x):
   x=np.clip(x,low,high);x[0]=round(x[0]);x[4]=round(x[4]);x[3]=min(x[3],.55*x[2]);
   if sc=='R0':x[4:6]=0
   if sc=='R1':x[0]=450
   if x[4]==0:x[5]=0
   return x
  def ev(x):
   x=repair(x);k=tuple(np.round(x,5));
   if k not in cache:cache[k]=evaluate(sc,x)
   return cache[k]
  # R0: search maximum feasible prefix at generous assets, then fix fleet for Pareto.
  if sc=='R0':
   l,h=1,450;best=0
   while l<=h:
    mid=(l+h)//2;x=np.array([mid,1526.58,60000,15000,0,0,2500.]);r=ev(x)
    if r is not None:best=mid;l=mid+1
    else:h=mid-1
   if not best:raise RuntimeError('R0 sem candidato factivel encontrado')
   low[0]=high[0]=best;cache.clear();print('R0 BEV prefixo encontrado',best,flush=True)
  pop=[repair(np.array([high[0],1526.58,40000,12000,30,750,2500.])),repair(high.copy())]+[repair(rng.uniform(low,high)) for _ in range(a.pop-2)]
  def ranks(pool):
   vals=[(r['f1'],r['f2']) if (r:=ev(x)) else (1e9,1e9) for x in pool]; layers=fronts(vals);rank={};cd={}
   for i,f in enumerate(layers):rank.update({j:i for j in f});cd.update(crowd(f,vals))
   return layers,rank,cd
  for gen in range(a.geracoes+1):
   layers,rank,cd=ranks(pop); good=[r for r in cache.values() if r];pd.DataFrame(good).to_csv(out/f'avaliacoes_{sc}.csv',index=False);print(sc,gen,'avaliados',len(cache),'factíveis',len(good),flush=True)
   if gen==a.geracoes:break
   def tournament():
    i,j=rng.integers(len(pop),size=2);return pop[min([i,j],key=lambda k:(rank[k],-cd[k]))]
   children=[]
   for _ in range(a.pop):
    u,v=tournament(),tournament();alpha=rng.random(7);children.append(repair(alpha*u+(1-alpha)*v+rng.normal(0,.08,7)*(high-low)*(rng.random(7)<.35)))
   pool=pop+children;layers,rank,cd=ranks(pool);pop=[pool[j] for f in layers for j in sorted(f,key=lambda k:cd[k],reverse=True)][:a.pop]
  good=[r for r in cache.values() if r];
  if not good:print(sc,'SEM SOLUCOES',flush=True);continue
  f=[good[i] for i in fronts([(r['f1'],r['f2']) for r in good])[0]];df=pd.DataFrame(f).sort_values('f1');df.to_csv(out/f'pareto_{sc}.csv',index=False);z=df[['f1','f2']].to_numpy();z=(z-z.min(0))/np.maximum(z.ptp(0) if hasattr(z,'ptp') and np.__version__.startswith('1.') else np.ptp(z,axis=0),1e-12)
  for label,i in [('min_F1',0),('min_F2',int(z[:,1].argmin())),('compromisso_ideal',int(np.linalg.norm(z,axis=1).argmin()))]:reps.append(dict(df.iloc[i],solution=label))
 pd.DataFrame(reps).to_csv(out/'solucoes_representativas.csv',index=False);print(out)
if __name__=='__main__':main()

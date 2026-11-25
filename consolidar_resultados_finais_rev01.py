"""Pos-processamento exploratorio; nao executa MILP nem NSGA-II."""
from pathlib import Path
import json, numpy as np, pandas as pd
from datetime import datetime
R=Path('resultados'); p=json.loads(Path('premissas_sinteticas_rev01.json').read_text(encoding='utf-8-sig'))
a=json.loads((R/'bau_REV032/auditoria_REV032.json').read_text(encoding='utf-8-sig'))['physical']
rate=p['taxa_real']; D=lambda t:(1+rate)**(-t); af=sum(D(t) for t in range(1,21)); den=p['pkm_anual_requisito']*af
out=R/('CONSOLIDADO_FINAL_REV01_'+datetime.now().strftime('%Y%m%d_%H%M%S'));out.mkdir()
v=pd.read_csv(R/'R1_REV04_G4/r1_vehicle_states_g4.csv'); km=v.groupby('vehicle_id').traction_kwh.sum().sort_index().cumsum()*365/1.23
km=np.r_[0,km.to_numpy()]
# Common exploratory cost conventions; retain original values separately.
def calc(r):
 n=int(r.n_bev); nd=int(r.n_diesel); ng=int(r.n_gas); pv=r.pv_kwp*4000; b=r.bess_kwh*1500; pcs=r.pcs_kw*900; ch=r.ports*250000; bio=r.gas_production_nm3h*(24*365/100*500+1000); c=r.chp_modules*75*8000; st=r.gas_storage_nm3*1500; gs=5000000 if ng else 0
 conn=r.connection_cost if 'connection_cost' in r else p['capex_instalacao_conexao_brl']; cap=pv+b+pcs+ch+bio+c+st+conn; op=r.grid_kwh*.8+r.f2*360+pv*.015+(b+pcs)*.025+ch*.02+bio*.05+c*.04+st*.02+r.substrate_t*90
 # proportional allocation of shared electric supply to traction vs compression
 ac=r.charge_dc_kwh/(.95 if r.config=='BAU' else .9727); comp=r.gas_bus_nm3*.25; share=ac/(ac+comp) if ac+comp else 0
 ve=cap+op*af+pv*.15*D(12)+b*.6*D(12)+pcs*D(15)+c*.25*D(10)-(pv+b+pcs+ch)*.1*D(20)
 gasinfra=gs*(1+.02*af); otherkm=km[-1]-km[n]; dieselprice=p['custo_diesel_combustivel_anual_brl']/(350/450*km[-1]*.5)
 fuel=(otherkm*.5*dieselprice if nd else 0)+r.gas_bus_nm3*3.1
 maint=n/100*p['custo_manutencao_bev_anual_brl']+otherkm*2.3*(bool(nd)+bool(ng)); fleet=n/100*p['custo_aquisicao_100_bev_brl']+nd/350*p['valor_oportunidade_350_diesel_brl']+ng*1500000
 vf=fleet+maint*af+nd/350*p['custo_reposicao_350_diesel_brl']*(D(6)+D(18))+n/100*((p['custo_reposicao_100_bev_brl']-p['credito_residual_bev_brl'])*D(10)-p['credito_residual_bev_brl']*D(20))+ng*1500000*(D(12)-4/12*D(20))
 total=ve+gasinfra+fuel*af+vf
 return pd.Series(dict(F1=total/den,F2=r.f2,LCOE=ve*share/(r.charge_dc_kwh*af) if r.charge_dc_kwh else np.nan,VP_total=total,VP_frota=vf,VP_eletrico_tracao=ve*share,VP_gas_infra_compressao=gasinfra+ve*(1-share),CAPEX=cap+gs+fleet,OPEX=op+gs*.02+fuel+maint,diesel_l=otherkm*.5 if nd else 0,compressao_kwh=comp,perdas_eletricas_kwh=r.grid_kwh+r.pv_kwh+r.chp_net_kwh-ac-comp))
frames=[]
for sc in ['R0','R1','R2']:
 for run in ['174536','180116']:
  d=pd.read_csv(R/f'NSGAII_FINAL_REV01_20261124_{run}'/f'avaliacoes_{sc}.csv');d['execucao']=run;frames.append(d)
d=pd.concat(frames,ignore_index=True);d=pd.concat([d,d.apply(calc,axis=1)],axis=1)
bau=pd.Series(dict(config='BAU',n_bev=450,n_diesel=0,n_gas=0,pv_kwp=0,bess_kwh=0,pcs_kw=0,chp_modules=0,gas_production_nm3h=0,gas_storage_nm3=0,ports=29,f1=.4718822467482189,f2=a['peak_pcc_import_kw'],grid_kwh=a['annual_ac_kwh'],pv_kwh=0,chp_net_kwh=0,substrate_t=0,gas_bus_nm3=0,charge_dc_kwh=a['annual_dc_kwh'],connection_cost=1688976.4815190923));bau=pd.concat([bau,calc(bau)]).to_frame().T
fronts=[]; reps=[]
for sc,g in d.groupby('config'):
 g=g.sort_values(['F1','F2']);keep=[];best=np.inf
 for i,r in g.iterrows():
  if r.F2<best-1e-7:keep.append(i);best=r.F2
 f=g.loc[keep].copy();fronts.append(f);f.to_csv(out/f'pareto_{sc}.csv',index=False)
 z=f[['F1','F2']].to_numpy();z=(z-z.min(0))/np.maximum(np.ptp(z,axis=0),1e-12);k=int(np.argmax(1-z.sum(1)))
 for label,i in [('min_F1',0),('min_F2',len(f)-1),('knee',k)]:reps.append(dict(f.iloc[i],solucao=label))
rep=pd.concat([bau.assign(solucao='calculado'),pd.DataFrame(reps)],ignore_index=True);rep.to_csv(out/'comparativo.csv',index=False);d.to_csv(out/'candidatos.csv',index=False)
notes=['Economia harmonizada exploratoria: tarifa 0.80, demanda 360 por kW ano, carregador 250000 por porta; BAU historico preservado em f1.','Reposicao PCS ano 15, PV inversor e BESS ano 12; residual simplificado 10%; sem contingencia adicional.','O&M BEV agregado pode sobrepor O&M eletrico; custos de conexao BAU historicos, reforco adicional nao quantificado.','LCOE: rateio proporcional energia AC de tracao e compressao, nao custeio marginal.','Diesel preco inferido da premissa sintetica e km medio; km por prefixo.','Emissoes nao calculadas: fatores nao aprovados.','Fronteiras do conjunto amostrado; sem nova otimizacao, sem certificacao anual; BAU eta .95, rotas .9727.']
(out/'ressalvas.txt').write_text('\n'.join(notes),encoding='utf-8')
with pd.ExcelWriter(out/'consolidado.xlsx',engine='openpyxl') as w:
 rep.to_excel(w,sheet_name='Comparativo',index=False);d.to_excel(w,sheet_name='Candidatos',index=False)
 for f in fronts:f.to_excel(w,sheet_name='Pareto_'+f.config.iloc[0],index=False)
 pd.DataFrame({'Ressalvas':notes}).to_excel(w,sheet_name='Premissas',index=False)
try:
 import matplotlib.pyplot as plt
 for f in fronts:
  plt.plot(f.F1,f.F2,'o-',label=f.config.iloc[0]);
 plt.scatter(float(bau.F1.iloc[0]),float(bau.F2.iloc[0]),marker='*',s=120,label='BAU');plt.xlabel('F1 (R$/PKM)');plt.ylabel('F2 (kW)');plt.legend();plt.grid(alpha=.25);plt.tight_layout();plt.savefig(out/'pareto_comparativo.png',dpi=180);plt.close()
 for f in fronts:
  plt.plot(f.F1,f.F2,'o-');plt.xlabel('F1 (R$/PKM)');plt.ylabel('F2 (kW)');plt.grid(alpha=.25);plt.tight_layout();plt.savefig(out/f'pareto_{f.config.iloc[0]}.png',dpi=180);plt.close()
except ImportError:print('matplotlib ausente; CSV e Excel preservados')
print(rep[['config','solucao','F1','F2','LCOE','n_bev','n_diesel','n_gas']].to_string(index=False));print(out)

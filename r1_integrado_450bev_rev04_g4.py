#!/usr/bin/env python3
"""R1 REV03: MILP diario periodico, 450 BEV, rede/PV/BESS/CHP/biogas.
Ensaio exploratorio; nao certifica disponibilidade anual nem capacidade local.
Nao modifica REV02, R0, P2 ou BAU.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import coo_matrix

DT = 0.25

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vehicle-slots', required=True, type=Path)
    p.add_argument('--pv-slots', required=True, type=Path, help='CSV slot,pv_available_kw; 96 linhas; PV em kW')
    p.add_argument('--ports', required=True, type=int)
    p.add_argument('--bess-kwh', required=True, type=float)
    p.add_argument('--pcs-kw', required=True, type=float)
    p.add_argument('--chp-modules', required=True, type=int)
    p.add_argument('--gas-storage-nm3', required=True, type=float)
    p.add_argument('--gas-production-nm3h', required=True, type=float)
    p.add_argument('--substrate-t-day', required=True, type=float)
    p.add_argument('--pcc-kw', default=2500., type=float)
    p.add_argument('--battery-kwh', default=350., type=float)
    p.add_argument('--soc-min', default=.15, type=float)
    p.add_argument('--soc-max', default=.90, type=float)
    p.add_argument('--eta-ac-dc', default=.9727, type=float)
    p.add_argument('--eta-bess', default=.922, type=float)
    p.add_argument('--eta-dc-battery', default=1., type=float)
    p.add_argument('--time-limit', default=300., type=float)
    p.add_argument('--output-dir', default=Path('resultados/R1_IMPLEMENTACAO_CONTROLADA_REV01/milp_rev03'), type=Path)
    a=p.parse_args()
    if min(a.ports,a.bess_kwh,a.pcs_kw,a.chp_modules,a.gas_storage_nm3,a.gas_production_nm3h,a.substrate_t_day,a.pcc_kw) < 0:
        p.error('Capacidades nao podem ser negativas')
    if not (0 <= a.soc_min < a.soc_max <= 1 and 0 < a.eta_ac_dc <= 1 and 0 < a.eta_bess <= 1 and 0 < a.eta_dc_battery <= 1):
        p.error('SOC/eficiencias invalidos')
    raw=pd.read_csv(a.vehicle_slots)
    req={'vehicle_id','slot','traction_kwh','charge_allowed','max_charge_dc_kw'}
    if not req.issubset(raw.columns): p.error(f'Colunas ausentes: {req-set(raw.columns)}')
    if len(raw)!=43200 or raw.vehicle_id.nunique()!=450 or raw.duplicated(['vehicle_id','slot']).any():
        p.error('Esperados exatamente 450 x 96 registros unicos')
    raw=raw.sort_values(['vehicle_id','slot']).reset_index(drop=True)
    vids=raw.vehicle_id.unique().tolist(); V=len(vids); T=96
    if not np.array_equal(raw.slot.to_numpy().reshape(V,T),np.tile(np.arange(T),(V,1))):
        p.error('Cada veiculo deve ter slots 0..95')
    tr=raw.traction_kwh.to_numpy(float).reshape(V,T)
    allow=raw.charge_allowed.to_numpy(float).reshape(V,T)
    maxp=raw.max_charge_dc_kw.to_numpy(float).reshape(V,T)
    if not np.isfinite(tr).all() or (tr < 0).any() or not np.isin(allow,[0,1]).all() or not np.isfinite(maxp).all() or (maxp < 0).any():
        p.error('Dados operacionais invalidos')
    if (maxp[allow==0] > 1e-7).any(): p.error('Potencia positiva em janela bloqueada')
    pv=pd.read_csv(a.pv_slots)
    if not {'slot','pv_available_kw'}.issubset(pv.columns) or len(pv)!=T or not np.array_equal(pv.slot.to_numpy(),np.arange(T)):
        p.error('PV deve conter 96 linhas, slot 0..95, pv_available_kw')
    pv_av=pv.pv_available_kw.to_numpy(float)
    if not np.isfinite(pv_av).all() or (pv_av < 0).any(): p.error('PV invalido')
    # Uma unica variavel de potencia por par elegivel, com binaria de ocupacao.
    pairs=np.argwhere(allow==1); M=len(pairs)
    # indices de variaveis, sempre blocos contiguos
    start={}; cursor=0
    for name,size in [('power',M),('occupied',M),('vehicle_soc',V*T),('grid',T),('pv',T),('bess_charge',T),('bess_discharge',T),('bess_soc',T),('bess_mode',T),('chp_power',T),('chp_active',T),('gas_use',T),('gas_production',T),('gas_soc',T)]:
        start[name]=cursor;cursor+=size
    N=cursor
    ix=lambda name,k:start[name]+k
    lb=np.zeros(N);ub=np.full(N,np.inf);integrality=np.zeros(N,dtype=np.int8);objective=np.zeros(N)
    for k,(v,t) in enumerate(pairs):
        ub[ix('power',k)]=maxp[v,t]
        ub[ix('occupied',k)]=1
        integrality[ix('occupied',k)]=1
    lb[start['vehicle_soc']:start['vehicle_soc']+V*T]=a.soc_min*a.battery_kwh
    ub[start['vehicle_soc']:start['vehicle_soc']+V*T]=a.soc_max*a.battery_kwh
    bounds={'grid':a.pcc_kw,'pv':None,'bess_charge':a.pcs_kw,'bess_discharge':a.pcs_kw,'bess_soc':.9*a.bess_kwh,'bess_mode':1,'chp_power':75*a.chp_modules,'chp_active':a.chp_modules,'gas_use':75*a.chp_modules/(6*.35),'gas_production':a.gas_production_nm3h,'gas_soc':a.gas_storage_nm3}
    for t in range(T):
        for name,cap in bounds.items():
            ub[ix(name,t)]=pv_av[t] if cap is None else cap
        lb[ix('bess_soc',t)]=.1*a.bess_kwh
        integrality[ix('bess_mode',t)]=1
        integrality[ix('chp_active',t)]=1
        objective[ix('grid',t)]=DT
        objective[ix('gas_production',t)]=1e-6*DT
    # Sparse COO, sem criar matriz densa
    ri=[];ci=[];data=[];low=[];high=[]
    def row(items,l=0.,u=0.):
        r=len(low)
        for j,c in items:
            if c:
                ri.append(r);ci.append(int(j));data.append(float(c))
        low.append(float(l));high.append(float(u))
    by_vt={(int(v),int(t)):k for k,(v,t) in enumerate(pairs)}
    by_t=[[] for _ in range(T)]
    for k,(v,t) in enumerate(pairs):
        by_t[int(t)].append(k)
        row([(ix('power',k),1),(ix('occupied',k),-maxp[v,t])],-np.inf,0)
    for t in range(T):
        row([(ix('occupied',k),1) for k in by_t[t]],-np.inf,a.ports)
        # AC: rede + PV + BESS descarga + CHP liquido = BESS carga + carregadores AC
        row([(ix('grid',t),1),(ix('pv',t),1),(ix('bess_discharge',t),1),
             (ix('chp_power',t),.95),(ix('bess_charge',t),-1)] +
            [(ix('power',k),-1/a.eta_ac_dc) for k in by_t[t]])
        # CHP modular: potencia entre 50% e 100% por modulo ligado
        row([(ix('chp_power',t),1),(ix('chp_active',t),-75)],-np.inf,0)
        row([(ix('chp_power',t),1),(ix('chp_active',t),-37.5)],0,np.inf)
        row([(ix('chp_power',t),1),(ix('gas_use',t),-6*.35)])
        row([(ix('bess_charge',t),1),(ix('bess_mode',t),-a.pcs_kw)],-np.inf,0)
        row([(ix('bess_discharge',t),1),(ix('bess_mode',t),a.pcs_kw)],-np.inf,a.pcs_kw)
        prev=(t-1)%T
        row([(ix('bess_soc',t),1),(ix('bess_soc',prev),-1),
             (ix('bess_charge',t),-DT*a.eta_bess),(ix('bess_discharge',t),DT/a.eta_bess)])
        row([(ix('gas_soc',t),1),(ix('gas_soc',prev),-1),
             (ix('gas_production',t),-DT),(ix('gas_use',t),DT)])
    row([(ix('gas_production',t),DT) for t in range(T)],-np.inf,100*a.substrate_t_day)
    # SOC ciclico individual: inicio de t=0 e igual ao fim de t=95
    for v in range(V):
        for t in range(T):
            items=[(ix('vehicle_soc',v*T+t),1),
                   (ix('vehicle_soc',v*T+(t-1)%T),-1)]
            k=by_vt.get((v,t))
            if k is not None:items.append((ix('power',k),-DT*a.eta_dc_battery))
            row(items,-tr[v,t],-tr[v,t])
    A=coo_matrix((data,(ri,ci)),shape=(len(low),N)).tocsr()
    import highspy
    from types import SimpleNamespace
    ref=Path('resultados/R1_REV04_G3')
    d=pd.read_csv(ref/'r1_dispatch_rev03.csv').set_index('slot').loc[np.arange(T)]
    vs=pd.read_csv(ref/'r1_vehicle_states_rev03.csv').set_index(['vehicle_id','slot']).loc[pd.MultiIndex.from_product([vids,range(T)])]
    q=vs.charge_dc_kw.to_numpy().reshape(V,T)
    if not np.allclose(vs.traction_kwh.to_numpy().reshape(V,T),tr,rtol=0,atol=1e-7):
        raise RuntimeError('Tracao G3 divergente')
    x0=np.zeros(N)
    for k,(v,t) in enumerate(pairs):
        x0[ix('power',k)]=q[v,t]
        x0[ix('occupied',k)]=float(q[v,t]>0)
    x0[start['vehicle_soc']:start['vehicle_soc']+V*T]=vs.soc_end_kwh.to_numpy()
    for name in bounds:
        if name=='bess_mode':
            x0[start[name]:start[name]+T]=(d.bess_charge.to_numpy()>1e-8).astype(float)
        else:
            x0[start[name]:start[name]+T]=d[name].to_numpy()
    x0[integrality==1]=np.rint(x0[integrality==1])
    x0=np.clip(x0,lb,ub)
    lo=np.asarray(low); hi=np.asarray(high)
    def audit(x):
        ax=A@x
        return dict(row=float(max(0,np.max(lo-ax),np.max(ax-hi))),bound=float(max(0,np.max(lb-x),np.max(x-ub))),integer=float(np.max(np.abs(x[integrality==1]-np.rint(x[integrality==1])))))
    checks=audit(x0)
    print('G4 MIP start audit:',checks)
    if not np.isfinite(x0).all() or max(checks.values())>1e-6:
        raise RuntimeError('MIP start nao validado')
    c=np.zeros(N); c[start['grid']:start['grid']+T]=DT
    h=highspy.Highs()
    def ok(status):
        if status!=highspy.HighsStatus.kOk:
            raise RuntimeError(str(status))
    ok(h.setOptionValue('time_limit',float(a.time_limit)))
    ok(h.setOptionValue('mip_rel_gap',0.01))
    lp=highspy.HighsLp()
    lp.num_col_=N; lp.num_row_=A.shape[0]
    lp.col_cost_=c; lp.col_lower_=lb; lp.col_upper_=ub
    lp.row_lower_=lo; lp.row_upper_=hi
    lp.integrality_=[highspy.HighsVarType.kInteger if i else highspy.HighsVarType.kContinuous for i in integrality]
    lp.a_matrix_.format_=highspy.MatrixFormat.kRowwise
    lp.a_matrix_.start_=A.indptr.astype(np.int32)
    lp.a_matrix_.index_=A.indices.astype(np.int32)
    lp.a_matrix_.value_=A.data
    ok(h.passModel(lp))
    ok(h.setSolution(N,np.arange(N,dtype=np.int32),x0))
    print('G4 baseline grid kWh:',float(c@x0))
    h.run()
    ms=h.getModelStatus(); info=h.getInfo(); sol=h.getSolution()
    x=np.asarray(sol.col_value) if sol.value_valid else None
    accepted=x is not None and len(x)==N and np.isfinite(x).all() and max(audit(x).values())<=1e-6 and c@x<=c@x0+1e-6
    if not accepted:
        x=x0.copy()
    optimal=accepted and ms==highspy.HighsModelStatus.kOptimal
    result=SimpleNamespace(x=x,status=0 if optimal else 1,message=str(ms)+'; '+('solver incumbent' if accepted else 'validated G3 fallback'),mip_gap=float(info.mip_gap) if accepted and np.isfinite(info.mip_gap) else None)
    a.output_dir.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(a.output_dir/'r1_solution_g4.npz',x=x,baseline=x0)
    meta={'solver_status':str(ms),'solver_version':h.version(),'solver_incumbent_accepted':bool(accepted),'baseline_grid_kwh':float(c@x0),'grid_kwh':float(c@x),'audit':audit(x),'baseline_audit':checks,'dual_bound':float(info.mip_dual_bound) if np.isfinite(info.mip_dual_bound) else None}
    (a.output_dir/'r1_audit_g4.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    print(json.dumps(meta,indent=2))
    status={0:'OPTIMAL',1:'LIMIT_REACHED',2:'INFEASIBLE',3:'UNBOUNDED',4:'SOLVER_ERROR'}.get(result.status,'UNKNOWN')
    report={'status':status,'message':str(result.message),'vehicles':V,'slots':T,'service_traction_kwh':float(tr.sum()),
            'eligible_vehicle_slots':M,'variables':N,'constraints':len(low),'pcc_limit_kw':a.pcc_kw,
            'ports':a.ports,'chp_modules':a.chp_modules,'substrate_t_day':a.substrate_t_day,
            'scope':'SYNTHETIC_PERIODIC_DAY_ONLY','annual_feasibility_certified':False,
            'caveats':['PV, BESS, CHP, substrato e portas sao hipoteses de ensaio ate validacao de limites fisicos',
                       'SOC e balanços verificados nos limites de slots; eventos intrasslot requerem auditoria posterior',
                       'Disponibilidade anual de CHP de 96% nao implementada',
                       'Potencia CHP modular inteira, sem minimo de tempo ligado/desligado',
                       'O objetivo minimiza importacao diaria; nao e F1 economica nem fronteira de Pareto']}
    a.output_dir.mkdir(parents=True,exist_ok=True)
    if result.x is not None:
        x=result.x
        disp=pd.DataFrame({'slot':np.arange(T)})
        for name in ['grid','pv','bess_charge','bess_discharge','bess_soc','chp_power','chp_active','gas_use','gas_production','gas_soc']:
            disp[name]=x[start[name]:start[name]+T]
        charge=np.zeros((V,T));occup=np.zeros((V,T))
        for k,(v,t) in enumerate(pairs):
            charge[v,t]=x[ix('power',k)];occup[v,t]=x[ix('occupied',k)]
        disp['bess_mode']=x[start['bess_mode']:start['bess_mode']+T]
        disp['charge_dc_kw']=charge.sum(axis=0)
        disp['ports_used']=occup.sum(axis=0)
        disp.to_csv(a.output_dir/'r1_dispatch_g4.csv',index=False)
        states=x[start['vehicle_soc']:start['vehicle_soc']+V*T].reshape(V,T)
        pd.DataFrame({'vehicle_id':np.repeat(vids,T),'slot':np.tile(np.arange(T),V),
                      'traction_kwh':tr.ravel(),'charge_dc_kw':charge.ravel(),
                      'soc_end_kwh':states.ravel(),'occupied':occup.ravel()}).to_csv(a.output_dir/'r1_vehicle_states_g4.csv',index=False)
        residual=states-np.roll(states,1,axis=1)-DT*a.eta_dc_battery*charge+tr
        report.update({'peak_pcc_kw':float(disp.grid.max()),'grid_kwh':float(disp.grid.sum()*DT),
                       'max_ports_used':float(disp.ports_used.max()),
                       'charge_dc_kwh':float(charge.sum()*DT),
                       'max_abs_soc_balance_residual_kwh':float(np.max(np.abs(residual))),
                       'max_abs_daily_vehicle_energy_gap_kwh':float(np.max(np.abs(DT*a.eta_dc_battery*charge.sum(axis=1)-tr.sum(axis=1)))),
                       'mip_gap':float(result.mip_gap) if result.mip_gap is not None else None})
    (a.output_dir/'r1_report_g4.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(report,indent=2,ensure_ascii=False))

if __name__=='__main__':main()

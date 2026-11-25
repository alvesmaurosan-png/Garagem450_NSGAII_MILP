"""REV03.2 BAU deterministico: rede ampliavel; sem NSGA-II.
Execucao na raiz: python src/bau_rev032.py --config parametros/bau_rev032.json
Custos ausentes bloqueiam F1/LCOE; nao sao convertidos silenciosamente em zero.
"""
from __future__ import annotations
import argparse, hashlib, json, math
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = ('fleet_purchase','fleet_maintenance','fleet_replacement','charger_purchase',
              'charger_maintenance','charger_replacement','electrical_installation',
              'grid_connection','grid_reinforcement','grid_energy','grid_demand',
              'grid_charges','system_opex','residual_credit')
ELECTRIC = ('charger_purchase','charger_maintenance','charger_replacement',
            'electrical_installation','grid_connection','grid_reinforcement',
            'grid_energy','grid_demand','grid_charges','system_opex','residual_credit')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require_finite(value, label, nonnegative=True):
    if value is None or isinstance(value,bool):
        raise ValueError(f'{label}: valor ausente/invalido')
    x=float(value)
    if not math.isfinite(x) or (nonnegative and x<0):
        raise ValueError(f'{label}: valor nao finito ou negativo')
    return x


def load_frozen(csv, step=15, ports=29, port_kw=138):
    df=pd.read_csv(csv)
    needed={'vehicle_id','slot','charge_dc_kwh','port_active'}
    if not needed.issubset(df.columns):raise ValueError(f'Colunas ausentes: {needed-set(df.columns)}')
    if df.duplicated(['vehicle_id','slot']).any():raise ValueError('Duplicatas veiculo-slot')
    if df[list(needed)].isna().any().any():raise ValueError('Nulos na agenda')
    slots=round(1440/step)
    if slots*step!=1440:raise ValueError('step nao divide 24 horas')
    if (df.slot%1!=0).any() or (df.slot<0).any() or (df.slot>=slots).any():raise ValueError('Slot invalido')
    if (df.charge_dc_kwh< -1e-8).any():raise ValueError('Carga negativa')
    if (df.charge_dc_kwh>port_kw*step/60+1e-6).any():raise ValueError('Porta individual excedida')
    if (~df.port_active.isin([0,1])).any():raise ValueError('port_active invalido')
    if ((df.charge_dc_kwh>1e-6)&(df.port_active!=1)).any():raise ValueError('Carga sem porta')
    if df.vehicle_id.nunique()!=450:raise ValueError('Frota diferente de 450')
    agg=df.groupby('slot').agg(dc_kwh=('charge_dc_kwh','sum'),ports_active=('port_active','sum')).reindex(range(slots),fill_value=0)
    if agg.ports_active.max()>ports:raise ValueError('Numero de portas excedido')
    if abs(agg.dc_kwh.sum()-83386.664545)>.02:raise ValueError('Energia divergente da REV03.1')
    agg=agg.reset_index();agg['start_min']=agg.slot*step
    agg['dc_kw']=agg.dc_kwh*60/step
    if (agg.dc_kw>ports*port_kw+1e-6).any():raise ValueError('Potencia DC excedida')
    return agg


def physical(agg, cfg):
    p=cfg['physical'];eta=require_finite(p['acdc_efficiency'],'acdc_efficiency')
    if not 0<eta<=1:raise ValueError('Eficiencia fora (0,1]')
    step=int(p['step_min']);dt=step/60
    aux=require_finite(p['auxiliary_kw'],'auxiliary_kw')
    margin=require_finite(p['engineering_margin_fraction'],'engineering_margin_fraction')
    kva_factor=require_finite(p['power_factor'],'power_factor')
    if not 0<kva_factor<=1:raise ValueError('Fator de potencia invalido')
    transformer_util=require_finite(p['transformer_max_utilization'],'transformer_max_utilization')
    if not 0<transformer_util<=1:raise ValueError('Utilizacao transformador invalida')
    sizes=p['transformer_standard_kva']
    if not isinstance(sizes,list) or not sizes:raise ValueError('Lista de transformadores ausente')
    sizes=sorted({require_finite(x,'transformer_standard_kva') for x in sizes})
    if sizes[0]<=0:raise ValueError('Transformador invalido')
    d=agg.copy()
    d['charge_ac_kw']=d.dc_kw/eta
    d['auxiliary_kw']=aux
    d['pcc_import_kw']=d.charge_ac_kw+d.auxiliary_kw
    d['pcc_import_kwh']=d.pcc_import_kw*dt
    d['acdc_loss_kwh']=(d.charge_ac_kw-d.dc_kw)*dt
    peak=float(d.pcc_import_kw.max())
    planning=peak*(1+margin)
    required_kva=planning/kva_factor/transformer_util
    transformer=next((x for x in sizes if x>=required_kva-1e-8),None)
    annual=cfg['annualization'];days=require_finite(annual['equivalent_days_per_year'],'equivalent_days_per_year')
    if days<=0 or days>366:raise ValueError('Dias equivalentes fora do intervalo')
    prior=p['existing_connection_kw']
    existing=require_finite(prior,'existing_connection_kw') if prior is not None else None
    contract=p['contracted_demand_kw']
    contract=require_finite(contract,'contracted_demand_kw') if contract is not None else None
    out={
      'daily_dc_kwh':float(d.dc_kwh.sum()),'daily_ac_kwh':float(d.pcc_import_kwh.sum()),
      'daily_aux_kwh':aux*24,'daily_conversion_loss_kwh':float(d.acdc_loss_kwh.sum()),
      'peak_pcc_import_kw':peak,'connection_planning_kw':planning,
      'transformer_required_kva':required_kva,'transformer_selected_kva':transformer,
      'transformer_sizing_status':'SELECTED' if transformer is not None else 'PENDING_STANDARD_SIZE',
      'existing_connection_kw':existing,
      'reinforcement_delta_kw':max(0,planning-existing) if existing is not None else None,
      'contracted_demand_kw':contract,
      'contracted_demand_sufficient':contract>=peak-1e-6 if contract is not None else None,
      'annualization_days':days,'annual_ac_kwh':float(d.pcc_import_kwh.sum()*days),
      'annual_dc_kwh':float(d.dc_kwh.sum()*days),
      'annual_pkm':require_finite(annual['daily_pkm'],'daily_pkm')*days,
      'annual_km':require_finite(annual['daily_km'],'daily_km')*days,
      'annualization_status':'SYNTHETIC_REPEAT_NOT_VALIDATED_CALENDAR',
      'grid_only_bau_physical_status':'PASS_WITH_EXPANDABLE_GRID',
    }
    if abs(out['daily_ac_kwh']-(out['daily_dc_kwh']/eta+aux*24))>1e-5:raise AssertionError('Balanco AC/DC')
    return d,out


def read_master(path):
    if not path.is_file():return {'status':'NOT_FOUND','sha256':None,'active_records':[]}
    df=pd.read_excel(path,sheet_name='Base_Ativa')
    needed={'ID','Parâmetro','Valor ativo','Unidade','Status'}
    if not needed.issubset(df):raise ValueError('Base Mestre com esquema inesperado')
    records=[]
    for _,r in df.iterrows():
        if pd.notna(r['Valor ativo']):
            records.append({'id':str(r['ID']),'parameter':str(r['Parâmetro']),
              'value':str(r['Valor ativo']),'unit':str(r['Unidade']),
              'status':str(r['Status'])})
    return {'status':'READ_ONLY_RECONCILIATION','sha256':sha(path),
            'active_record_count':len(records),'active_records':records}


def economic(cfg, phys):
    econ=cfg['economics'];n=int(econ['years']);rate=require_finite(econ['real_discount_rate'],'real_discount_rate')
    if n<1 or rate<=-1:raise ValueError('Horizonte/taxa invalidos')
    costs=econ['annual_costs_brl_2026']
    if set(costs)!=set(CATEGORIES):raise ValueError('Rubricas devem ser exatamente: '+str(CATEGORIES))
    missing=[];bad=[];flow=[]
    for category in CATEGORIES:
        values=costs[category]
        if not isinstance(values,list) or len(values)!=n:raise ValueError(f'{category}: requer {n} valores anuais (t=1..{n})')
        # custos operacionais no fim do ano; CAPEX inicial deve ser registrado em initial_costs
        for year,v in enumerate(values,1):
            if v is None:missing.append(f'{category}[{year}]')
            else:
                try:require_finite(v,f'{category}[{year}]')
                except ValueError:bad.append(f'{category}[{year}]')
    initial=econ['initial_costs_brl_2026']
    if set(initial)!=set(CATEGORIES):raise ValueError('Rubricas iniciais incompletas')
    for category in CATEGORIES:
        v=initial[category]
        if v is None:missing.append(f'initial:{category}')
        else:
            try:require_finite(v,f'initial:{category}')
            except ValueError:bad.append(f'initial:{category}')
    # GATE: nao supor custos zero. Zero deve ser decisao explicita e justificada.
    if bad:raise ValueError('Custos invalidos: '+str(bad))
    pv_pkm=sum(phys['annual_pkm']/((1+rate)**t) for t in range(1,n+1))
    if pv_pkm<=0:raise ValueError('VP(PKM) nao positivo')
    result={'status':'BLOCKED_MISSING_COSTS' if missing else 'COMPUTED_EXPLORATORY',
            'missing_cost_cells':missing,'pv_pkm':pv_pkm,
            'F2_kw':phys['peak_pcc_import_kw'],
            'lcoe_boundary':'electric_only_costs_over_useful_dc_energy_delivered',
            'lcoe_denominator':'discounted_dc_energy_kwh',
            'fleet_included_in_F1':True}
    if missing:return result,None
    pv_by_category={};rows=[]
    for cat in CATEGORIES:
        sign=-1 if cat=='residual_credit' else 1
        pv=sign*float(initial[cat]);pv_by_category[cat]=pv
        rows.append({'year_index':0,'calendar_year':int(econ['first_year'])-1,
                     'category':cat,'cost_brl_2026':sign*float(initial[cat]),'discount_factor':1.,'pv_brl_2026':pv})
        for t,value in enumerate(costs[cat],1):
            dfactor=1/(1+rate)**t;discounted=sign*float(value)*dfactor
            pv_by_category[cat]+=discounted
            rows.append({'year_index':t,'calendar_year':int(econ['first_year'])+t-1,
                         'category':cat,'cost_brl_2026':sign*float(value),
                         'discount_factor':dfactor,'pv_brl_2026':discounted})
    total=sum(pv_by_category.values());elec=sum(pv_by_category[c] for c in ELECTRIC)
    pv_dc=sum(phys['annual_dc_kwh']/((1+rate)**t) for t in range(1,n+1))
    result.update({'F1_brl_per_pkm':total/pv_pkm,'LCOE_brl_per_dc_kwh':elec/pv_dc,
      'pv_integrated_cost_brl_2026':total,'pv_electric_cost_brl_2026':elec,
      'pv_dc_energy_kwh':pv_dc,'pv_costs_by_category':pv_by_category,
      'note':'F1 e LCOE exploratorios ate homologacao de tarifas, custos, anualizacao e fronteira LCOE'})
    return result,pd.DataFrame(rows)


def run(cfg, root=ROOT):
    path=root/cfg['inputs']['frozen_vehicle_csv'];rev=root/cfg['inputs']['rev031_audit_json']
    if not path.is_file() or not rev.is_file():raise FileNotFoundError(f'Entradas REV02.3a/REV03.1 ausentes: {path}, {rev}')
    reference=json.loads(rev.read_text(encoding='utf-8'))
    expected=reference['input_sha256'].get(path.name)
    if expected is None or sha(path)!=expected:raise ValueError('HASH da agenda nao coincide com REV03.1')
    if reference['parameters']['frozen_ports']!=29:raise ValueError('REV03.1 nao fixa 29 portas')
    if abs(cfg['annualization']['daily_pkm']-reference['service_total_pkm'])>1e-4:raise ValueError('PKM difere do servico congelado')
    if abs(cfg['annualization']['daily_km']-reference['service_total_km'])>1e-4:raise ValueError('km diferem do servico congelado')
    if cfg['physical']['step_min']!=reference['parameters']['step_min']:raise ValueError('Passo temporal alterado')
    if abs(cfg['physical']['acdc_efficiency']-reference['parameters']['acdc_efficiency_exploratory'])>1e-12:
        raise ValueError('Eficiencia difere da REV03.1 congelada')
    agg=load_frozen(path,cfg['physical']['step_min'])
    d,phys=physical(agg,cfg)
    if abs(phys['peak_pcc_import_kw']-reference['frozen_schedule']['peak_ac_kw']-cfg['physical']['auxiliary_kw'])>1e-5:
        raise ValueError('Pico nao reconcilia com REV03.1')
    if abs(phys['daily_dc_kwh']-reference['frozen_schedule']['daily_dc_kwh'])>.01:
        raise ValueError('Energia nao reconcilia com REV03.1')
    master_path=root/cfg['inputs']['master_xlsx']
    master=read_master(master_path)
    result,ledger=economic(cfg,phys)
    audit={'generator':'REV032_BAU_DETERMINISTIC','classification':'SYNTHETIC_EXPLORATORY',
      'BAU_no_2500_kw_cap':True,'NSGA_II_used':False,
      'frozen_reference':'REV02.3a peak 29 portas / REV03.1',
      'hashes':{path.name:sha(path),rev.name:sha(rev),master_path.name:master['sha256']},
      'physical':phys,'economic':result,
      'master_reconciliation':{'status':master['status'],'active_record_count':master.get('active_record_count'),
        'warning':'Valores da Base Mestre NAO sao importados automaticamente para custos'},
      'audit':{'physical_energy_balance':'PASS','frozen_hash':'PASS',
               'economic_complete':result['status']=='COMPUTED_EXPLORATORY',
               'BAU_final_approved':False}}
    out=root/'resultados'/'bau_REV032';out.mkdir(parents=True,exist_ok=True)
    d.to_csv(out/'balanco_15min_REV032.csv',index=False)
    if ledger is not None:ledger.to_csv(out/'fluxos_economicos_REV032.csv',index=False)
    (out/'auditoria_REV032.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    return audit


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',default='parametros/bau_rev032.json')
    args=ap.parse_args();cfg_path=Path(args.config)
    if not cfg_path.is_absolute():cfg_path=ROOT/cfg_path
    cfg=json.loads(cfg_path.read_text(encoding='utf-8'))
    print(json.dumps(run(cfg),ensure_ascii=False,indent=2))

if __name__=='__main__':main()

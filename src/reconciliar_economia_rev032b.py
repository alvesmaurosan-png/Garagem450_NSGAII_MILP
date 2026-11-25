"""REV03.2b: inventário e geração de fluxos econômicos condicionais, sem F1/LCOE.
Não modifica REV03.2/REV03.2a. Executar na raiz do projeto.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, math
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
CATEGORIES=('fleet_purchase','fleet_maintenance','fleet_replacement','charger_purchase',
'charger_maintenance','charger_replacement','electrical_installation','grid_connection',
'grid_reinforcement','grid_energy','grid_demand','grid_charges','system_opex','residual_credit')
RULES={'initial_unit','initial_fixed','annual_unit','annual_fixed','annual_energy',
'annual_demand','annual_fraction_capex','replacement_unit','residual_fraction','explicit_zero'}
VALID_STATUSES={'VALIDATED','EXPLORATORY','PENDING'}


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def csv_write(path, rows, headers):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=headers,extrasaction='ignore');w.writeheader();w.writerows(rows)

def number(x,label):
    if isinstance(x,bool) or not isinstance(x,(float,int)) or not math.isfinite(x) or x<0:
        raise ValueError(f'{label}: requer numero nao negativo finito')
    return float(x)

def rule_value(spec, t, phys):
    kind=spec['rule']; p=spec.get('parameters',{})
    if kind=='explicit_zero':return 0.0
    if kind=='initial_fixed':return number(p['amount_brl_2026'],'amount') if t==0 else 0.0
    if kind=='initial_unit':return number(p['unit_cost_brl_2026'],'unit_cost')*number(p['quantity'],'quantity') if t==0 else 0.0
    if kind=='annual_fixed':return number(p['amount_brl_2026_per_year'],'amount') if t>0 else 0.0
    if kind=='annual_unit':return number(p['unit_cost_brl_2026_per_year'],'unit_cost')*number(p['quantity'],'quantity') if t>0 else 0.0
    if kind=='annual_energy':return number(p['tariff_brl_per_kwh'],'tariff')*number(phys['annual_ac_kwh'],'annual_ac_kwh') if t>0 else 0.0
    if kind=='annual_demand':return number(p['tariff_brl_per_kw_month'],'tariff')*number(p['contracted_kw'],'contracted_kw')*12 if t>0 else 0.0
    if kind=='annual_fraction_capex':return number(p['capex_brl_2026'],'capex')*number(p['fraction_per_year'],'fraction') if t>0 else 0.0
    if kind=='replacement_unit':
        years=p['years'];
        if not isinstance(years,list) or not all(isinstance(y,int) and y>0 for y in years):raise ValueError('replacement years invalidos')
        return number(p['unit_cost_brl_2026'],'unit_cost')*number(p['quantity'],'quantity') if t in years else 0.0
    if kind=='residual_fraction':
        return number(p['asset_cost_brl_2026'],'asset_cost')*number(p['residual_fraction'],'fraction') if t==phys['years'] else 0.0
    raise ValueError('Regra nao reconhecida: '+str(kind))

def run(config, root=ROOT):
    root=Path(root); base=json.loads((root/config['bau_config']).read_text(encoding='utf-8'))
    econ=base['economics'];n=econ['years'];first=econ['first_year'];rate=econ['real_discount_rate']
    if (n,first)!=(20,2038) or not math.isclose(rate,.08,abs_tol=1e-12):raise ValueError('Protocolo 20 anos/2038/8% alterado')
    if config.get('reference_t0')!='INICIO_2038' or config.get('currency_base')!='BRL_CONSTANT_2026':raise ValueError('Referencia temporal/monetaria invalida')
    master=root/base['inputs']['master_xlsx'];df=pd.read_excel(master,sheet_name='Base_Ativa')
    active=df[df['Valor ativo'].notna()].copy();active['ID']=active['ID'].astype(str)
    if active['ID'].duplicated().any():raise ValueError('IDs duplicados')
    master_rows=[]
    for _,r in active.iterrows():
        rid=str(r['ID']); is_bau=rid not in ('D05-001','OPS-003')
        disposition='FORA_BAU' if not is_bau else ('CONVERSAO_ANO_BASE_PENDENTE' if rid=='ECO-009' else 'REFERENCIA_DOCUMENTAL')
        master_rows.append(dict(id=rid,parametro=str(r['Parâmetro']),valor_fonte=str(r['Valor ativo']),
            unidade_fonte=str(r['Unidade']),status_fonte=str(r['Status']),origem_fonte=str(r['Origem ativa']),
            aplicacao_fonte=str(r['Aplicação']),tratamento_bau=disposition,
            observacao=str(r['Observação'])))
    rules=config['categories']
    if set(rules)!=set(CATEGORIES):raise ValueError('As 14 categorias sao obrigatorias')
    phys=config['physical_drivers']; phys['years']=n
    for key in ('annual_ac_kwh','peak_pcc_import_kw','fleet_count','charger_ports'):
        number(phys[key],key)
    # Gate de consistencia com resultado fisico auditado: não permitir alterar a referência.
    audit_file=root/'resultados'/'bau_REV032'/'auditoria_REV032.json'
    if not audit_file.is_file():raise FileNotFoundError('Auditoria REV03.2 obrigatoria: '+str(audit_file))
    audit=json.loads(audit_file.read_text(encoding='utf-8')); frozen=audit['physical']
    for a,b in [('annual_ac_kwh','annual_ac_kwh'),('peak_pcc_import_kw','peak_pcc_import_kw')]:
        if not math.isclose(phys[a],frozen[b],rel_tol=1e-9,abs_tol=1e-5):raise ValueError('Driver fisico nao coincide com REV03.2: '+a)
    if phys['fleet_count']!=450 or phys['charger_ports']!=29:raise ValueError('Frota/portas congeladas divergentes')
    if not audit['BAU_no_2500_kw_cap']:raise ValueError('BAU com limite PCC indevido')
    matrix=[];flows=[];issues=[];count_known=0
    for cat in CATEGORIES:
        spec=rules[cat];status=spec['status'];kind=spec['rule']
        if status not in VALID_STATUSES:raise ValueError('Status invalido '+cat)
        if kind is not None and kind not in RULES:raise ValueError('Regra invalida '+cat)
        source=spec.get('source','');reason=spec.get('justification','');yearbase=spec.get('price_base_year')
        ready=status=='VALIDATED' and kind in RULES and bool(source.strip()) and yearbase==2026 and bool(reason.strip())
        if kind=='explicit_zero' and (not reason.strip() or not source.strip()):ready=False
        if kind=='annual_energy' and cat!='grid_energy':raise ValueError('annual_energy so grid_energy')
        if kind=='annual_demand' and cat!='grid_demand':raise ValueError('annual_demand so grid_demand')
        if kind=='residual_fraction' and cat!='residual_credit':raise ValueError('residual_fraction so residual_credit')
        matrix.append(dict(categoria=cat,regra=kind or '',status_parametro=status,fonte=source,
            ano_base=yearbase if yearbase is not None else '',justificativa=reason,
            parametros_json=json.dumps(spec.get('parameters',{}),ensure_ascii=False),
            habilitado_para_fluxo='SIM' if ready else 'NAO',
            bloqueio='' if ready else 'AUSENTE_OU_NAO_VALIDADO'))
        if not ready:issues.append(dict(categoria=cat,tipo='PARAMETRO',detalhe='Regra/fonte/justificativa/ano-base 2026 ausente ou nao validado'))
        for t in range(n+1):
            moment='INICIO_2038' if t==0 else 'FIM_'+str(first+t-1)
            val=None
            if ready:
                val=rule_value(spec,t,phys)
                count_known+=1
            flows.append(dict(ano_indice=t,ano_calendario=first if t==0 else first+t-1,
                momento=moment,categoria=cat,regra=kind or '',valor_brl_2026='' if val is None else round(val,6),
                fator_desconto=round((1+rate)**(-t),12),vp_brl_2026='' if val is None else round(val/(1+rate)**t,6),
                status='VALIDADO' if ready else 'BLOQUEADO',fonte=source,
                credito=(cat=='residual_credit')))
    # Guardas de fronteira economica; F1 e LCOE nao sao calculados nesta revisao mesmo sem pendencias.
    out=root/'resultados'/'bau_REV032b';out.mkdir(parents=True,exist_ok=True)
    csv_write(out/'inventario_mestre_REV032b.csv',master_rows,['id','parametro','valor_fonte','unidade_fonte','status_fonte','origem_fonte','aplicacao_fonte','tratamento_bau','observacao'])
    csv_write(out/'matriz_regras_REV032b.csv',matrix,list(matrix[0]))
    csv_write(out/'fluxos_condicionais_REV032b.csv',flows,list(flows[0]))
    csv_write(out/'pendencias_REV032b.csv',issues,['categoria','tipo','detalhe'])
    report={'generator':'REV032b_ECONOMIC_RULE_RECONCILIATION','classification':'SYNTHETIC_EXPLORATORY',
        'hashes':{'master_xlsx':sha(master),'bau_config':sha(root/config['bau_config']),
                  'rev032_audit':sha(audit_file)},
        'master_active_records':len(master_rows),'categories':len(matrix),'cost_rows':len(flows),
        'validated_cost_rows':count_known,'blocked_cost_rows':len(flows)-count_known,
        'blocked_categories':[m['categoria'] for m in matrix if m['habilitado_para_fluxo']=='NAO'],
        'reference_t0':'INICIO_2038','first_operational_year':2038,'last_operational_year':2057,
        'currency_base':'BRL_CONSTANT_2026','real_discount_rate':rate,
        'physical_reference_verified':True,'bau_grid_expandable':True,'pcc_2500_applied_to_bau':False,
        'F1_brl_per_pkm':None,'LCOE_brl_per_kwh':None,'BAU_final_approved':False,
        'economic_status':'BLOCKED_MISSING_OR_UNVALIDATED_COSTS' if issues else 'RULES_VALIDATED_BUT_F1_STILL_GATED',
        'warnings':['ECO-009 maio/2025 nao convertido para 2026','Nenhum zero implicito: somente regras validadas geram zeros fora do periodo de incidencia',
        'Creditos residuais sao positivos na matriz e devem ser subtraidos no custo total futuro',
        'Tarifa anual_energy e simplificacao: tarifacao horossazonal exige serie 15 min e calendario',
        'Evitar dupla contagem entre charger_purchase/electrical_installation e grid_charges/grid_energy/grid_demand']}
    (out/'auditoria_REV032b.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',default='parametros/economia_rev032b.json');a=ap.parse_args()
    cp=Path(a.config);cp=cp if cp.is_absolute() else ROOT/cp
    print(json.dumps(run(json.loads(cp.read_text(encoding='utf-8'))),ensure_ascii=False,indent=2))
if __name__=='__main__':main()

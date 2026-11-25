"""REV03.2a: auditoria econômica read-only; NUNCA calcula F1/LCOE com lacunas.
Executar na raiz: python src/reconciliar_economia_rev032a.py --config parametros/bau_rev032.json
"""
from __future__ import annotations
import argparse, csv, hashlib, json, math
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = ('fleet_purchase','fleet_maintenance','fleet_replacement','charger_purchase',
'charger_maintenance','charger_replacement','electrical_installation','grid_connection',
'grid_reinforcement','grid_energy','grid_demand','grid_charges','system_opex','residual_credit')
MAPPING = {
'D03-001':('physical.fleet_size','Frota 450 BEV','BAU'),
'D05-001':('scenario.pcc_limit','NAO APLICAR AO BAU','R0/R1/R2'),
'ECO-001':('economics.real_discount_rate','Desconto real','BAU'),
'ECO-002':('economics.years','Horizonte','BAU'),
'ECO-003':('economics.first_year','Implantacao','BAU'),
'ECO-004':('economics.currency_base_year','Reais constantes','BAU'),
'ECO-005':('economics.first_operational_year','Primeiro fluxo fim 2038','BAU'),
'ECO-006':('economics.pv_reference','t=0 inicio 2038','BAU'),
'ECO-009':('fleet_purchase','Preco mai/2025; conversao 2026 pendente','BAU'),
'OPS-003':('gas_bus_consumption','NAO APLICAR AO BAU','R2')}


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write_csv(path, headers, records):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=headers,extrasaction='ignore');w.writeheader();w.writerows(records)


def run(cfg, root=ROOT):
    econ=cfg['economics']; n=econ['years']; first=econ['first_year']; rate=econ['real_discount_rate']
    if not isinstance(n,int) or n!=20 or first!=2038 or not isinstance(rate,(int,float)) or not math.isclose(rate,.08,abs_tol=1e-12):
        raise ValueError('REV03.2a exige horizonte 20 anos, inicio 2038, desconto real 8%; alteracoes exigem revisao de protocolo')
    if cfg['physical']['existing_connection_kw'] is not None:
        # Nao impede a auditoria: custo de reforco depende da conexao efetiva
        pass
    costs=econ['annual_costs_brl_2026'];initial=econ['initial_costs_brl_2026']
    if set(costs)!=set(CATEGORIES) or set(initial)!=set(CATEGORIES):raise ValueError('Rubricas nao reconciliam com REV03.2')
    for c in CATEGORIES:
        if not isinstance(costs[c],list) or len(costs[c])!=n:raise ValueError('Serie anual invalida: '+c)
    master=root/cfg['inputs']['master_xlsx']
    if not master.is_file():raise FileNotFoundError(master)
    df=pd.read_excel(master,sheet_name='Base_Ativa')
    required={'ID','Parâmetro','Valor ativo','Unidade','Status','Origem ativa','Aplicação','Observação'}
    if not required.issubset(df.columns):raise ValueError('Esquema Base Mestre inesperado')
    active=df.loc[df['Valor ativo'].notna()].copy()
    if active['ID'].duplicated().any():raise ValueError('IDs ativos duplicados')
    out=root/'resultados'/'bau_REV032a';out.mkdir(parents=True,exist_ok=True)
    params=[]
    for _,r in active.iterrows():
        rid=str(r['ID']); mapped,policy,scope=MAPPING.get(rid,('UNMAPPED','Exige avaliacao individual','UNDETERMINED'))
        params.append({'id':rid,'parametro':str(r['Parâmetro']),'valor_fonte':str(r['Valor ativo']),
        'unidade_fonte':str(r['Unidade']),'status_fonte':str(r['Status']),
        'origem':str(r['Origem ativa']),'aplicacao_fonte':str(r['Aplicação']),
        'campo_destino_proposto':mapped,'escopo_revisao':scope,'tratamento':policy,
        'status_integracao':'REFERENCIA_SEM_IMPORTACAO','observacao':str(r['Observação'])})
    write_csv(out/'matriz_parametros_REV032a.csv',list(params[0]) if params else ['id'],params)
    rows=[];pending=[]
    for c in CATEGORIES:
        for t in range(n+1):
            val=initial[c] if t==0 else costs[c][t-1]
            year=first if t==0 else first+t-1
            label='INICIO_2038' if t==0 else 'FIM_'+str(year)
            valid=isinstance(val,(int,float)) and not isinstance(val,bool) and math.isfinite(val) and val>=0
            state='PENDENTE' if val is None else ('VALOR_SEM_PROVENIENCIA' if valid else 'INVALIDO')
            # Valores presentes no JSON sao apenas candidatos ate a documentacao de origem
            if state!='VALIDADO':pending.append({'categoria':c,'ano_indice':t,'ano_calendario':year,'situacao':state,
                'acao':'Documentar custo, ano-base, fonte e justificativa; zero exige decisao explicita'})
            rows.append({'ano_indice':t,'ano_calendario':year,'momento':label,'categoria':c,
              'valor_brl_2026':val if valid else '', 'status':state,
              'fator_desconto':round((1+rate)**(-t),12),
              'vp_brl_2026':'', 'observacao':'Sem VP: valor nao validado' if val is not None else 'Custo ausente; NAO equivale a zero'})
    write_csv(out/'fluxos_auditaveis_REV032a.csv',list(rows[0]),rows)
    write_csv(out/'pendencias_economicas_REV032a.csv',list(pending[0]),pending)
    audit={'generator':'REV032a_ECONOMIC_AUDIT_ONLY','classification':'SYNTHETIC_EXPLORATORY',
      'input_hashes':{'master_xlsx':digest(master)},'master_active_records':len(params),
      'first_operational_year':first,'last_operational_year':first+n-1,
      'reference_t0':'INICIO_2038','operating_flows':'FIM_DE_CADA_ANO_2038_2057',
      'currency_base':'BRL_CONSTANT_2026','real_discount_rate':rate,
      'bau_grid_expandable':True,'pcc_2500_applied_to_bau':False,
      'frozen_physical_results_modified':False,'cost_rows':len(rows),
      'pending_cost_rows':len(pending),'economic_status':'BLOCKED_MISSING_OR_UNVALIDATED_COSTS',
      'F1_brl_per_pkm':None,'LCOE_brl_per_kwh':None,'BAU_final_approved':False,
      'cautions':['CAPEX ECO-009 em R$ mai/2025 nao convertido para R$2026',
      'Zero requer justificativa; nao preencher automaticamente',
      'Nenhuma rubrica e importada automaticamente da Base Mestre',
      'Conexao existente e demanda contratada pendentes; reforco nao precificado',
      'F1/LCOE nao calculados, mesmo que JSON tenha valores sem proveniencia']}
    (out/'auditoria_REV032a.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    return audit


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',default='parametros/bau_rev032.json');a=ap.parse_args()
    cp=Path(a.config);cp=cp if cp.is_absolute() else ROOT/cp
    print(json.dumps(run(json.loads(cp.read_text(encoding='utf-8'))),ensure_ascii=False,indent=2))
if __name__=='__main__':main()

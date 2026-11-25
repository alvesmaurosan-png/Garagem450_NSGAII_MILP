"""REV03.2c: auditoria monetaria read-only; nunca calcula F1/LCOE nem altera REV anteriores."""
from __future__ import annotations
import argparse,csv,hashlib,json,math
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
CATS=('fleet_purchase','fleet_maintenance','fleet_replacement','charger_purchase','charger_maintenance','charger_replacement','electrical_installation','grid_connection','grid_reinforcement','grid_energy','grid_demand','grid_charges','system_opex','residual_credit')

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save_csv(p,rows,cols):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore');w.writeheader();w.writerows(rows)
def finite(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) and x>=0

def convert_price(value,source_year,target_year,index_source,index_target):
    if not finite(value) or not finite(index_source) or not finite(index_target) or index_source<=0 or index_target<=0:raise ValueError('Indice/valor invalido')
    if source_year!=2025 or target_year!=2026:raise ValueError('Conversao fora do escopo controlado')
    return value*index_target/index_source

def run(config,root=ROOT):
    root=Path(root);bau_path=root/config['bau_config']; b_path=root/config['rev032b_config']
    bau=json.loads(bau_path.read_text(encoding='utf-8'));b=json.loads(b_path.read_text(encoding='utf-8'))
    master=root/bau['inputs']['master_xlsx']; audit_path=root/'resultados/bau_REV032/auditoria_REV032.json'
    b_audit_path=root/'resultados/bau_REV032b/auditoria_REV032b.json'
    for p in (master,audit_path,b_audit_path):
        if not p.is_file():raise FileNotFoundError(str(p))
    a=json.loads(audit_path.read_text(encoding='utf-8'));ba=json.loads(b_audit_path.read_text(encoding='utf-8'))
    if sha(master)!=ba['hashes']['master_xlsx'] or sha(audit_path)!=ba['hashes']['rev032_audit']:raise ValueError('Hash mudou desde REV03.2b')
    if not ba['physical_reference_verified'] or not a['BAU_no_2500_kw_cap']:raise ValueError('Referencia fisica invalida')
    if (bau['economics']['years'],bau['economics']['first_year'],bau['economics']['real_discount_rate'])!=(20,2038,0.08):raise ValueError('Horizonte economico alterado')
    if set(b['categories'])!=set(CATS):raise ValueError('Rubricas REV03.2b divergentes')
    df=pd.read_excel(master,sheet_name='Base_Ativa');df=df[df['Valor ativo'].notna()]
    if len(df)!=10 or df['ID'].duplicated().any():raise ValueError('Base Mestre ativa inesperada')
    eco=df[df['ID']=='ECO-009']
    if len(eco)!=1 or not math.isclose(float(eco.iloc[0]['Valor ativo']),2799076.42,abs_tol=.01):raise ValueError('ECO-009 alterado')
    monetary=config['monetary'];idx=monetary['indexation_2025_2026']; status=idx['status']
    if status not in ('PENDING','EXPLORATORY','VALIDATED'):raise ValueError('Status indice invalido')
    source=idx.get('source','');basis=idx.get('methodology','');i25=idx.get('index_may_2025');i26=idx.get('index_2026_reference')
    valid=status=='VALIDATED' and bool(source.strip()) and bool(basis.strip()) and finite(i25) and finite(i26) and i25>0 and i26>0
    converted=convert_price(2799076.42,2025,2026,i25,i26) if valid else None
    inventory=[]
    for _,r in df.iterrows():
        rid=str(r['ID']); monetary_id=rid=='ECO-009'; outside=rid in ('D05-001','OPS-003')
        inventory.append(dict(id=rid,parametro=r['Parâmetro'],valor_fonte=r['Valor ativo'],unidade=r['Unidade'],status_fonte=r['Status'],origem=r['Origem ativa'],pesquisa=r['ID pesquisa'],observacao=r['Observação'],data_base='MAIO_2025' if monetary_id else 'NAO_APLICAVEL',aplicacao_bau='NAO' if outside else 'SIM',valor_brl_2026=round(converted,6) if monetary_id and valid else '',tratamento='CONVERTIDO_CONDICIONAL' if monetary_id and valid else ('CONVERSAO_PENDENTE' if monetary_id else ('FORA_DA_FRONTEIRA_BAU' if outside else 'PREMISSA_NAO_MONETARIA'))))
    rules=[];issues=[];flows=[];filled=0
    for cat in CATS:
        spec=b['categories'][cat]; st=spec['status']; rule=spec['rule'];src=spec.get('source','');just=spec.get('justification','');base=spec.get('price_base_year')
        # A REV03.2c nao promove automaticamente nenhum custo a validado.
        # Conversao ECO-009, mesmo completa, requer aprovacao da regra de aquisicao na REV03.2b.
        eligible=st=='VALIDATED' and base==2026 and bool(src.strip()) and bool(just.strip()) and rule is not None
        # Proibido habilitar rubricas nesta revisao: so audita elegibilidade declarada.
        if eligible:issues.append(dict(categoria=cat,pendencia='VALIDACAO_CRUZADA_NECESSARIA',detalhe='Regra declarada VALIDATED na REV03.2b; reconciliar com modelo de custos antes de calcular'))
        else:issues.append(dict(categoria=cat,pendencia='CUSTO_NAO_HOMOLOGADO',detalhe='Fonte, ano-base, regra ou validacao pendente'))
        rules.append(dict(categoria=cat,regra=rule,status_origem=st,fonte=src,ano_base=base if base is not None else '',elegivel_documental='SIM' if eligible else 'NAO',habilitado_para_F1='NAO',tratamento='CREDITO_SUBTRAIR' if cat=='residual_credit' else 'CUSTO_ADICIONAR',risco_dupla_contagem=('carregador versus instalacao' if cat in ('charger_purchase','electrical_installation') else 'energia/demanda/encargos' if cat in ('grid_energy','grid_demand','grid_charges') else 'nenhum risco especifico identificado')))
        for t in range(21):
            flows.append(dict(categoria=cat,t=t,ano_calendario=2038 if t==0 else 2037+t,momento='INICIO_2038' if t==0 else 'FIM_'+str(2037+t),valor_brl_2026='',fator_desconto=round(1/(1.08**t),12),vp_brl_2026='',status='BLOQUEADO_REV032c',fonte=src,regra=rule))
    if not valid:issues.append(dict(categoria='fleet_purchase',pendencia='INDICE_DE_CONVERSAO',detalhe='ECO-009 maio/2025 requer indice e metodologia ate referencia de 2026'))
    issues.extend([dict(categoria='grid_reinforcement',pendencia='CAPACIDADE_EXISTENTE',detalhe='Potencia de conexao existente nao documentada'),dict(categoria='grid_demand',pendencia='DEMANDA_CONTRATADA',detalhe='Demanda contratada nao definida'),dict(categoria='grid_energy',pendencia='TARIFA_HOROSSAZONAL',detalhe='Tarifa, calendario e contabilizacao temporal nao homologados')])
    out=root/'resultados/bau_REV032c';out.mkdir(parents=True,exist_ok=True)
    save_csv(out/'inventario_monetario_REV032c.csv',inventory,list(inventory[0]))
    save_csv(out/'matriz_homologacao_REV032c.csv',rules,list(rules[0]))
    save_csv(out/'fluxos_bloqueados_REV032c.csv',flows,list(flows[0]))
    save_csv(out/'pendencias_priorizadas_REV032c.csv',issues,['categoria','pendencia','detalhe'])
    report=dict(generator='REV032c_MONETARY_CONTROL_ONLY',classification='SYNTHETIC_EXPLORATORY',hashes={'master':sha(master),'bau_config':sha(bau_path),'rev032_audit':sha(audit_path),'rev032b_config':sha(b_path),'rev032b_audit':sha(b_audit_path)},master_active_records=len(inventory),monetary_source='ECO-009',source_price_brl_may_2025=2799076.42,conversion_index_status=status,conversion_methodology=basis or None,converted_unit_price_brl_2026=converted,monetary_conversion_ready=valid,reference_t0='INICIO_2038',cost_rows=len(flows),blocked_rows=len(flows),categories=len(rules),F1_brl_per_pkm=None,LCOE_brl_per_kwh=None,BAU_final_approved=False,economic_status='BLOCKED_MONETARY_RECONCILIATION',prior_revisions_modified=False,notes=['Valor monetario convertido, se houver, e documental; nao habilita automaticamente CAPEX da frota','Nenhum zero implicito e nenhum fluxo numerico foi gerado','Tarifa horossazonal e custos de reforco continuam pendentes','As 14 rubricas exigem verificacao de dupla contagem e escopo'])
    (out/'auditoria_REV032c.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',default='parametros/economia_rev032c.json');args=p.parse_args();cfg=Path(args.config);cfg=cfg if cfg.is_absolute() else ROOT/cfg
    print(json.dumps(run(json.loads(cfg.read_text(encoding='utf-8'))),ensure_ascii=False,indent=2))
if __name__=='__main__':main()

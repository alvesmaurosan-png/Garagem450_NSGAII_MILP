"""REV03.2d: auditoria documental monetaria read-only sobre REV03.2c.
Nao altera arquivos de revisoes anteriores nem calcula F1/LCOE.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CATS=('fleet_purchase','fleet_maintenance','fleet_replacement','charger_purchase','charger_maintenance','charger_replacement','electrical_installation','grid_connection','grid_reinforcement','grid_energy','grid_demand','grid_charges','system_opex','residual_credit')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def readcsv(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def writecsv(path,rows,columns):
    with Path(path).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');w.writeheader();w.writerows(rows)
def number(x):return type(x) in (int,float) and math.isfinite(x) and x>0

def run(config,root=ROOT):
    root=Path(root);c_path=root/config['rev032c_config'];c=json.loads(c_path.read_text(encoding='utf-8'))
    base=root/'resultados/bau_REV032c';audit_path=base/'auditoria_REV032c.json'
    audit=json.loads(audit_path.read_text(encoding='utf-8'))
    if audit['generator']!='REV032c_MONETARY_CONTROL_ONLY' or audit['cost_rows']!=294 or audit['blocked_rows']!=294:raise ValueError('REV03.2c inconsistente')
    master=root/'parametros/Base_Mestre_450_Reconciliada_REV02.xlsx'
    bau=root/c['bau_config'];b=root/c['rev032b_config'];bau_audit=root/'resultados/bau_REV032/auditoria_REV032.json';b_audit=root/'resultados/bau_REV032b/auditoria_REV032b.json'
    for key,p in [('master',master),('bau_config',bau),('rev032b_config',b),('rev032_audit',bau_audit),('rev032b_audit',b_audit)]:
        if sha(p)!=audit['hashes'][key]:raise ValueError('Integridade alterada: '+key)
    inv=readcsv(base/'inventario_monetario_REV032c.csv');rules=readcsv(base/'matriz_homologacao_REV032c.csv');flows=readcsv(base/'fluxos_bloqueados_REV032c.csv')
    if len(inv)!=10 or len(rules)!=14 or len(flows)!=294 or {r['categoria'] for r in rules}!=set(CATS):raise ValueError('Matrizes REV03.2c inesperadas')
    if any(r['valor_brl_2026'].strip() or r['vp_brl_2026'].strip() for r in flows):raise ValueError('Fluxos anteriores nao bloqueados')
    monetary=config['monetary'];period=monetary['target_period'];status=monetary['status'];idx=monetary['index']
    if period!='2026-01':raise ValueError('REV03.2d fixada em janeiro/2026; alterar exige decisao explicita')
    if status not in ('PENDING','DOCUMENTED','APPROVED'):raise ValueError('Status invalido')
    source=idx['source'];i25=idx['may_2025'];i26=idx['jan_2026'];url=idx['url'];retrieval=idx['retrieved_on'];series=idx['series'];method=idx['methodology']
    complete=all(isinstance(x,str) and x.strip() for x in (source,url,retrieval,series,method)) and number(i25) and number(i26)
    if status!='PENDING' and not complete:raise ValueError('Indice documentado/aprovado exige fonte, URL, serie, data e ambos indices')
    approved=status=='APPROVED' and complete and bool(monetary['approval'].get('decision_id')) and bool(monetary['approval'].get('approved_by')) and bool(monetary['approval'].get('approved_on'))
    if status=='APPROVED' and not approved:raise ValueError('Aprovacao exige responsavel, data e ID da decisao')
    source_price=2799076.42
    converted=round(source_price*i26/i25,6) if complete else None
    if not any(r['id']=='ECO-009' and abs(float(r['valor_fonte'])-source_price)<.01 for r in inv):raise ValueError('ECO-009 divergente')
    rows=[]
    for r in rules:
        cat=r['categoria'];related='ECO-009' if cat=='fleet_purchase' else ''
        note=('Indice documentado, mas preco BEV 2038 e quantidade de compras ainda requerem homologacao' if cat=='fleet_purchase' and complete else 'Sem fonte de custo homologada para esta rubrica')
        rows.append(dict(categoria=cat,fonte_monetaria=related,indice_status=status if related else 'NAO_APLICAVEL',valor_unitario_2026_documental=converted if related and complete else '',status_homologacao='DOCUMENTAL_APROVADO_NAO_OPERACIONAL' if related and approved else 'PENDENTE',fluxos_liberados='NAO',pendencia=note,risco_dupla_contagem=r['risco_dupla_contagem']))
    pend=[dict(prioridade='P1' if cat in ('fleet_purchase','grid_energy','grid_demand','grid_connection','grid_reinforcement') else 'P2',categoria=cat,pendencia=('IPCA maio/2025 e janeiro/2026 documentados e aprovados; elegibilidade BEV 2038' if cat=='fleet_purchase' else 'Fonte, unidade, regra de incidencia e validacao especifica'),status='PENDENTE') for cat in CATS]
    if approved:pend[0]['pendencia']='Elegibilidade do preco historico para a frota de 2038 e regras de aquisicao/reposicao'
    out=root/'resultados/bau_REV032d';out.mkdir(parents=True,exist_ok=True)
    writecsv(out/'matriz_evidencias_REV032d.csv',rows,list(rows[0]))
    writecsv(out/'pendencias_homologacao_REV032d.csv',pend,list(pend[0]))
    memo=[dict(item='ECO-009',valor_fonte_brl=source_price,periodo_origem='2025-05',periodo_destino=period,indice_origem=i25 if complete else '',indice_destino=i26 if complete else '',formula='preco_fonte * indice_destino / indice_origem',valor_convertido_brl=converted if complete else '',indice_fonte=source,indice_url=url,serie=series,data_consulta=retrieval,status_indice=status,aprovacao='SIM' if approved else 'NAO',uso_em_fluxos='PROIBIDO_REV032d')]
    writecsv(out/'memoria_conversao_REV032d.csv',memo,list(memo[0]))
    report=dict(generator='REV032d_DOCUMENTED_MONETARY_APPROVAL_ONLY',classification='SYNTHETIC_EXPLORATORY',reference_month=period,index_status=status,index_complete=complete,index_approved=approved,source_price_brl_may_2025=source_price,converted_unit_price_brl_jan_2026=converted,approved_for_model=False,source_hashes={'rev032c_config':sha(c_path),'rev032c_audit':sha(audit_path),'rev032c_inventory':sha(base/'inventario_monetario_REV032c.csv'),'rev032c_rules':sha(base/'matriz_homologacao_REV032c.csv'),'rev032c_flows':sha(base/'fluxos_bloqueados_REV032c.csv')},categories=14,cost_rows=294,blocked_rows=294,F1_brl_per_pkm=None,LCOE_brl_per_kwh=None,BAU_final_approved=False,prior_revisions_modified=False,economic_status='BLOCKED_COST_SCOPE_AND_VALIDATION',notes=['Aprovacao do indice nao homologa preco tecnologico 2038','IPCA nao e projecao de custo futuro de BEV','Nenhum fluxo foi liberado; nenhuma revisao anterior foi escrita','Aprovar documento exige decisao formal e verificacao da fonte oficial'])
    (out/'auditoria_REV032d.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',default='parametros/economia_rev032d.json');args=p.parse_args();cp=Path(args.config);cp=cp if cp.is_absolute() else ROOT/cp
    print(json.dumps(run(json.loads(cp.read_text(encoding='utf-8'))),ensure_ascii=False,indent=2))
if __name__=='__main__':main()

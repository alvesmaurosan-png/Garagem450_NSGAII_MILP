"""REV03.2e: inventario economico read-only; nao libera fluxos nem altera revisoes."""
import argparse,csv,hashlib,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CATS=('fleet_purchase','fleet_maintenance','fleet_replacement','charger_purchase','charger_maintenance','charger_replacement','electrical_installation','grid_connection','grid_reinforcement','grid_energy','grid_demand','grid_charges','system_opex','residual_credit')
DETAILS={
'fleet_purchase':('P1','ECO-009; quantidade 450 BEV','Validar configuracao, escopo e elegibilidade do preco BEV para 2038; cronograma de aquisicao','VALIDACAO_DOCUMENTAL_E_DECISAO','fleet_replacement;residual_credit'),
'fleet_maintenance':('P1','450 BEV','Contrato/plano de manutencao, custo anual por veiculo e inclusoes','PESQUISA_PRECO','system_opex'),
'fleet_replacement':('P1','Horizonte 2038-2057','Vida util e calendario de substituicao; custo de reposicao sem duplicar compra inicial','DECISAO_TECNICA_E_PRECO','fleet_purchase;residual_credit'),
'charger_purchase':('P1','29 portas de recarga','Topologia e potencia nominal dos equipamentos, preco instalado ou nao instalado','ESPECIFICACAO_E_PRECO','electrical_installation'),
'charger_maintenance':('P2','29 portas de recarga','OPEX anual e itens cobertos por garantia/contrato','PESQUISA_PRECO','system_opex'),
'charger_replacement':('P2','Horizonte 20 anos','Vida util, modulos substituidos e custos futuros em reais constantes','DECISAO_TECNICA_E_PRECO','charger_purchase;residual_credit'),
'electrical_installation':('P1','Transformador selecionado 6000 kVA; pico PCC 3841,52 kW','Memorial e orcamento: transformador, cubiculos, cabos, protecoes, obras e engenharia','PROJETO_E_ORCAMENTO','charger_purchase;grid_connection'),
'grid_connection':('P1','BAU com rede ampliavel; planejamento 4225,67 kW','Parecer de acesso, capacidade existente e orcamento de conexao','EVIDENCIA_DISTRIBUIDORA','grid_reinforcement;electrical_installation'),
'grid_reinforcement':('P1','BAU sem teto PCC 2500 kW','Necessidade de obras e responsabilidade de custeio; nao presumir custo zero','EVIDENCIA_DISTRIBUIDORA','grid_connection'),
'grid_energy':('P1','Consumo AC anual 32038034,27255 kWh; serie 15 min sintetica','Tarifa horossazonal, impostos/encargos e calendario tarifario; evitar tarifa media sem justificativa','TARIFA_OFICIAL_E_MODELO','grid_charges;grid_demand'),
'grid_demand':('P1','Pico PCC 3841,52 kW','Demanda contratada e tarifa R$/kW mes; regras de ultrapassagem e modalidades','TARIFA_OFICIAL_E_CONTRATO','grid_energy;grid_charges'),
'grid_charges':('P2','Categoria economica definida','Delimitar encargos nao inclusos em energia/demanda; documentar eventuais zeros','RECONCILIACAO_CONTABIL','grid_energy;grid_demand'),
'system_opex':('P2','Categoria economica definida','Custos administrativos/seguros/operacao sem manutencoes ja contadas','PESQUISA_PRECO_E_ESCOPO','fleet_maintenance;charger_maintenance'),
'residual_credit':('P2','Horizonte termina em 2057','Vidas uteis remanescentes, metodo e credito separado, sem dupla contagem','DECISAO_METODOLOGICA','fleet_replacement;charger_replacement')}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def readcsv(p):
 with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def writecsv(p,rows,headers):
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=headers);w.writeheader();w.writerows(rows)
def run(config,root=ROOT):
 root=Path(root);dpath=root/config['rev032d_config'];d=json.loads(dpath.read_text(encoding='utf-8-sig'))
 audit_path=root/'resultados/bau_REV032d/auditoria_REV032d.json';audit=json.loads(audit_path.read_text(encoding='utf-8-sig'))
 if audit['generator']!='REV032d_DOCUMENTED_MONETARY_APPROVAL_ONLY' or audit['cost_rows']!=294 or audit['blocked_rows']!=294 or audit['F1_brl_per_pkm'] is not None or audit['LCOE_brl_per_kwh'] is not None:raise ValueError('Gate REV03.2d inconsistente')
 if audit['reference_month']!='2026-01':raise ValueError('Mes base divergente')
 memo=readcsv(root/'resultados/bau_REV032d/memoria_conversao_REV032d.csv')
 if len(memo)!=1 or memo[0]['item']!='ECO-009':raise ValueError('Memoria ECO-009 ausente')
 if audit['index_complete'] and not math.isclose(float(memo[0]['valor_convertido_brl']),audit['converted_unit_price_brl_jan_2026'],abs_tol=.0001):raise ValueError('Preco ECO-009 divergente')
 if memo[0]['uso_em_fluxos']!='PROIBIDO_REV032d':raise ValueError('Uso monetario indevidamente liberado')
 inv=readcsv(root/'resultados/bau_REV032b/inventario_mestre_REV032b.csv')
 rules=readcsv(root/'resultados/bau_REV032c/matriz_homologacao_REV032c.csv')
 if len(inv)!=10 or len(rules)!=14 or {r['categoria'] for r in rules}!=set(CATS):raise ValueError('Inventario ou regras incompletos')
 if audit['prior_revisions_modified']:raise ValueError('Integridade anterior nao confirmada')
 rows=[];gaps=[]
 for cat in CATS:
  priority,known,missing,kind,overlap=DETAILS[cat]
  row=next(r for r in rules if r['categoria']==cat)
  val= audit['converted_unit_price_brl_jan_2026'] if cat=='fleet_purchase' and audit['index_complete'] else None
  state='PRECO_ATUALIZADO_NAO_HOMOLOGADO' if val is not None else 'SEM_PRECO_HOMOLOGADO'
  item=dict(categoria=cat,prioridade=priority,drivers_disponiveis=known,preco_documental_brl_2026='' if val is None else f'{val:.6f}',estado_preco=state,regra_existente=row.get('regra',''),lacuna=missing,tipo_pendencia=kind,risco_dupla_contagem=overlap,liberado_para_fluxo='NAO',origem_documental='ECO-009/REV03.2d' if val is not None else '',observacao='Valor nao equivale a custo tecnologico homologado para 2038' if val is not None else '')
  rows.append(item)
  gaps.append(dict(prioridade=priority,categoria=cat,tipo_pendencia=kind,acao_necessaria=missing,depende_de=overlap,status='ABERTA'))
 out=root/'resultados/bau_REV032e';out.mkdir(parents=True,exist_ok=True)
 writecsv(out/'matriz_economica_consolidada_REV032e.csv',rows,list(rows[0]))
 writecsv(out/'lacunas_priorizadas_REV032e.csv',gaps,list(gaps[0]))
 writecsv(out/'inventario_ativo_referenciado_REV032e.csv',inv,list(inv[0]))
 report=dict(generator='REV032e_BAU_ECONOMIC_INVENTORY_ONLY',classification='SYNTHETIC_EXPLORATORY',source_hashes={'rev032d_config':sha(dpath),'rev032d_audit':sha(audit_path),'rev032d_memo':sha(root/'resultados/bau_REV032d/memoria_conversao_REV032d.csv'),'rev032b_inventory':sha(root/'resultados/bau_REV032b/inventario_mestre_REV032b.csv'),'rev032c_rules':sha(root/'resultados/bau_REV032c/matriz_homologacao_REV032c.csv')},active_master_records=len(inv),categories=len(rows),research_and_decision_gaps=len(gaps),documented_monetary_values=sum(bool(r['preco_documental_brl_2026']) for r in rows),homologated_cost_categories=0,cost_rows=294,blocked_rows=294,F1_brl_per_pkm=None,LCOE_brl_per_kwh=None,BAU_final_approved=False,prior_revisions_modified=False,economic_status='BLOCKED_COST_SCOPE_AND_VALIDATION',notes=['Matriz de lacunas nao implica que todas exigem pesquisa de mercado; algumas exigem decisao tecnica ou evidencia da distribuidora','IPCA documentado nao homologa preco BEV 2038','Nenhum custo, zero ou fluxo foi liberado','Nao modifica arquivos anteriores'])
 (out/'auditoria_REV032e.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 return report

def main():
 p=argparse.ArgumentParser();p.add_argument('--config',default='parametros/economia_rev032e.json');a=p.parse_args();cp=Path(a.config);cp=cp if cp.is_absolute() else ROOT/cp
 print(json.dumps(run(json.loads(cp.read_text(encoding='utf-8-sig'))),ensure_ascii=False,indent=2))
if __name__=='__main__':main()

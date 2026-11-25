#!/usr/bin/env python3
"""REV03 - NSGA-II exploratorio: MILP anual existente + F1 total sintetico documentado.
Nao altera arquivos originais. F2 usa maximo anual PCC de solucao inteira.
O atendimento a PKM nao esta certificado: Pareto e EXPLORATORIO/CONDICIONAL.
"""
import argparse, csv, hashlib, json, math, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parent
REPORTS=ROOT/'resultados/R0_REV07/R0_INTEGRACAO_OPERACIONAL'
CERT='ANNUAL_ENCODED_ELECTRICAL_INTEGER_FEASIBLE_FIXED_SELECTION'

def fronts(vals):
    n=len(vals); dominates=[[] for _ in range(n)]; degree=[0]*n; out=[]
    for i in range(n):
        for j in range(n):
            if i==j:continue
            if all(a<=b for a,b in zip(vals[i],vals[j])) and any(a<b for a,b in zip(vals[i],vals[j])):dominates[i].append(j)
            elif all(a<=b for a,b in zip(vals[j],vals[i])) and any(a<b for a,b in zip(vals[j],vals[i])):degree[i]+=1
    layer=[i for i in range(n) if degree[i]==0]
    while layer:
        out.append(layer); nxt=[]
        for i in layer:
            for j in dominates[i]:
                degree[j]-=1
                if degree[j]==0:nxt.append(j)
        layer=nxt
    return out

def crowd(layer, vals):
    distance={i:0. for i in layer}
    if len(layer)<3:return {i:float('inf') for i in layer}
    for axis in (0,1):
        ordered=sorted(layer,key=lambda i:vals[i][axis]);distance[ordered[0]]=distance[ordered[-1]]=float('inf')
        width=vals[ordered[-1]][axis]-vals[ordered[0]][axis]
        if width>0:
            for j in range(1,len(ordered)-1):distance[ordered[j]]+=(vals[ordered[j+1]][axis]-vals[ordered[j-1]][axis])/width
    return distance

def classification(report,rc,timeout):
    if timeout:return 'INCONCLUSIVO','TIMEOUT'
    if rc!=0 or not isinstance(report,dict):return 'INCONCLUSIVO','PROCESSO_OU_RELATORIO_INVALIDO'
    status=report.get('status','SEM_STATUS')
    if report.get('mode')!='anual':return 'INCONCLUSIVO','NAO_ANUAL'
    days=report.get('days',[])
    if status==CERT and report.get('annual_integer_feasibility_certified') is True and len(days)==365 and all(d.get('status')=='MILP_INTEGER_FEASIBLE' and isinstance(d.get('pcc_peak_kw'),(float,int)) and math.isfinite(d['pcc_peak_kw']) for d in days):
        return 'FACTIVEL_CODIFICADO',status
    # Nenhum status atual comprova inviabilidade inteira anual.
    return 'INCONCLUSIVO',status

def economics(x,p,grid_kwh,peak):
    rate=p['taxa_real'];h=p['horizonte_anos'];pv=lambda amount,t:amount/(1+rate)**t
    capex=p['capex_pv_bess_pcs_carregadores_referencia_brl']+sum((x[i]-p[k])*p[c] for i,k,c in ((0,'referencia_pv_kwp','custo_marginal_pv_brl_kwp'),(1,'referencia_bess_kwh','custo_marginal_bess_brl_kwh'),(2,'referencia_pcs_kw','custo_marginal_pcs_brl_kw')))
    if capex<=0:raise ValueError('CAPEX sintetico nao positivo')
    energy0=capex+p['capex_instalacao_conexao_brl']
    fleet0=p['custo_aquisicao_100_bev_brl']+p['valor_oportunidade_350_diesel_brl']
    annual_energy=grid_kwh*p['preco_eletricidade_brl_kwh']+12*peak*p['preco_demanda_brl_kw_mes']+p['custo_diesel_combustivel_anual_brl']+capex*p['opex_ativos_fracao_capex_ano']
    annual_fleet=p['custo_manutencao_diesel_anual_brl']+p['custo_manutencao_bev_anual_brl']
    ve=energy0;vf=fleet0
    for t in range(1,h+1):ve+=pv(annual_energy,t);vf+=pv(annual_fleet,t)
    for t in p['anos_reposicao_diesel']:vf+=pv(p['custo_reposicao_350_diesel_brl'],t)
    for t in p['anos_reposicao_bev']:vf+=pv(p['custo_reposicao_100_bev_brl']-p['credito_residual_bev_brl'],t)
    vf-=pv(p['credito_residual_bev_brl'],h)
    ve-=pv(capex*p['residual_ativos_fracao_capex_ano20'],h)
    denom=sum(pv(p['pkm_anual_requisito'],t) for t in range(1,h+1))
    return {'f1_total_brl_pkm':(ve+vf)/denom,'f1_energia_brl_pkm':ve/denom,'f1_frota_brl_pkm':vf/denom,'vp_energia_brl':ve,'vp_frota_brl':vf,'vp_pkm_requisito':denom,'grid_kwh_ano':grid_kwh,'capex_ativos_brl':capex}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pop',type=int,default=4);ap.add_argument('--geracoes',type=int,default=1)
    ap.add_argument('--seed',type=int,default=42);ap.add_argument('--timeout',type=int,default=7200)
    ap.add_argument('--tempo-lp',type=float,default=60);ap.add_argument('--tempo-milp',type=float,default=90)
    ap.add_argument('--max-iter',type=int,default=30);ap.add_argument('--variacao',type=float,default=.05)
    ap.add_argument('--pcc-min-kw',type=float,default=1800.)
    ap.add_argument('--selecao-json',default='');ap.add_argument('--premissas',default='premissas_sinteticas_rev01.json')
    ap.add_argument('--preflight',action='store_true');ap.add_argument('--executar',action='store_true',help='Autoriza chamadas custosas do MILP anual')
    a=ap.parse_args()
    if not 0<a.pcc_min_kw<=2500:ap.error('pcc-min-kw invalido')
    if a.pop<4 or a.geracoes<1 or not 0<a.variacao<.5:ap.error('pop>=4, geracoes>=1, 0<variacao<0.5')
    p=json.loads((ROOT/a.premissas).read_text(encoding='utf8'))
    if p['natureza']!='SINTETICA_EXPLORATORIA_NAO_HOMOLOGADA':ap.error('Premissas nao identificadas como sinteticas')
    for k in ('custo_diesel_combustivel_anual_brl','custo_manutencao_diesel_anual_brl','custo_manutencao_bev_anual_brl'):
        if p[k] is None:ap.error('Rubrica sem valor: '+k)
    required=[ROOT/'r0_integracao_operacional_rev03.py',ROOT/'dados/processados/dia_sintetico_450_sessoes_REV01.csv',ROOT/'resultados/R0_REV07/G4_B1/contrato_energia_G4B1.csv']
    missing=[str(q.relative_to(ROOT)) for q in required if not q.is_file()]
    print(json.dumps({'modo':'PREFLIGHT' if not a.executar else 'EXECUCAO','premissas':'SINTETICAS','faltantes':missing,'servico_pkm_certificado':False,'f1':'TOTAL_FROTA_ENERGIA','f2':'PCC_ANUAL_INTEIRO'},ensure_ascii=False))
    if missing:ap.error('Arquivos necessarios ausentes')
    if not a.executar:return
    center=np.array([p['referencia_pv_kwp'],p['referencia_bess_kwh'],p['referencia_pcs_kw']],float)
    rng=np.random.default_rng(a.seed);cache={};population=[np.r_[center,2500.]]
    out=ROOT/'resultados/NSGAII_MILP_EXPLORATORIO_REV03';out.mkdir(parents=True,exist_ok=True)
    lower=np.r_[center*(1-a.variacao),a.pcc_min_kw];upper=np.r_[center*(1+a.variacao),2500.]
    def clip(x):return np.clip(x,lower,upper)
    def eval(x):
        key=','.join(f'{z:.8f}' for z in x)
        if key in cache:return cache[key]
        signature=json.dumps({'revision':'REV03','key':key,'seed':a.seed,'selecao':a.selecao_json,'premissas':p},sort_keys=True)
        tag='nsga03_'+hashlib.sha256(signature.encode()).hexdigest()[:16]
        reportpath=REPORTS/f'resultado_{tag}.json'
        rec={'run_id':tag,'pv_kwp':float(x[0]),'bess_kwh':float(x[1]),'pcs_kw':float(x[2]),'pcc_alvo_kw':float(x[3]),'status':'INCONCLUSIVO','motivo':None,'f1_total_brl_pkm':None,'f1_energia_brl_pkm':None,'f1_frota_brl_pkm':None,'f2_pcc_kw':None,'servico_pkm_certificado':False,'pareto_condicional':False}
        if reportpath.exists():
            # Reuso somente de relatorio ja concluido e assinatura identica; nunca sobrescrever.
            report=json.loads(reportpath.read_text(encoding='utf8'))
            if report.get('status')!=CERT:rec['motivo']='RELATORIO_PREEXISTENTE_NAO_CONCLUIDO';cache[key]=rec;return rec
            rc=0;timed_out=False
        else:
            cmd=[sys.executable,str(ROOT/'r0_integracao_operacional_rev03.py'),'--modo','anual','--n-bev',str(p['n_bev']),'--pv-kwp',str(x[0]),'--bess-kwh',str(x[1]),'--pcs-kw',str(x[2]),'--tempo-lp-diario',str(a.tempo_lp),'--tempo-milp',str(a.tempo_milp),'--max-iter',str(a.max_iter),'--run-id',tag,'--pcc-alvo-kw',str(x[3]),'--preco-energia-brl-kwh',str(p['preco_eletricidade_brl_kwh'])]
            if a.selecao_json:cmd+=['--selecao-json',str(Path(a.selecao_json).resolve())]
            timed_out=False;rc=None
            with (out/f'{tag}.log').open('x',encoding='utf8') as log:
                try:rc=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=a.timeout).returncode
                except subprocess.TimeoutExpired:timed_out=True
            try:report=json.loads(reportpath.read_text(encoding='utf8')) if reportpath.exists() else None
            except (OSError,ValueError):report=None
        rec['status'],rec['motivo']=classification(report,rc,timed_out)
        if rec['status']=='FACTIVEL_CODIFICADO':
            try:
                grid=0.
                for day in range(365):
                    with np.load(REPORTS/f'{tag}_dia_{day:03d}.npz',allow_pickle=False) as data:
                        v=np.asarray(data['grid_kw'],float)
                        if len(v)!=96 or not np.all(np.isfinite(v)) or np.min(v)<-1e-6:raise ValueError('Perfil de rede invalido')
                        grid+=float(v.sum())*.25
                peak=max(float(d['pcc_peak_kw']) for d in report['days'])
                if peak > x[3]+1e-3:raise ValueError('Pico excede teto operacional')
                op=float(report.get('custo_operacional_anual_brl',float('nan')))
                if not math.isfinite(op) or abs(op-grid*p['preco_eletricidade_brl_kwh'])>max(1.,abs(op))*1e-5:
                    raise ValueError('Custo do MILP nao reconciliado com energia importada')
                rec.update(economics(x,p,grid,peak));rec['f2_pcc_kw']=peak;rec['pareto_condicional']=True
                rec['custo_operacional_milp_brl']=op
                rec['otimalidade_inteira_anual_certificada']=False
            except Exception as exc:
                rec['status']='INCONCLUSIVO';rec['motivo']='ERRO_ECONOMICO_OU_SERIES:'+str(exc);rec['pareto_condicional']=False
        cache[key]=rec
        (out/'avaliacoes.json').write_text(json.dumps(list(cache.values()),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
        print(f"{len(cache)} | {rec['status']} | {rec['motivo']} | F1={rec['f1_total_brl_pkm']} | F2={rec['f2_pcc_kw']}",flush=True)
        return rec
    def select(pool):
        unique=list(dict((','.join(f'{v:.8f}' for v in x),x) for x in pool).values())
        good=[x for x in unique if eval(x)['pareto_condicional']]
        bad=[x for x in unique if not eval(x)['pareto_condicional']]
        vals=[(eval(x)['f1_total_brl_pkm'],eval(x)['f2_pcc_kw']) for x in good]
        chosen=[]
        for layer in fronts(vals):
            cd=crowd(layer,vals)
            chosen.extend(good[i] for i in sorted(layer,key=lambda i:cd[i],reverse=True)[:a.pop-len(chosen)])
            if len(chosen)>=a.pop:break
        chosen.extend(bad[:a.pop-len(chosen)])
        return chosen[:a.pop]
    while len(population)<a.pop:population.append(clip(np.r_[center*(1+rng.uniform(-a.variacao,a.variacao,3)),rng.uniform(a.pcc_min_kw,2500.)]))
    for gen in range(a.geracoes):
        print(f'GERACAO {gen+1}/{a.geracoes}',flush=True)
        for x in population:eval(x)
        if gen+1==a.geracoes:break
        children=[]
        while len(children)<a.pop:
            i,j=rng.integers(len(population),size=2);alpha=rng.random(4)
            children.append(clip(alpha*population[i]+(1-alpha)*population[j]+rng.normal(0,.01,4)*(upper-lower)))
        for x in children:eval(x)
        population=select(population+children)
    records=list(cache.values()); fields=list(dict.fromkeys(k for r in records for k in r))
    with (out/'candidatos.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(records)
    good=[r for r in records if r['pareto_condicional']]
    front=[good[i] for i in fronts([(r['f1_total_brl_pkm'],r['f2_pcc_kw']) for r in good])[0]] if good else []
    with (out/'pareto_condicional.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(front)
    print(f'AVALIADOS={len(records)} FACTIVEIS_CODIFICADOS={len(good)} PARETO_CONDICIONAL={len(front)}')
    print('ATENCAO: F1 sintetico; PKM nao certificado; LP anual coordenado economicamente; otimo inteiro anual nao certificado.')
if __name__=='__main__':main()

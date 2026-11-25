"""Pós-processamento da release REV04 + CGOB REV04.1; não chama solver."""
import argparse, hashlib, json
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--raiz',type=Path,default=Path(__file__).resolve().parent)
p.add_argument('--saida',type=Path,default=Path('resultados/GRAFICOS_CONSOLIDADOS_REV041'))
a=p.parse_args(); root=a.raiz.resolve(); r=root/'resultados'; out=root/a.saida
out.mkdir(parents=True,exist_ok=True)
sources={}; generated=[]
def read(path):
    sources[str(path.relative_to(root))]=hashlib.sha256(path.read_bytes()).hexdigest()
    return pd.read_csv(path)
def save(name,title,ylabel,xlabel='Configuração'):
    plt.title(title); plt.ylabel(ylabel); plt.xlabel(xlabel); plt.grid(axis='y',alpha=.22); plt.tight_layout()
    for ext in ('png','svg'):
        path=out/f'{name}.{ext}'; plt.savefig(path,dpi=300,bbox_inches='tight'); generated.append(path.name)
    plt.close()
def bar(name,title,col,unit,scale=1,df=None):
    d=c if df is None else df; v=d[col]/scale
    plt.figure(figsize=(8,4.5)); b=plt.bar(d.config,v); plt.bar_label(b,fmt='%.3g',padding=3); plt.margins(y=.15); save(name,title,unit)
def stack(name,title,cols,labels,unit,scale=1,percent=False):
    d=c.set_index('config')[cols]/scale; d.columns=labels
    if percent: d=d.div(d.sum(axis=1),axis=0)*100
    d.plot.bar(stacked=True,figsize=(8,4.5),rot=0); plt.legend(); save(name,title,unit)
c=read(r/'consolidado_REV04/comparativo.csv').set_index('config').loc[['BAU','R0','R1','R2']].reset_index()
e=read(r/'CGOB_REV041/comparativo_ambiental.csv'); s=read(r/'CGOB_REV041/sensibilidade_cgob.csv'); l=read(r/'CGOB_REV041/limiares_cobertura.csv')
for col in ['F1','F2','LCOE']:
    assert ((e.set_index('config').loc[c.config,col].to_numpy()-c[col].to_numpy()).__abs__()<1e-7).all(),col
for name,title,col,unit,scale in [
('01_F1','Custo descontado por passageiro-quilômetro','F1','R$/PKM',1),('02_F2','Pico efetivo de importação','F2','kW',1),('03_LCOE','LCOE da eletricidade de tração','LCOE','R$/kWh',1),('04_CAPEX','Investimento inicial','CAPEX','R$ milhões',1e6),('05_OPEX','Custo operacional anual','OPEX','R$ milhões/ano',1e6),('06_VP','Valor presente dos custos','VP_total','R$ milhões',1e6),('08_PV','Potência fotovoltaica','pv_kwp','kWp',1),('09_BESS','Capacidade nominal BESS','bess_kwh','MWh',1000),('10_PCS','Potência PCS','pcs_kw','kW',1),('11_CHP','Módulos CHP','chp_modules','Módulos',1),('12_Portas','Portas de recarga','ports','Portas',1),('13_Producao_biogas','Capacidade de produção de biogás','gas_production_nm3h','Nm³/h',1),('14_Armazenamento_biogas','Capacidade de armazenamento de biogás','gas_storage_nm3','Nm³',1),('17_Recarga_DC','Energia anual de recarga DC','charge_dc_kwh','GWh/ano',1e6),('18_Compressao','Energia elétrica de compressão','compressao_kwh','GWh/ano',1e6),('19_Diesel','Consumo anual de diesel','diesel_l','Milhões L/ano',1e6),('20_GN','Consumo anual de gás veicular','gas_bus_nm3','Milhões Nm³/ano',1e6),('21_Substrato','Consumo anual de substrato','substrate_t','t/ano',1),('22_CO2_fisico','CO₂ fóssil operacional estimado','CO2_operacional_t_ano','t CO₂/ano',1),('23_Intensidade_fisica','Intensidade fóssil operacional','CO2_g_PKM','g CO₂/PKM',1)]: bar(name,title,col,unit,scale)
stack('07_Frota','Composição da frota',['n_bev','n_diesel','n_gas'],['BEV','Diesel','GAS-BUS'],'Ônibus')
for pct in (False,True): stack('16_Matriz_percentual' if pct else '15_Matriz_energia','Suprimento elétrico anual',['grid_kwh','pv_kwh','chp_net_kwh'],['Rede','PV','CHP líquido'],'%' if pct else 'GWh/ano',1e6,pct)
bar('24_CGOB_atribuicao','R2: indicador atribuído hipotético (não inventário físico)','CO2_fossil_t_ano','t CO₂/ano',df=e[e.config=='R2-CGOB'])
plt.figure(figsize=(8,4.5)); plt.plot(s.cobertura_hipotetica_pct,s.CO2_fossil_atribuido_t_ano,'o-',label='R2 atribuição hipotética')
for _,row in c[c.config!='R2'].iterrows(): plt.axhline(row.CO2_operacional_t_ano,ls='--',label=row.config+' físico')
plt.legend(); save('25_CGOB_sensibilidade','Sensibilidade contábil (não redução física)','t CO₂/ano','Cobertura hipotética (%)')
plt.figure(figsize=(8,4.5)); plt.bar(l.referencia,l.cobertura_pct); plt.ylim(0,100); save('26_CGOB_limiares','Cobertura para equivalência numérica de indicadores','%','Referência')
rev1=r/'CONSOLIDADO_FINAL_REV01_20261124_200032'; rev2=r/'CONSOLIDADO_FINAL_REV02_20261124_215315'; rev4=r/'NSGAII_FINAL_REV04_20261125_010610'
fronts={k:read(folder/f'pareto_{k}.csv') for k,folder in [('R0',rev1),('R1',rev4),('R2',rev2)]}
plt.figure(figsize=(8,5));
for k,d in fronts.items(): plt.scatter(d.F2,d.F1,label=k,s=25)
plt.scatter(c.F2,c.F1,marker='*',s=100,label='Representativas'); plt.legend(); save('27_Pareto_comparativo','Pontos não dominados por rota e soluções representativas','F1 (R$/PKM)','F2 (kW)')
for k,d in fronts.items():
    plt.figure(figsize=(8,4.5)); plt.scatter(d.F2,d.F1); save('28_Pareto_'+k,'Fronteira observada '+k,'F1 (R$/PKM)','F2 (kW)')
lp=read(rev4/'avaliacoes_LP.csv'); milp=read(rev4/'avaliacoes_MILP.csv')
plt.figure(figsize=(8,4.5)); lp.status.value_counts().plot.bar(rot=15); save('29_R1_status_LP','Classificação das avaliações LP — R1','Avaliações','Status')
plt.figure(figsize=(8,4.5)); plt.scatter(lp.F2,lp.F1,s=9,alpha=.4,label='LP'); plt.scatter(milp.F2,milp.F1,marker='x',label='MILP anual validado'); plt.legend(); save('30_R1_LP_MILP','Triagem LP e soluções anuais R1','F1 (R$/PKM)','F2 (kW)')
d=read(rev4/'despacho_4.csv'); assert len(d)==35040
h=d.index/4; day=h/24
plt.figure(figsize=(10,4.5)); plt.plot(day,d.grid_kw,lw=.6); plt.axhline(2500,ls='--',label='Teto PCC'); plt.legend(); save('31_R1_PCC_anual','R1 ID4 — importação anual','kW','Dia do ano')
plt.figure(figsize=(8,4.5)); plt.plot(h,sorted(d.grid_kw,reverse=True)); save('32_R1_duracao_PCC','R1 ID4 — curva de duração','kW','Horas acumuladas')
for name,col,title,unit in [('33_R1_SOC_BESS','bess_kwh','Energia armazenada BESS','kWh'),('34_R1_Estoque_biogas','gas_store_nm3','Estoque de biogás','Nm³')]:
    plt.figure(figsize=(10,4.5)); plt.plot(day,d[col],lw=.6); save(name,'R1 ID4 — '+title,unit,'Dia do ano')
peak=int(d.grid_kw.idxmax())//96; q=d.iloc[peak*96:(peak+1)*96]; plt.figure(figsize=(10,4.5))
for col,label,factor in [('grid_kw','Rede',1),('pv_kw','PV',1),('chp_gross_kw','CHP líquido',.95),('charge_kw','Carga BESS',1),('discharge_kw','Descarga BESS',1),('demand_kw','Demanda',1)]: plt.plot(range(96),q[col]*factor,label=label)
plt.xticks(range(0,96,12),range(0,24,3)); plt.legend(ncol=3); save('35_R1_despacho_dia_pico',f'R1 ID4 — despacho no dia {peak+1} (pico PCC)','kW','Hora local')
(out/'manifesto_graficos.json').write_text(json.dumps({'fontes_sha256':sources,'arquivos':generated,'solver_executado':False,'ressalvas':['R0 e R2: dias representativos; R1: cronologia anual.','CGOB: atribuição hipotética, sem redução física comprovada.','Fronteiras observadas por rota, sem interpolação ou certificação de ótimo global.']},ensure_ascii=False,indent=2),encoding='utf-8')
print(f'PASS: {len(generated)//2} gráficos em PNG e SVG: {out}')

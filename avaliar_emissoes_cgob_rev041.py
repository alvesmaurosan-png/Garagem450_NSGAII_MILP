"""Pós-processamento REV04.1: não executa solver nem altera REV04."""
import argparse, csv, json, hashlib, math
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cobertura', type=float, default=100, help='Cobertura hipotética em percentual')
    a = p.parse_args()
    if not 0 <= a.cobertura <= 100:
        p.error('Cobertura deve estar entre 0 e 100')
    root = Path(__file__).resolve().parent
    source = root / 'resultados/consolidado_REV04/comparativo.csv'
    prem = root / 'premissas_sinteticas_rev01.json'
    with source.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    if sorted(r['config'] for r in rows) != ['BAU','R0','R1','R2']:
        raise ValueError('Esperada uma solução representativa por cenário')
    r = next(r for r in rows if r['config']=='R2')
    gas = float(r['gas_bus_nm3']); grid = float(r['grid_kwh'])
    original = float(r['CO2_operacional_t_ano'])
    fossil = gas*2/1000; electricity = grid*.1/1000
    if not math.isclose(original, fossil+electricity, rel_tol=1e-9):
        raise ValueError('Inventário original R2 não reconciliado')
    pkm = original*1e6/float(r['CO2_g_PKM'])
    for row in rows:
        if not math.isclose(float(row['CO2_operacional_t_ano'])*1e6/float(row['CO2_g_PKM']), pkm, rel_tol=1e-9):
            raise ValueError('Denominador PKM inconsistente')
    out = root / 'resultados/CGOB_REV041'; out.mkdir(parents=True, exist_ok=True)
    def write(name, records):
        with (out/name).open('w', encoding='utf-8-sig', newline='') as f:
            w=csv.DictWriter(f, fieldnames=list(records[0])); w.writeheader(); w.writerows(records)
    def adjusted(c): return electricity+fossil*(1-c/100)
    sensitivity=[dict(cobertura_hipotetica_pct=c,volume_equivalente_nm3=gas*c/100,CO2_fossil_atribuido_t_ano=adjusted(c),CO2_fossil_atribuido_g_PKM=adjusted(c)*1e6/pkm) for c in sorted(set([0,25,50,75,90,95,100,a.cobertura]))]
    write('sensibilidade_cgob.csv',sensitivity)
    comparison=[]
    for row in rows:
        comparison.append(dict(config=row['config'],F1=row['F1'],F2=row['F2'],LCOE=row['LCOE'],CO2_fossil_t_ano=row['CO2_operacional_t_ano'],CO2_fossil_g_PKM=row['CO2_g_PKM'],natureza='inventario_REV04'))
    comparison.append(dict(config='R2-CGOB',F1=r['F1'],F2=r['F2'],LCOE=r['LCOE'],CO2_fossil_t_ano=adjusted(a.cobertura),CO2_fossil_g_PKM=adjusted(a.cobertura)*1e6/pkm,natureza='atribuicao_hipotetica_condicionada'))
    write('comparativo_ambiental.csv',comparison)
    write('limiares_cobertura.csv',[dict(referencia=row['config'],cobertura_pct=100*(1-(float(row['CO2_operacional_t_ano'])-electricity)/fossil)) for row in rows if row['config']!='R2'])
    audit=dict(status='PASS_RECONCILIACAO_ARITMETICA',fonte=str(source.relative_to(root)),sha256=hashlib.sha256(source.read_bytes()).hexdigest(),pkm_ano=pkm,gas_nm3_ano=gas,fator_gn_kg_nm3=2,fator_rede_kg_kwh=.1,CO2_original_t_ano=original,CO2_rede_t_ano=electricity,cobertura_hipotetica_pct=a.cobertura,CO2_atribuido_t_ano=adjusted(a.cobertura),CO2_biogenico_t_ano=None,CGOB_aquisicao_cancelamento_verificados=False,metodologia_atribuicao_validada=False,solver_executado=False,ressalva='Nao altera inventario fisico. Atribuicao hipotetica depende de metodologia aplicavel, equivalencia energetica, rastreabilidade e ausencia de dupla contagem. CO2 biogenico nao quantificado; sem ACV, CH4 ou N2O. Economia preservada; nao valida preco ou cobertura efetiva.')
    (out/'auditoria_cgob.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'PASS: R2 original = {original:.2f} t/ano; R2-CGOB hipotetico ({a.cobertura:g}%) = {adjusted(a.cobertura):.2f} t/ano')
    print('Resultados:',out)

if __name__=='__main__': main()

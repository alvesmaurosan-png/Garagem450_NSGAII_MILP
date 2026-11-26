(.venv) PS C:\Users\SN72755\PycharmProjects\Garagem450_NSGAII_MILP_GitHub\Garagem450_NSGAII_MILP> if ($dialog.ShowDialog() -eq "OK") {
>>     Copy-Item -LiteralPath $dialog.FileName `
>>         -Destination ".\docs\relatorio_final\Relatorio_Tecnico_Cientifico_Final_REV042_Garagem450.docx"
>>
>>     Write-Host "Relatorio incorporado." -ForegroundColor Green
>> }
"""REV04.2: sensibilidade de precos, configuracao fixa; nenhum solver."""
import argparse, csv, hashlib, json, math, itertools
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--gn', nargs='+', type=float, default=[2.4,2.6,3,3.1068,4,5])
    p.add_argument('--cgob', nargs='+', type=float, default=[0,.1,.25,.5,.75,1,1.4,2])
    p.add_argument('--cobertura', nargs='+', type=float, default=[100])
    a=p.parse_args()
    if any(not math.isfinite(x) or x<0 for x in a.gn+a.cgob+a.cobertura) or max(a.cobertura)>100: p.error('Precos nao negativos e cobertura entre 0 e 100.')
    root=Path(__file__).resolve().parent
    src=root/'resultados/consolidado_REV04/comparativo.csv'; prem=root/'premissas_sinteticas_rev01.json'
    with src.open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    if sorted(r['config'] for r in rows)!=['BAU','R0','R1','R2']: raise ValueError('Cenarios inesperados')
    d={r['config']:r for r in rows}; r=d['R2']; q=json.loads(prem.read_text(encoding='utf-8-sig'))
    n=q['horizonte_anos']; rate=q['taxa_real']; k=q['pkm_anual_requisito']; af=sum((1+rate)**-t for t in range(1,n+1)); den=k*af
    v=float(r['gas_bus_nm3']); f0=float(r['F1']); vp=float(r['VP_total']); op=float(r['OPEX']); base=3.1
    if n!=20 or v<=0 or not math.isclose(vp/den,f0,rel_tol=1e-9): raise ValueError('Base economica nao reconciliada')
    for x in rows:
        if not math.isclose(float(x['VP_total'])/den,float(x['F1']),rel_tol=1e-9): raise ValueError('F1 inconsistente: '+x['config'])
    refs={s:float(d[s]['F1']) for s in ['BAU','R0','R1']}
    def calc(g,c,b):
        total=g+c*b/100; delta=v*(total-base); newvp=vp+delta*af; f=newvp/den
        return dict(GN_brl_nm3=g,CGOB_brl_nm3_equivalente=c,cobertura_pct=b,preco_total_brl_nm3=total,custo_GN_anual=g*v,custo_CGOB_anual=c*b/100*v,delta_OPEX=delta,OPEX=op+delta,VP_total=newvp,F1=f,F2=float(r['F2']),LCOE=float(r['LCOE']),CAPEX=float(r['CAPEX']),**{f'delta_F1_{s}_pct':100*(f/y-1) for s,y in refs.items()},menor_F1_estrito=f<min(refs.values()))
    original=calc(3,.1,100)
    if not math.isclose(original['F1'],f0,rel_tol=1e-12) or original['VP_total']!=vp: raise ValueError('Caso base nao reproduzido')
    gs=sorted(set(a.gn+[3])); cs=sorted(set(a.cgob+[.1])); bs=sorted(set(a.cobertura+[100])); records=[calc(g,c,b) for g,c,b in itertools.product(gs,cs,bs)]
    limits=[]
    for g,b,s in itertools.product(gs,bs,refs):
        total=base+(refs[s]-f0)*k/v
        limits.append(dict(referencia=s,GN_brl_nm3=g,cobertura_pct=b,preco_total_equilibrio=total,CGOB_equilibrio=(total-g)/(b/100) if b else None,situacao='SEM_PREMIO_COMPETITIVO' if g>total else ('COBERTURA_ZERO' if b==0 else 'LIMIAR_CALCULADO')))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    out=root/'resultados/SENSIBILIDADE_ECONOMICA_REV042'; out.mkdir(parents=True,exist_ok=True)
    def write(name,rr):
        with (out/name).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rr[0])); w.writeheader(); w.writerows(rr)
    write('sensibilidade_gn_cgob.csv',records); write('sensibilidade_cgob_gn_fixo.csv',[calc(3,c,100) for c in cs]); write('limiares_competitividade.csv',limits)
    def save(name):
        plt.tight_layout()
        for ext in ['png','svg']: plt.savefig(out/f'{name}.{ext}',dpi=300)
        plt.close()
    plt.figure(figsize=(9,5));
    for g in gs: plt.plot(cs,[calc(g,c,100)['F1'] for c in cs],marker='o',label=f'GN R$ {g:g}')
    for s,y in refs.items(): plt.axhline(y,linestyle='--',label=s)
    plt.xlabel('Premio CGOB (R$/Nm³ equivalente)'); plt.ylabel('F1 (R$/PKM)'); plt.title('R2 fixa — cobertura hipotetica integral'); plt.legend(ncol=2,fontsize=8); plt.grid(alpha=.2); save('01_F1_sensibilidade')
    # Grafico complementar: GN fixo em R$ 3,00/Nm3
    fig, ax = plt.subplots(figsize=(11, 6))

    x_cgob = [i / 100 for i in range(651)]
    y_f1 = [calc(3.0, p, 100)['F1'] for p in x_cgob]

    ax.plot(
        x_cgob, y_f1,
        color='#187E69',
        linewidth=2.8,
        label='R2 fixa'
    )

    cores = {
        'R0': '#1F77B4',
        'BAU': '#D62728',
        'R1': '#FF7F0E'
    }

    for s in ['R0', 'BAU', 'R1']:
        ax.axhline(
            refs[s],
            color=cores[s],
            linestyle='--',
            linewidth=2.0,
            label=s
        )

    ax.axvline(
        x=1.40,
        color='#808080',
        linestyle=':',
        linewidth=2.0,
        label='Ref. atributo ambiental (R$ 1,40/Nm\u00b3)'
    )

    ax.set_xlim(0, 6.5)
    ax.set_xlabel('CGOB (R$/Nm\u00b3 equivalente)', fontsize=12)
    ax.set_ylabel('F1 (R$/PKM)', fontsize=12)
    ax.tick_params(labelsize=11)
    ax.grid(True, alpha=0.20)
    ax.set_axisbelow(True)

    ax.legend(
        loc='upper center',
        bbox_to_anchor=(0.5, -0.19),
        ncol=3,
        fontsize=10,
        frameon=False,
        handlelength=3.5,
        columnspacing=1.8,
        labelspacing=0.8
    )

    fig.subplots_adjust(bottom=0.29)

    save('04_F1_CGOB_GN_fixo')

    plt.figure(figsize=(9,5)); plt.plot(cs,[calc(3,c,100)['custo_CGOB_anual']/1e6 for c in cs],marker='o'); plt.xlabel('Premio CGOB (R$/Nm³ equivalente)'); plt.ylabel('Custo anual (R$ milhoes)'); plt.title('Custo incremental do atributo — cobertura integral'); plt.grid(alpha=.2); save('02_custo_CGOB')
    plt.figure(figsize=(9,5));
    for s,y in refs.items(): plt.plot(gs,[base+(y-f0)*k/v-g for g in gs],marker='o',label=s)
    plt.axhline(0,color='black',linewidth=.8); plt.xlabel('Preco GN (R$/Nm³)'); plt.ylabel('Premio CGOB de equilibrio (R$/Nm³ equivalente)'); plt.title('Limiares economicos — cobertura integral'); plt.legend(); plt.grid(alpha=.2); save('03_limiares')
    audit=dict(status='PASS_RECONCILIACAO_ARITMETICA',solver_executado=False,configuracao_fixa=True,precos_validados=False,base_GN=3,base_CGOB=.1,base_cobertura_pct=100,pkm_ano=k,gas_nm3_ano=v,taxa_real=rate,horizonte=n,fator_vp=af,caso_base=original,numero_casos=len(records),fontes={str(x.relative_to(root)):hashlib.sha256(x.read_bytes()).hexdigest() for x in [src,prem]},ressalvas=['Precos em BRL constantes jan/2026 assumidos; sem harmonizacao tributaria ou metrologica das referencias externas.','Premio por Nm3 equivalente e cobertura energetica aproximada por volume; nao representa cotacao de certificado.','R$ 3,10 consta no consolidador REV02; decomposicao 3,00 + 0,10 e hipotese do estudo.','LCOE eletrico de tracao, CAPEX e F2 invariantes; nenhuma reotimizacao ou validacao ambiental.'])
    (out/'auditoria_sensibilidade.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False),encoding='utf-8')
    print('PASS: caso base reconciliado; nenhum solver executado.')
    for c in [.1,1,1.4,2]: print(f'GN=3 CGOB={c:g}: F1={calc(3,c,100)["F1"]:.6f}')
    print('Casos:',len(records),'\nResultados:',out)
if __name__=='__main__': main()

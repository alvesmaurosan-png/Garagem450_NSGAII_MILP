# Garagem450 — Consolidação G06 e auditoria final de prontidão G08

**Data:** 15/11/2026  
**Escopo:** BAU sintético, 450 ônibus BEV; preços reais constantes de janeiro/2026; horizonte 2038–2057; taxa real 8% a.a.  
**Natureza:** fechamento econômico derivado e auditoria de prontidão; sem reexecução de MILP/NSGA-II; sem alterações na Base Mestre, parâmetros ou resultados congelados.

## 1. Decisões sintéticas aprovadas (G03–G07)

- **G03:** 29 carregadores × R$ 226.447,05 = **R$ 6.566.964,45**, alocados em t=0; valor convencional jan/2026 sem IPCA adicional. Por aprovação expressa, aquisição dos carregadores é independente de instalação e conexão, como **convenção de escopo**, não comprovação contratual. Diferença técnica 150 kW (benchmark) versus 138 kW (modelo) permanece declarada.
- **G04:** manter manutenção congelada da frota; nenhum OPEX incremental não documentado no perímetro sintético. Isso não afirma custo real zero.
- **G05:** manter somente TE/TUSD de energia e demanda já calculadas, bandeira verde, sem componentes adicionais; não representa fatura integral real.
- **G06:** recuperação econômica de 50% da fração linear de vida útil remanescente; ônibus L=12 anos, instalações L=25 anos, carregadores L=20 anos, conexão L=30 anos **mas não recuperável**; carregadores sem reposição. Frota original substituída no início de 2048 (t=10); frota substituta e demais ativos avaliados no fim de 2057 (t=20).
- **G07:** PKM anual sintético constante de 569.130.934,0742, 20 fluxos em fim de ano, descontados a 8%; convenção, não demanda empiricamente observada.

## 2. Fórmula residual e cronologia

`VR_i = C_i × max(0, 1 − A_i/L_i) × α_i`, com `α_i = 0,50` para ativos recuperáveis. Conexão tem elegibilidade de recuperação **não**, portanto crédito zero **por decisão explícita**, não por omissão. Carregadores têm fração remanescente zero após 20 anos, também sem crédito.

| Ativo/evento | Momento VP | Crédito nominal (R$) | Crédito em VP (R$) |
|---|---:|---:|---:|
| Frota original retirada 2048 | t=10 | 106.868.291,58 | 49.500.696,74 |
| Frota substituta fim 2057 | t=20 | 106.868.291,58 | 22.928.400,39 |
| Instalações elétricas fim 2057 | t=20 | 150.131,24 | 32.210,39 |
| Carregadores DC fim 2057 | t=20 | 0,00 | 0,00 |
| Conexão elétrica fim 2057 | t=20 | 0,00 | 0,00 |
| **Total** | | **213.886.714,40** | **72.461.307,52** |

A reposição da frota em 2048 é custo positivo no **início** do ano, t=10. O fluxo operacional de 2048 é fim de ano, t=11. A alienação da frota original ocorre em t=10; não descontar novamente em t=11.

## 3. Ponte econômica derivada (não sobrescreve REV03.2g.9)

| Rubrica | R$ em valor presente |
|---|---:|
| VP parcial condicionado original (congelado) | 2.702.683.343,20 |
| Aquisição dos 29 carregadores (G03, t=0) | + 6.566.964,45 |
| **Ponte antes dos créditos** | **2.709.250.307,65** |
| Créditos residuais G06 (t=10 e t=20) | − 72.461.307,52 |
| **VP líquido derivado do BAU sintético** | **2.636.789.000,14** |

VP(PKM) de conferência: **5.587.811.404,88 passageiros·km**, usando fator de anuidade `9.818147407449291`. O denominador é sintético e não foi reestimado.

## 4. Auditoria independente de consistência G08

| Teste | Resultado |
|---|---|
| 20 linhas anuais e anos 2038–2057 | PASS |
| t operacional 1–20 | PASS |
| 14 rubricas únicas | PASS |
| VP OPEX confere com auditoria | PASS |
| CAPEX instalação + conexão | PASS |
| VP documentado congelado | PASS |
| VP condicionado congelado | PASS |
| Reposição 2048 descontada t10 | PASS |
| Rubrica compra carregador não integrada previamente | PASS |
| Fator VP(PKM) = soma 20 anos | PASS |

### Verificações qualitativas e limites

- **PASS — consistência interna:** todas as 14 rubricas identificadas; fluxos 2038–2057, t=1..20, reconciliados com a auditoria congelada; custos iniciais e reposição preservados; residual calculado sem alterar os originais.
- **PASS — convenções de escopo:** G03–G06 possuem aprovação expressa, incluindo ausência sintética de sobreposição, fronteira OPEX/fatura e elegibilidade de residual.
- **LIMITAÇÃO — documentação externa:** a separação instalação versus carregadores é premissa sintética, não verificação de contratos; instalação e conexão são proxies exploratórias; preço de frota e tarifa mantêm ressalvas de origem; valores de recuperação não são preços de revenda observados.
- **LIMITAÇÃO — comparabilidade:** o presente fechamento é apenas do **BAU**. Não foi demonstrada neste pacote a aplicação da mesma fronteira econômica, convenções residuais e PKM aos demais cenários ou a consistência de interfaces com NSGA-II/MILP.
- **LIMITAÇÃO — dados de origem:** os arquivos ZIP contêm saídas econômicas resumidas, não a totalidade das séries físicas e das fontes tarifárias originais. Assim, a auditoria confirma coerência aritmética e decisões aprovadas, **não** revalida empiricamente as entradas.

## 5. Parecer de liberação

**G06: ENCERRADO POR CONVENÇÃO SINTÉTICA APROVADA.** Todos os ativos têm tratamento residual definido e rastreável.

**G08: PASS na reconciliação aritmética do BAU sintético; liberação científica/comparativa de F1 permanece CONDICIONADA.** O numerador derivado e o denominador sintético estão calculáveis, mas não se deve rotular o quociente como F1 definitivo do estudo multi-cenário antes da auditoria de equivalência das fronteiras de custo e serviço nos cenários comparados. Nenhum F1 definitivo ou LCOE final é divulgado neste documento.

### Critério único de encerramento remanescente

Conferir, em uma única auditoria transversal, se os demais cenários usam: (i) mesma base monetária e horizonte; (ii) mesma definição de CAPEX/OPEX da frota e infraestrutura, com as diferenças tecnológicas próprias; (iii) créditos residuais com a regra de G06; (iv) PKM de serviço consistente; (v) nenhuma dupla contagem. **Não é necessária nova pesquisa para o BAU nem reexecução do despacho/otimização.** Se o objetivo for somente o BAU sintético, o fechamento econômico aritmético já está concluído.

## 6. Evidência e integridade

- ZIP examinado: `matriz_14_rubricas_REV032g9.zip`; SHA-256 `dca3f83224c4e50ea6006fa54b1bfd5d5135f204ef05bb41cf3941254af614bc`.
- `auditoria_duas_camadas_REV032g9.json` SHA-256 `cdcac26e7c6118187a1d78d2cd57f082c4c5e260ee76c38d441078ccf950d2a1`.
- `fluxo_anual_duas_camadas_REV032g9.csv` SHA-256 `8355ceee161cc6e0b543a7094fc344ca9b7cea96def8cf67eca296886639195f`.
- `matriz_14_rubricas_REV032g9.csv` SHA-256 `845aa09aa84fbb58673214c6c13dd8106598ae0bbd34e53e72593ecfa33478c0`.
- `relatorio_fechamento_REV032g9.md` SHA-256 `57abd4f446cae109ced4cb7e7107b2ef423dfdb43db317685e50376e1a9c667d`.

**Controle de não alteração:** cálculos realizados exclusivamente em memória a partir do ZIP de entrada; nenhum original foi sobrescrito.

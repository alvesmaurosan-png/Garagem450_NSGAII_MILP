# Garagem450 — Integração econômica controlada das convenções G03–G05

**Natureza:** memória de integração incremental e reconciliação; não é homologação de F1, LCOE ou valor residual.  
**Data:** 15/11/2026.  
**Referências:** `parametros/Base_Mestre_450_Reconciliada_REV02.xlsx` (P09); `REG_HOMOLOGACAO_CONVENCOES_G03_G04_G05_GARAGEM450.md`; `REG_DECISAO_ECO007_ECO008_ECO021_REV032g12.md`; REV03.2g.9 (`auditoria_duas_camadas_REV032g9.json`, `matriz_14_rubricas_REV032g9.csv`, `fluxo_anual_duas_camadas_REV032g9.csv`).

## 1. Invariantes e limites

- Não modificar Base Mestre, JSONs de parâmetros, fluxo de caixa ou VP de REV03.2g.9.
- Não executar MILP, NSGA-II, despacho ou faturamento.
- Moeda convencional: reais constantes de janeiro de 2026; VP no início de 2038, taxa real 8% a.a., 2038–2057.
- Este documento produz somente uma **ponte aritmética indicativa de integração**; o VP congelado não é substituído. Não produzir F1/LCOE.

## 2. Matriz incremental de decisão

| Rubrica | Base anterior | Decisão vigente | Lançamento incremental proposto | Status |
|---|---|---|---:|---|
| CAPEX carregadores G03 | P09, R$ 226.447,05/un; 29 un; não integrado | preço sintético jan/2026 sem IPCA; equipamento de referência 150 kW, modelado 138 kW | **+R$ 6.566.964,45 em t=0**, condicionado à checagem da matriz original de 14 rubricas | AUTORIZADO PARA PONTE, NÃO INCORPORADO AO VP CONGELADO |
| Instalação elétrica | R$ 1.501.312,4280, já integrada | preservar | R$ 0 de ajuste | PRESERVADO |
| Conexão | R$ 187.664,0535, já integrada | preservar | R$ 0 de ajuste | PRESERVADO |
| Manutenção frota G04 | R$ 66.939.116,166011766/ano, já integrada | preservar sem decomposição presumida | R$ 0 de **lançamento adicional por exclusão de escopo**, não custo real nulo | APROVADO |
| Manutenção carregadores e OPEX adicional | não integrado | excluir do perímetro sintético o não documentado; não usar 2% histórico | nenhum lançamento | APROVADO, EXCLUSÃO EXPLÍCITA |
| Energia TE/TUSD G05 | R$ 14.546.699,898915628/ano, já integrada | preservar | R$ 0 de ajuste | APROVADO |
| Demanda TUSD G05 | R$ 2.498.103,979966172/ano, já integrada | preservar | R$ 0 de ajuste | APROVADO |
| Tributos, bandeiras adicionais, reativos, ultrapassagem e demais componentes | não integrados | excluídos do **perímetro sintético**, bandeira verde | nenhum lançamento | APROVADO, NÃO É FATURA REAL |
| Reposição de carregadores | zero em REV03.2g.7 | preservar hipótese de não reposição | R$ 0 adicional | APROVADO ANTERIORMENTE |
| Residual e recuperação G06 | indefinidos | método definido; taxas não homologadas | **não lançar crédito nem zerá-lo** | BLOQUEADO |

**Condição antidupla contagem:** antes de materializar um novo fluxo econômico, verificar em `matriz_14_rubricas_REV032g9.csv` que o CAPEX de carregadores não está incluído nas rubricas de instalação/conexão e que a linha de carregadores está efetivamente não integrada. A ausência de comprovação da desagregação é ressalva da hipótese sintética, não prova de inexistência de sobreposição física.

## 3. Ponte aritmética indicativa (não substituir resultados congelados)

| Elemento | R$ de janeiro/2026 |
|---|---:|
| VP documentado REV03.2g.9 — **congelado** | 826.255.483,3377191 |
| CAPEX inicial de frota — **congelado** | 1.282.419.498,9573 |
| VP reposição de frota condicionada — **congelado** | 594.008.360,9098448 |
| VP parcial condicionado REV03.2g.9 — **congelado** | **2.702.683.343,204864** |
| Incremento candidato G03, t=0 | **6.566.964,45** |
| **Soma de conferência não homologada** | **2.709.250.307,654864** |

A soma de conferência serve exclusivamente para testar a aritmética da ponte. **Não é novo VP homologado, custo integral, limite inferior garantido ou F1.** O valor residual G06 poderá reduzir o VP e depende de aprovação; outros ajustes de perímetro também podem existir.

## 4. Verificações para integração no repositório

1. Confirmar hash e existência dos três arquivos de REV03.2g.9; comparar suas rubricas com a matriz acima.
2. Confirmar que G03 consta como não integrado e que instalação/conexão não incorporam a compra de equipamentos.
3. Registrar evento G03 de R$ 6.566.964,45 em **t=0 (início de 2038)** somente em uma **camada derivada separada**, preservando arquivos e valores congelados.
4. Não adicionar eventos de OPEX G04 nem encargos G05 fora do perímetro aprovado. Preservar explicitamente as exclusões.
5. Manter a reposição condicionada da frota em t=10, o denominador PKM aprovado e o residual G06 como pendência, sem imputar zero.
6. Validar identidade: VP da camada derivada, antes de G06 = VP parcial condicionado congelado + CAPEX G03. Registrar diferença zero dentro da precisão monetária.
7. Produzir trilha de auditoria com entradas, hashes, data, convenções e estados, **sem alterar** os arquivos de REV03.2g.9.

## 5. Estados de gate

- G03: `CONVENCAO_APROVADA_PONTE_ARITMETICA_PREPARADA`; integração operacional pendente de verificação da matriz original.
- G04: `FRONTEIRA_SINTETICA_APROVADA_SEM_LANCAMENTO_ADICIONAL`.
- G05: `FATURAMENTO_SINTETICO_APROVADO_SUBTOTAL_PRESERVADO`.
- G06: `METODO_DEFINIDO_TAXAS_RESIDUAIS_PENDENTES`.
- G07: `CONVENCAO_PKM_APROVADA`.
- G08: `F1_DEFINITIVO_BLOQUEADO`.

## 6. Critério de saída

A integração econômica controlada estará **operacionalmente reconciliada** apenas depois de inspecionados os arquivos reais de REV03.2g.9 e comprovada a ausência de duplicidade nas rubricas. A ponte numérica aqui calculada não satisfaz, sozinha, esse critério. Nenhum cálculo de F1 definitivo ou LCOE definitivo está autorizado.

# Garagem450 — Adaptador econômico R0-OPT-REV01

## Escopo e instalação

Patch **aditivo**, exclusivamente econômico, com Python padrão e `pytest` para testes. Copiar `src/economia_adaptador_rev01.py` e `tests/test_economia_adaptador_rev01.py` para os diretórios homônimos do projeto. Não substituir módulos REV03.2, não alterar MILP, certificados NPZ, resultados nem parâmetros originais.

Executar na raiz do PyCharm:

```powershell
python -m pytest tests/test_economia_adaptador_rev01.py -q
```

## Decisões incorporadas

- Horizonte 2038–2057; t=0 início de 2038; fluxos operacionais t=1..20; taxa real 8% a.a.; moeda R$ constantes de janeiro/2026.
- Fronteira integrada: frota + carregadores + instalações + conexão/reforço + energia/demanda + OPEX + reposições − créditos G06.
- G06: `custo * max(0, 1 - idade/vida) * 0.50`; vidas BEV 12, instalações 25, carregadores 20, conexão 30 mas **não recuperável**. Reposição BEV em t=10, crédito da frota original em t=10, crédito da substituta em t=20. A substituição deve ser contabilizada **também como custo** na rubrica de reposição.
- Não embute valores do BAU no R0. Nenhum custo ausente vira zero automaticamente; zeros explícitos exigem justificação no processo de preparação de entradas.
- `F1_brl_per_pkm` fica `None` até comprovar equivalência de serviço, fronteira econômica e série anual PCC. `f1_diagnostic_brl_per_pkm` não é F1 validado e **não deve alimentar NSGA-II**.
- `pcc_kw` exige 35.040 pontos em 15 minutos e máximo de 2.500 kW. Se a série não estiver disponível, F2 é nulo.

## Interface

`evaluate(initial_costs=..., annual_costs=..., annual_pkm=..., assets=..., pcc_kw=..., service_equivalence_verified=..., cost_boundary_verified=...)`

As 13 rubricas de custos são definidas por `CATEGORIES`; `residual_credit` é **calculado**, não aceito como custo externo. Cada rubrica precisa de valor inicial e de 20 valores anuais. O adaptador não calcula tarifas a partir do despacho, não faz validação de dados empíricos e não lê o MILP. O processo de reconciliação deve assegurar que custos/PKM são do **mesmo cenário** e que os fluxos já estão completos.

### Ressalvas técnicas

- As categorias agregadas são um contrato de entrada; não se deve duplicar TE/TUSD ou somar custos de aquisição e reposição duas vezes.
- O adaptador **não verifica automaticamente** se os custos de ativos declarados em `assets` correspondem aos custos do ledger, nem se há ativos faltantes. A aprovação de `cost_boundary_verified=True` requer auditoria externa de correspondência e completude.
- A interface de `annual_costs` usa índice 0 → t=1. Para o evento em **t=10**, usar índice **9**. Para custos operacionais do ano civil 2048 em t=11, usar índice 10.
- A solução de 100 BEV permanece uma referência factível. Este patch não afirma F1_R0, não calcula Pareto e não libera a otimização sem os gates.

## Proveniência

Consolidação `CONSOLIDACAO_G06_AUDITORIA_G08_GARAGEM450.md` (15/11/2026), relatório `RELATORIO_RESULTADOS_BAU_GARAGEM450_REV01.md` e código legado REV03.2, disponibilizados nos dois ZIPs de auditoria. Nenhuma pesquisa externa ou alteração dos artefatos históricos.

# Garagem450 — Registro de resolução controlada de G03, G04 e G05

**Natureza:** registro documental de diagnóstico e decisões propostas; não constitui homologação automática de valores.
**Vinculação:** `parametros/Base_Mestre_450_Reconciliada_REV02.xlsx`, `Pesquisa_Fontes` P09, registros econômicos REV03.2g.4a, REV03.2g.5, REV03.2g.9 e parecer REV03.2g.11.
**Escopo:** BAU sintético 450 ônibus; R$ constantes janeiro/2026; horizonte 2038–2057; 8% reais. Sem reexecução MILP/NSGA-II, sem recálculo de custos, sem alteração da Base Mestre.

## G03 — CAPEX dos carregadores

- Referência P09: orçamento licitatório Pregão Aracaju 24/2026, carregador DC de 150 kW, R$ 226.447,05/unidade; ano 2026, mês-base não comprovado.
- Arquitetura física: 29 carregadores de 138 kW. Total aritmético do benchmark: R$ 6.566.964,45, **não integrado** ao VP congelado.
- O benchmark não comprova equivalência técnica integral entre equipamentos de 150 e 138 kW, nem inclui necessariamente obras elétricas, frete, comissionamento e instalação.
- **Regra:** não aplicar IPCA de julho/2026 a referência de mês desconhecido; não substituir o valor por estimativa nova sem decisão.
- **Evidência mínima de fechamento:** documento primário com data/mês do orçamento e escopo do fornecimento, ou aprovação explícita de convenção monetária sintética com ressalva de incerteza; delimitação do escopo para evitar sobreposição com instalação/conexão.
- **Estado:** `BLOCKED_REFERENCE_MONTH_AND_SCOPE`.

## G04 — Manutenção dos carregadores e OPEX do sistema

- Manutenção da frota: R$ 2,7051765762140327/km e R$ 66.939.116,166011766/ano, congelada em REV03.2f; não reabrir.
- Não há decomposição comprovada que demonstre se o proxy de manutenção da frota contém assistência a carregadores, manutenção elétrica, software de gestão, suporte e outras despesas.
- Existe taxa histórica de 2% do CAPEX/ano para carregadores em matriz anterior, **não ativa na Garagem450**; não transferir nem somar automaticamente.
- **Regra:** identificar serviços incluídos/excluídos no proxy da frota; só contabilizar OPEX adicional se comprovadamente incremental e sem sobreposição. Ausência de dado não é custo zero.
- **Evidência mínima de fechamento:** delimitação documental das coberturas e uma decisão expressa para cada rubrica (incluído, incremental quantificado, ou hipótese sintética aprovada e explicitada).
- **Estado:** `BLOCKED_NON_OVERLAP_NOT_DEMONSTRATED`.

## G05 — Faturamento elétrico integral

- Referência de faturamento parcial REV03.2g.4a: energia R$ 14.997.159,319/ano e demanda R$ 2.575.461,3516/ano, base julho/2026, subtotal R$ 17.572.620,6706/ano.
- REV03.2g.5: energia R$ 14.546.699,898915628/ano, demanda R$ 2.498.103,979966172/ano, subtotal R$ 17.044.803,8788818/ano em reais equivalentes de janeiro/2026 por IPCA. Não equivale a tarifa regulada de janeiro/2026.
- Modalidade A4 Azul e demanda contratada são hipóteses sintéticas, não contrato efetivo. O faturamento completo ainda não foi homologado.
- **Regra antidupla contagem:** TE/TUSD energia e TUSD demanda já contêm componentes tarifários; não adicionar encargos genericamente sem demonstrar exclusão. Segregar tributos, bandeiras, reativos, ultrapassagem, eventuais adicionais e condições de faturamento conforme aplicabilidade. Não presumir que todos incidem ou que são zero.
- **Evidência mínima de fechamento:** matriz componente × incluído/excluído/não aplicável × regra de cálculo × fonte × decisão; enquadramento e condições de faturamento sintéticas aprovados.
- **Estado:** `BLOCKED_FULL_BILL_PERIMETER_NOT_DEFINED`.

## Matriz de decisões propostas

| ID | Decisão | Situação | Efeito |
|---|---|---|---|
| G03-D1 | Preservar benchmark P09 sem converter até esclarecer mês-base | PROPOSTA | Sem alteração do VP |
| G03-D2 | Tratar equivalência 150/138 kW e escopo de instalação como ressalvas | PROPOSTA | Evita dupla contagem de CAPEX |
| G04-D1 | Preservar manutenção da frota congelada | DECISÃO VIGENTE | Sem recálculo |
| G04-D2 | Não ativar taxa histórica de 2% de OPEX dos carregadores | PROPOSTA | Evita custo não sustentado |
| G05-D1 | Preservar faturamento parcial reconciliado | DECISÃO VIGENTE | Sem recálculo |
| G05-D2 | Exigir matriz de inclusão de componentes antes de declarar fatura integral | PROPOSTA | Impede soma duplicada de encargos |

## Condições de liberação

- **G03:** `BLOCKED` até decisão de mês-base/convenção monetária e equivalência de escopo.
- **G04:** `BLOCKED` até segregação ou decisão de tratamento explícita de manutenção e OPEX incremental.
- **G05:** `BLOCKED` até delimitação integral dos componentes e condições de faturamento.
- **G06:** método residual definido, parâmetros de recuperação ainda condicionados.
- **G07:** convenção sintética do VP(PKM) aprovada pelo pesquisador para o BAU.
- **G08 / F1 / LCOE:** `BLOCKED`.

## Preservação dos resultados

VP documentado REV03.2g.9: **R$ 826.255.483,34**.
VP parcial condicionado REV03.2g.9: **R$ 2.702.683.343,20**.
Nenhum valor é alterado por este registro. O VP condicionado não é necessariamente limite inferior por haver créditos residuais pendentes.

## Aprovação do pesquisador

- [ ] Aprovo G03-D1 e G03-D2 como regras de tratamento, sem homologar o CAPEX.
- [ ] Aprovo G04-D2 como regra de não ativação da taxa histórica, mantendo G04 bloqueado.
- [ ] Aprovo G05-D2 como requisito de reconciliação, mantendo G05 bloqueado.
- [ ] Confirmo preservação integral da Base Mestre e das revisões anteriores.

**Data/identificação da decisão:** ____________________

**Resultado do registro:** `G03_G04_G05_TRATAMENTO_DOCUMENTADO_PENDENCIAS_MANTIDAS`.

# Garagem450 — Registro controlado de homologação das convenções sintéticas G03, G04 e G05

**Natureza:** decisão metodológica expressamente aprovada pelo pesquisador; não é comprovação empírica de preços, contratos ou custos reais.  
**Data da aprovação:** 15/11/2026 (data da manifestação nesta conversa).  
**Escopo:** cenário BAU sintético da Garagem450; referência monetária R$ constantes de janeiro/2026; horizonte econômico 2038–2057; desconto real de 8% a.a.  
**Documento de referência:** `parametros/Base_Mestre_450_Reconciliada_REV02.xlsx`, especialmente `Pesquisa_Fontes!P09`, sem alterar células, abas, fórmulas, valores ou status de origem.  
**Antecedente documental:** `REG_RESOLUCAO_CONTROLADA_G03_G04_G05_REV032g12.md` (diagnóstico e propostas anteriores). Este registro formaliza a aprovação posterior, sem apagar o histórico.  
**Rastreabilidade:** decisões aprovadas explicitamente pelo pesquisador na conversa de 15/11/2026.

## 1. G03 — CAPEX dos carregadores: convenção APROVADA

**Decisão G03-A:** Adotar, exclusivamente como **preço sintético convencional em reais de janeiro/2026**, o benchmark P09 de **R$ 226.447,05 por carregador DC de 150 kW**, sem atualização adicional pelo IPCA. Para **29 unidades** da configuração de referência, o produto aritmético é **R$ 6.566.964,45**.

**Limites e ressalvas obrigatórias:** (i) a fonte P09 registra o ano de 2026, mas não comprova janeiro como mês-base real; (ii) o equipamento de referência é de 150 kW e o modelo físico utiliza 29 carregadores de 138 kW; a equivalência é convenção de custo, não comprovação técnica de identidade; (iii) o preço P09 não comprova a inclusão de instalação, comissionamento, conexão ou obras elétricas; (iv) não somar novamente parcelas já atribuídas à instalação e à conexão; (v) a rubrica não integra retroativamente os fluxos e valores presentes congelados.

**Estado:** `G03_CONVENCAO_SINTETICA_APROVADA`; integração monetária posterior sujeita à reconciliação antidupla contagem.

## 2. G04 — Manutenção e OPEX: convenção APROVADA

**Decisão G04-A:** Preservar o custo de manutenção da frota previamente congelado, **R$ 2,7051765762140327/km** e **R$ 66.939.116,166011766/ano** (REV03.2f). Excluir **do perímetro econômico sintético**, sem lançamento monetário adicional, OPEX incremental não documentado de carregadores, instalações elétricas, conexão, gestão ou serviços auxiliares. Não ativar a taxa histórica de 2% do CAPEX de carregadores ao ano.

**Limites e ressalvas obrigatórias:** exclusão de escopo **não significa custo operacional real zero**, nem demonstra que o proxy de manutenção da frota inclua manutenção da infraestrutura. A convenção é uma limitação consciente do modelo; pode subestimar custos reais e deve ser aplicada de modo consistente às arquiteturas comparadas. Não efetuar dedução, acréscimo ou reclassificação da manutenção congelada sem autorização posterior.

**Estado:** `G04_FRONTEIRA_OPEX_SINTETICA_APROVADA`.

## 3. G05 — Faturamento elétrico: convenção APROVADA

**Decisão G05-A:** Para o BAU sintético, limitar a despesa elétrica às parcelas **TE e TUSD de energia e TUSD de demanda** já calculadas sob hipótese de **Grupo A4, modalidade Azul, bandeira verde**, sem componentes adicionais. Preservar o subtotal anual reconciliado de **R$ 17.044.803,8788818** em reais equivalentes de janeiro/2026: energia **R$ 14.546.699,898915628** e demanda **R$ 2.498.103,979966172** (REV03.2g.5).

**Limites e ressalvas obrigatórias:** trata-se de **faturamento sintético de escopo limitado**, não de fatura integral real. A convenção exclui da modelagem acréscimos não previamente computados relativos a tributos, bandeiras adicionais, reativos, ultrapassagem e demais condições especiais; isso **não equivale a comprovar sua inexistência ou não incidência real**. Não duplicar encargos incorporados às parcelas tarifárias TE/TUSD. A conversão IPCA de julho/2026 para janeiro/2026 é equivalência monetária, não reconstrução de tarifa regulada vigente em janeiro/2026.

**Estado:** `G05_FRONTEIRA_FATURAMENTO_SINTETICO_APROVADA`.

## 4. Matriz de deliberação e efeitos

| Gate | Deliberação do pesquisador | Efeito autorizado | Não autorizado |
|---|---|---|---|
| G03 | APROVADA | Usar P09 como preço convencional jan/2026 para futura integração controlada | Declarar mês-base documental comprovado; alterar VP congelado |
| G04 | APROVADA | Excluir OPEX incremental sem documentação do perímetro sintético | Afirmar custo real zero; somar taxa histórica de 2% |
| G05 | APROVADA | Usar exclusivamente subtotal TE/TUSD energia e demanda já calculado | Declarar fatura real integral; adicionar encargos genericamente |
| G06 | NÃO OBJETO DESTA APROVAÇÃO | Preservar método residual anteriormente especificado | Homologar taxas de recuperação pendentes |
| G07 | DECISÃO ANTERIOR PRESERVADA | Manter convenção sintética de PKM | Alterar denominador ou calendário |
| G08 | BLOQUEADO | Preparar futura integração controlada e auditoria do F1 | Divulgar F1 ou LCOE definitivo |

## 5. Invariantes econômicos e computacionais

- **Nenhuma alteração** da Base Mestre, seus status originais ou arquivos de parâmetros congelados.
- **Nenhuma reexecução** de MILP, NSGA-II, despacho ou reconstrução de demanda.
- **Nenhum recálculo** ou substituição do VP documentado de **R$ 826.255.483,3377191** ou do VP parcial condicionado de **R$ 2.702.683.343,204864** (REV03.2g.9).
- O CAPEX dos carregadores aprovado para uso futuro **não está incorporado** aos VP acima por este ato.
- A aprovação de G03–G05 é **metodológica e sintética**, não homologação de aderência empírica; G06 e demais pendências econômicas não são automaticamente resolvidos.

## 6. Próxima operação autorizável, mas não executada

Efetuar, somente mediante instrução específica, uma **integração econômica controlada** do CAPEX G03 e a verificação de não sobreposição com instalação/conexão, preservando G04/G05 nos perímetros aprovados e tratando G06 separadamente. Emitir trilha de auditoria antes de qualquer novo valor de F1.

**Resultado deste registro:** `G03_G04_G05_CONVENCOES_SINTETICAS_FORMALMENTE_APROVADAS_F1_AINDA_BLOQUEADO`.

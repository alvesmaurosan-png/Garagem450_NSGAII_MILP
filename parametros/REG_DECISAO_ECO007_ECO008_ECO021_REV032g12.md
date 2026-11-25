# REG-REV03.2g.12 — Registro controlado de decisão econômica

**Projeto:** Garagem450_NSGAII_MILP — exercício sintético BAU, frota de 450 ônibus BEV  
**Objeto:** ECO-007, ECO-008 e ECO-021 — vida útil, reposição e valor residual por ativo  
**Natureza:** especificação metodológica controlada; **não constitui homologação de taxas financeiras**  
**Situação do registro:** MÉTODO DEFINIDO — PARÂMETROS CONDICIONADOS — G06 NÃO LIBERADO  
**Data de emissão:** 15/11/2026  
**Documento vinculado:** `parametros/Base_Mestre_450_Reconciliada_REV02.xlsx` (nome relativo ilustrativo; localizar a Base Mestre original no repositório)  
**SHA-256 da cópia examinada:** `26518a14bc9b53af59d43487abb451ca0bee79f65ae9667a252b28d779fe1f2d`  
**Escopo da vinculação:** identificação documental e rastreabilidade; não implica alteração ou homologação automática da planilha.

## 1. Verificação dos registros originais

Na aba `Base_Ativa` da Base Mestre REV02, os três registros estão **Pendente — não ativar**:

| ID | Descrição original | Situação da Base Mestre | Decisão deste registro |
|---|---|---|---|
| ECO-007 | Valor residual | Pendente — não ativar | Definir método por ativo; não ativar créditos |
| ECO-008 | Vida útil e reposição da frota | Pendente — não ativar | Preservar reposição sintética em 2048; vidas úteis técnicas não homologadas |
| ECO-021 | Custos de reposição e valor residual por ativo | Pendente — não ativar | Separar eventos de substituição, alienação e residual final |

Na aba `Excluidos`, o parâmetro histórico `D10-005` fixa valor residual igual a zero. **Não é parâmetro ativo nem fundamento para zerar os créditos neste estudo.**

## 2. Decisões anteriores preservadas

1. Horizonte econômico: 2038–2057, 20 fluxos operacionais anuais, reais constantes de janeiro/2026, taxa real de desconto de 8% a.a.; referência de valor presente no início de 2038.
2. Frota inicial: 450 ônibus BEV no início de 2038, CAPEX condicionado preservado; reposição integral no **início de 2048 (t = 10)**, ao mesmo custo real, **hipótese sintética condicionada, não comprovação de vida útil**.
3. Carregadores: **sem reposição durante 2038–2057**, por decisão sintética REV03.2g.7. Não equivale a vida útil técnica certificada nem a crédito residual nulo.
4. Nenhum fluxo ou VP congelado será recalculado neste registro. O VP documentado de R$ 826.255.483,34 e o VP parcial condicionado de R$ 2.702.683.343,20 permanecem inalterados.
5. A convenção de VP(PKM) do BAU foi aprovada separadamente; este registro não altera o denominador nem libera F1.

## 3. Método aprovado para especificação (sem ativação econômica)

Para cada lote/ativo `i`, definir: custo elegível `C_i` em R$ constantes de jan/2026; data de entrada em serviço; data de retirada ou avaliação; idade econômica `A_i` (anos); vida útil econômica de referência `L_i` (anos); e fator de recuperação econômica `alpha_i` (0 a 1), **somente após decisão expressa**.

- Fração linear de vida remanescente: `r_vida_i = max(0, 1 - A_i/L_i)`, para `L_i > 0`.
- Crédito econômico condicionado: `VR_i = C_i × r_vida_i × alpha_i`.
- `r_vida_i` **não é taxa comprovada de revenda**; `alpha_i` não pode ser implicitamente definido como 0 ou 1.
- Créditos de alienação no início de 2048: `VP(VR_2048) = VR_2048/(1,08)^10`.
- Créditos de ativos remanescentes ao final de 2057: `VP(VR_2057) = VR_2057/(1,08)^20`.
- Na futura função de custo, os créditos comprovados ou expressamente assumidos entram com sinal negativo; os eventos de aquisição e substituição entram uma única vez com sinal positivo.
- Não confundir valor contábil, vida técnica remanescente, valor de uso e preço líquido de alienação. Para instalações não destacáveis, um eventual valor residual pode depender da continuidade de uso ou da propriedade do imóvel.

**Regra de controle:** se `L_i`, `alpha_i`, titularidade, evento de alienação ou perímetro de custo estiverem indefinidos, registrar `VR_i = NÃO CALCULADO`, nunca zero por omissão.

## 4. Matriz de ativos e parâmetros condicionados

| Classe / evento | Momento | Referência exploratória | Fração linear ilustrativa | Situação de homologação |
|---|---|---|---|---|
| Frota original: retirada/alienação | Início de 2048, t=10 | 10 anos de operação planejada, por decisão de reposição | **Não atribuir** taxa de recuperação | Valor de alienação e regra econômica pendentes |
| Frota substituta: remanescente | Fim de 2057, t=20 | Vida econômica candidata 12 anos; idade aproximada de 10 anos | 16,67%, **se** L=12 | Candidata, não homologada; `alpha` pendente |
| Carregadores DC: remanescentes | Fim de 2057, t=20 | Sem reposição em 20 anos; vida econômica não definida | **Indeterminada** | Não inferir L=20 nem taxa zero |
| Instalações elétricas: remanescentes | Fim de 2057, t=20 | Vida econômica candidata 25 anos; idade aproximada de 20 anos | 20%, **se** L=25 | Candidata, não homologada; `alpha` pendente |
| Conexão elétrica: remanescente | Fim de 2057, t=20 | Vida econômica candidata 30 anos; idade aproximada de 20 anos | 33,33%, **se** L=30 | Candidata, não homologada; `alpha` pendente |

**Advertências:** (a) os 12, 25 e 30 anos são valores exploratórios discutidos nesta revisão, não referências técnicas homologadas na Base Mestre; (b) a idade dos ativos pressupõe entrada em operação em 2038, a confirmar por classe; (c) não aplicar taxa à parcela de custo de conexão que represente serviço, taxa ou direito não alienável; (d) o CAPEX dos carregadores continua sem mês-base reconciliado, impedindo o cálculo monetário do residual dessa classe; (e) a regra de substituição da frota em dez anos não valida automaticamente a vida econômica de doze anos dos substitutos.

## 5. Evidência necessária para ativação

| ID / decisão | Evidência ou aprovação requerida | Condição para alterar status |
|---|---|---|
| ECO-007 | Método residual aprovado, propriedade e recuperabilidade por classe, `alpha_i` explícito | Crédito monetário rastreável, sem valor zero implícito |
| ECO-008 | Vida útil econômica e política de reposição documentadas para cada tecnologia/lote | Diferenciar premissa de reposição em 2048 de vida técnica/econômica |
| ECO-021 | Inventário de CAPEX elegível por ativo, cronologia de retirada e substituição, valor de alienação da frota original e residual final | Sem dupla contagem e com desconto nos instantes corretos |

**Referências internas disponíveis:** Base Mestre REV02, abas `Base_Ativa` e `Excluidos`; decisões sintéticas REV03.2g.7; integração parcial REV03.2g.9; parecer REV03.2g.11. Nenhuma delas, isoladamente, comprova as taxas de recuperação propostas.

## 6. Portões de liberação e efeito sobre F1

- **G06:** `METODO_DEFINIDO_PARAMETROS_CONDICIONADOS` — **BLOQUEADO PARA INTEGRAÇÃO ECONÔMICA**.
- **G07:** convenção sintética de VP(PKM) do BAU aprovada em decisão separada; não é objeto de alteração aqui.
- **G03, G04, G05:** permanecem bloqueados conforme REV03.2g.11.
- **G08 / F1 / LCOE / BAU integral / liberação econômica NSGA-II–MILP:** permanecem **BLOQUEADOS**.

O VP parcial condicionado **não é necessariamente limite inferior** do custo total, em razão de custos adicionais e créditos residuais ainda não definidos.

## 7. Controle de alterações e aprovação

**Artefato único desta decisão:** este arquivo Markdown. Não modifica a Base Mestre nem quaisquer JSON, CSV, fluxos econômicos ou scripts do repositório. Se for incorporado ao projeto, manter cópia vinculada à Base Mestre por nome e SHA-256, com versionamento documental normal, sem sobrepor registros anteriores.

| Campo de governança | Valor |
|---|---|
| Método residual por ativo | ESPECIFICADO; sujeito à aprovação do pesquisador |
| Vidas úteis exploratórias | NÃO HOMOLOGADAS |
| Fatores de recuperação `alpha_i` | NÃO DEFINIDOS |
| Crédito residual no fluxo econômico | NÃO AUTORIZADO |
| Revisão de parâmetros anteriores | NÃO AUTORIZADA |
| Responsável pela decisão | Pesquisador responsável — aprovação pendente |
| Data de aprovação | Pendente |

**Deliberação proposta:** aprovar somente a **estrutura metodológica e os controles de rastreabilidade** deste registro; não aprovar taxas de recuperação financeira nem liberar G06/F1. A aprovação do pesquisador deve ser registrada explicitamente antes de tratar este documento como decisão vigente.

# Garagem450_NSGAII_MILP — RELEASE REV04

Distribuição científica do exercício exploratório de dimensionamento e despacho de microrredes para 450 ônibus. Não é projeto executivo nem certificação comercial. F1 = VP dos custos totais / VP do serviço (R$/passageiro·km); F2 = pico de importação PCC (kW); LCOE = custo nivelado da eletricidade de tração (R$/kWh), indicador complementar. Horizonte 2038–2057, taxa real 8%, requisito sintético comum de 569.130.934,0742 PKM/ano.

| Cenário | Arquitetura | Frota BEV/diesel/GN | F1 | F2 kW | LCOE |
|---|---|---|---:|---:|---:|
| BAU | Rede expansível | 450/0/0 | 0,48975 | 3841,52 | 0,92170 |
| R0 | Rede/PV/BESS | 315/135/0 | 0,45238 | 2498,40 | 1,24734 |
| R1 | Rede/PV/BESS/CHP-BIO | 450/0/0 | 0,50934 | 2490,17 | 1,28796 |
| R2 | Rede/PV/BESS/CHP-BIO + GN externo | 1/0/449 | 0,35123 | 56,22 | 1,38889 |

R2: biogás alimenta CHP, não ônibus; aproximadamente 98% da demanda elétrica é compressão de GN. CGOB é hipótese de custo, não certificado efetivamente adquirido. R1 tem seis trajetórias anuais aprovadas, duas não dominadas no subconjunto validado; ID4 escolhido pelo menor F1, ID7 pelo menor F2. R0/R2 usam dias representativos; R1 usa cronologia anual sintética. Não há garantia de ótimo global, robustez ou disponibilidade física de substrato. R0 histórico de 100 BEV não se confunde com R0 de 315 BEV.

## Instalação
Executar a partir da raiz, preferencialmente Python 3.13. Ambiente original não incluía lockfile; requirements registra faixas compatíveis, não reprodução bit a bit.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python verificar_release.py
```

Linux/macOS: `source .venv/bin/activate` em vez do comando de ativação Windows.

## Resultados existentes (sem solver)
- `resultados/consolidado_REV04/comparativo.csv`: seleção documental das linhas originais, sem recálculo econômico.
- `resultados/CONSOLIDADO_FINAL_REV02_20261124_215315/`: BAU, R0, R2 e respectivas fronteiras.
- `resultados/NSGAII_FINAL_REV04_20261125_010610/`: avaliações LP/MILP, Pareto R1, despachos e auditoria JSON.
- `docs/relatorio_final/`: relatório REV04 e anexo de arquiteturas.

## Reprodução opcional (não necessária para consultar a release)
Os comandos abaixo executam novas buscas e podem demorar horas; os resultados podem variar com solver/versão/tempo. Executar em cópia de trabalho. Os caminhos originais foram mantidos para evitar alteração dos modelos.

```powershell
python -u nsga2_milp_garagem450_final_rev01.py --pop 24 --geracoes 20 --seed 42 --tempo 3 --gas-station-capex 5000000 --gas-maint-km 2.3 --gas-compression 0.25
python -u nsga2_milp_garagem450_final_rev02.py --pop 24 --geracoes 20 --seed 42 --tempo 3 --gas-station-capex 5000000 --gas-maint-km 2.3 --gas-compression 0.25
python -u nsga2_milp_garagem450_final_rev04.py --pop 24 --geracoes 20 --seed 42 --tempo-lp 120 --tempo 30 --validar 8
```

REV01: referência R0; REV02: limite CHP de 15 módulos para R1/R2; REV04: R1 cronológica. Os consolidadores históricos usam nomes de execuções congeladas; não substituem automaticamente os resultados publicados. Os perfis G4 e solar G5.1 são entradas congeladas incluídas. `src/` e `tests/` mantêm componentes históricos e testes originais; não são todos necessários à execução principal. Para reproduzir experimentos antigos, extrair o ZIP histórico separado sobre uma cópia da árvore, mantendo caminhos originais. Não sobrescrever a release publicada.


## Atualização v4.0.1 — REV04.1

Complementação ambiental e visualização consolidada dos resultados da REV04.

### Principais contribuições

- Avaliação complementar dos atributos ambientais associados aos Certificados de Garantia de Origem de Biometano (CGOB).
- Separação entre emissões fósseis operacionais físicas e emissões fósseis atribuídas hipoteticamente mediante instrumentos contratuais.
- Análise de sensibilidade da cobertura renovável de 0% a 100%.
- Determinação dos limiares de equivalência ambiental entre as configurações.
- Geração centralizada de gráficos econômicos, energéticos, ambientais, operacionais e de otimização, nos formatos PNG e SVG.
- Preservação integral dos resultados originais da REV04.

### Reprodução dos resultados

```bash
python avaliar_emissoes_cgob_rev041.py --cobertura 100
python gerar_graficos_consolidados_rev041.py
```

Diretórios de saída:

- `resultados/CGOB_REV041/`
- `resultados/GRAFICOS_CONSOLIDADOS_REV041/`

### Ressalvas científicas

A atribuição ambiental mediante CGOB possui natureza exploratória e condicionada à elegibilidade metodológica, equivalência energética, rastreabilidade, aposentadoria dos certificados e ausência de dupla contagem.

O indicador ajustado não substitui o inventário físico de emissões, não representa neutralidade de carbono e não constitui avaliação de ciclo de vida.

Nenhuma nova otimização NSGA-II ou MILP foi executada nesta atualização. Os indicadores F1, F2 e LCOE permanecem inalterados.

## Publicação e licença
Licença e autoria bibliográfica aguardam confirmação do responsável. Não há autorização de redistribuição presumida. Revisar direitos dos dados, documentos, metadados e informações institucionais antes de tornar público. O arquivo histórico é para custódia e não deve ser enviado automaticamente ao GitHub.

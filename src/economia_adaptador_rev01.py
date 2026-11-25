"""Garagem450 R0-OPT-REV01: adaptador econômico puro, sem dependência do MILP.

Entradas são fluxos econômicos já conciliados, NÃO resultados físicos inferidos.
Convenção: t=0 início de 2038; t=1..20 finais de 2038..2057.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from typing import Mapping, Sequence

VERSION = 'R0-OPT-REV01'
CATEGORIES = ('fleet_purchase','fleet_maintenance','fleet_replacement',
 'charger_purchase','charger_maintenance','charger_replacement',
 'electrical_installation','grid_connection','grid_reinforcement',
 'grid_energy','grid_demand','grid_charges','system_opex')

class EconomicGateError(ValueError):
    """Entrada incompleta/incompatível; F1 não deve ser calculado."""

def amount(x, label):
    if x is None or isinstance(x, bool):
        raise EconomicGateError(f'{label}: ausente/invalido (None nao equivale a zero)')
    try: v=float(x)
    except (ValueError,TypeError): raise EconomicGateError(f'{label}: nao numerico') from None
    if not isfinite(v) or v < 0:
        raise EconomicGateError(f'{label}: deve ser finito e nao negativo')
    return v

@dataclass(frozen=True)
class Asset:
    asset_id: str
    category: str
    cost_brl_2026: float
    acquisition_t: int
    retirement_t: int
    life_years: int
    recoverable: bool

LIVES = {'bev':12, 'electrical_installation':25, 'charger':20, 'grid_connection':30}
RECOVERABLE = {'bev':True,'electrical_installation':True,'charger':True,'grid_connection':False}

def residual(asset: Asset, *, years: int=20, alpha: float=.50) -> dict:
    """Crédito G06 positivo, com desconto feito APENAS na agregação de fluxos."""
    if asset.category not in LIVES or asset.life_years != LIVES[asset.category]:
        raise EconomicGateError('Vida util/categoria G06 incompatível com a convencao aprovada')
    if asset.recoverable != RECOVERABLE[asset.category]:
        raise EconomicGateError('Elegibilidade G06 incompatível com a convencao aprovada')
    if not isinstance(asset.acquisition_t,int) or not isinstance(asset.retirement_t,int):
        raise EconomicGateError('Momentos G06 devem ser inteiros')
    if not 0 <= asset.acquisition_t <= asset.retirement_t <= years:
        raise EconomicGateError('Cronologia G06 invalida')
    cost=amount(asset.cost_brl_2026,'asset.cost_brl_2026')
    if alpha != .50:
        raise EconomicGateError('Fator G06 deve ser 0.50')
    age=asset.retirement_t-asset.acquisition_t
    credit=cost * max(0., 1.-age/asset.life_years) * alpha if asset.recoverable else 0.
    return {'asset_id':asset.asset_id,'category':asset.category,'t':asset.retirement_t,
            'age_years':age,'credit_brl_2026':credit}

def evaluate(*, initial_costs: Mapping[str,float], annual_costs: Mapping[str,Sequence[float]],
             annual_pkm: Sequence[float], assets: Sequence[Asset],
             pcc_kw: Sequence[float] | None=None, years: int=20,
             first_year: int=2038, rate: float=.08,
             currency_base: str='BRL_CONSTANT_JAN_2026',
             service_equivalence_verified: bool=False,
             cost_boundary_verified: bool=False,
             residual_costs_included_elsewhere: bool=False) -> dict:
    """Retorna F1 somente se todos os gates de comparação forem aprovados.

    initial_costs: rubricas em t=0; annual_costs: cada rubrica com 20 fluxos
    t=1..20. Reposições em t=10 devem entrar na posição de índice 9,
    independentemente dos fluxos operacionais do ano de 2048 (índice 10).
    Assets descrevem somente créditos G06; custos de aquisição/reposição
    DEVEM estar explicitamente nas rubricas. Proíbe residual já embutido.
    """
    if (years,first_year,rate,currency_base)!=(20,2038,.08,'BRL_CONSTANT_JAN_2026'):
        raise EconomicGateError('Horizonte/taxa/moeda divergentes do protocolo Garagem450')
    if residual_costs_included_elsewhere:
        raise EconomicGateError('Possivel dupla contagem de credito residual')
    if set(initial_costs)!=set(CATEGORIES) or set(annual_costs)!=set(CATEGORIES):
        raise EconomicGateError('Exigidas 13 rubricas de custos explicitas, inclusive zeros justificados')
    ledger=[]
    for category in CATEGORIES:
        v=amount(initial_costs[category],f'initial.{category}')
        ledger.append({'t':0,'category':category,'amount':v,'kind':'cost'})
        series=annual_costs[category]
        if len(series)!=years: raise EconomicGateError(f'annual.{category}: exigidos 20 fluxos')
        for t,value in enumerate(series,1):
            ledger.append({'t':t,'category':category,'amount':amount(value,f'annual.{category}[{t}]'),'kind':'cost'})
    if len(annual_pkm)!=years: raise EconomicGateError('PKM: exigidos 20 fluxos')
    vp_pkm=sum(amount(v,f'PKM[{i}]')/(1+rate)**i for i,v in enumerate(annual_pkm,1))
    if vp_pkm<=0: raise EconomicGateError('VP(PKM) deve ser positivo')
    ids=set()
    for asset in assets:
        if not asset.asset_id or asset.asset_id in ids: raise EconomicGateError('ID de ativo G06 ausente/duplicado')
        ids.add(asset.asset_id)
        credit=residual(asset,years=years)
        ledger.append({'t':credit['t'],'category':'residual_credit','amount':credit['credit_brl_2026'],'kind':'credit','asset_id':asset.asset_id})
    vp_costs=sum((1 if item['kind']=='cost' else -1)*item['amount']/(1+rate)**item['t'] for item in ledger)
    f2=None
    if pcc_kw is not None:
        if len(pcc_kw)!=365*96: raise EconomicGateError('F2 requer 35040 valores de PCC em 15 minutos')
        f2=max(amount(v,'PCC') for v in pcc_kw)
        if f2>2500+1e-5: raise EconomicGateError('PCC acima de 2500 kW')
    gates={'service_equivalence_verified':bool(service_equivalence_verified),
           'cost_boundary_verified':bool(cost_boundary_verified),
           'f2_annual_series_available':f2 is not None}
    released=all(gates.values())
    return {'version':VERSION,'status':'F1_F2_READY_FOR_COMPARISON' if released else 'DIAGNOSTIC_ONLY_NOT_COMPARABLE',
            'vp_costs_brl_2026':vp_costs,'vp_pkm':vp_pkm,
            'f1_diagnostic_brl_per_pkm':vp_costs/vp_pkm,
            'F1_brl_per_pkm':vp_costs/vp_pkm if released else None,
            'F2_kw':f2,'gates':gates,'ledger':ledger}

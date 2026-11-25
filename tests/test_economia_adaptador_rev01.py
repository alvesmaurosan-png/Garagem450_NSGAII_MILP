import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import pytest
from economia_adaptador_rev01 import Asset, CATEGORIES, EconomicGateError, evaluate, residual

def sample(**kwargs):
    initial={k:0. for k in CATEGORIES}
    annual={k:[0.]*20 for k in CATEGORIES}
    initial['fleet_purchase']=1000.
    annual['grid_energy']=[100.]*20
    params=dict(initial_costs=initial,annual_costs=annual,annual_pkm=[1000.]*20,assets=[])
    params.update(kwargs)
    return params

def test_g06_bev_original_t10():
    a=Asset('original','bev',1282419498.96,0,10,12,True)
    r=residual(a)
    assert r['credit_brl_2026']==pytest.approx(106868291.58,abs=.02)
    assert r['t']==10

def test_g06_bev_substituta_t20():
    a=Asset('substituta','bev',1282419498.96,10,20,12,True)
    assert residual(a)['credit_brl_2026']==pytest.approx(106868291.58,abs=.02)

def test_g06_instalacao():
    a=Asset('instalacao','electrical_installation',1501312.4,0,20,25,True)
    assert residual(a)['credit_brl_2026']==pytest.approx(150131.24)

def test_g06_carregador_sem_saldo():
    assert residual(Asset('charger','charger',6566964.45,0,20,20,True))['credit_brl_2026']==0

def test_g06_conexao_inelegivel():
    assert residual(Asset('connection','grid_connection',10000,0,20,30,False))['credit_brl_2026']==0

def test_g06_rejeita_elegibilidade_e_vida_incorretas():
    with pytest.raises(EconomicGateError): residual(Asset('c','grid_connection',100,0,20,30,True))
    with pytest.raises(EconomicGateError): residual(Asset('b','bev',100,0,10,10,True))

def test_pkm_20_anos_bau():
    out=evaluate(**sample(annual_pkm=[569130934.0742]*20))
    assert out['vp_pkm']==pytest.approx(5587811404.88,abs=.1)
    assert out['F1_brl_per_pkm'] is None

def test_aumento_custo_aumenta_f1_diagnostico():
    base=sample()
    a=evaluate(**base)
    base['initial_costs']['fleet_purchase']+=100
    b=evaluate(**base)
    assert b['f1_diagnostic_brl_per_pkm']>a['f1_diagnostic_brl_per_pkm']

def test_credito_reduz_vp_uma_vez_t10():
    base=evaluate(**sample())
    a=Asset('a','bev',1200,0,10,12,True)
    with_credit=evaluate(**sample(assets=[a]))
    expected=residual(a)['credit_brl_2026']/1.08**10
    assert base['vp_costs_brl_2026']-with_credit['vp_costs_brl_2026']==pytest.approx(expected)

def test_sem_zero_implicito():
    d=sample(); d['initial_costs']['fleet_purchase']=None
    with pytest.raises(EconomicGateError): evaluate(**d)

def test_dupla_contagem_bloqueada():
    with pytest.raises(EconomicGateError): evaluate(**sample(residual_costs_included_elsewhere=True))

def test_f1_bloqueado_sem_gates():
    assert evaluate(**sample())['F1_brl_per_pkm'] is None

def test_f1_f2_liberados_apenas_com_gates_e_serie():
    out=evaluate(**sample(pcc_kw=[2000.]*(365*96),service_equivalence_verified=True,cost_boundary_verified=True))
    assert out['status']=='F1_F2_READY_FOR_COMPARISON'
    assert out['F1_brl_per_pkm'] is not None and out['F2_kw']==2000

def test_pcc_acima_limite_rejeitado():
    with pytest.raises(EconomicGateError): evaluate(**sample(pcc_kw=[2501.]*(365*96)))

def test_reposicao_t10_descontada_t10():
    d=sample();d['annual_costs']['fleet_replacement'][9]=1080
    a=evaluate(**d)
    d['annual_costs']['fleet_replacement'][9]=0
    b=evaluate(**d)
    assert a['vp_costs_brl_2026']-b['vp_costs_brl_2026']==pytest.approx(1080/1.08**10)

def test_bau_ponte_documental():
    # Conferência aritmética da ponte documentada, sem usar estes números como R0.
    vp=2702683343.20+6566964.45-72461307.52
    assert vp==pytest.approx(2636789000.13,abs=.02)
    assert vp/5587811404.88==pytest.approx(.471882,abs=.000001)

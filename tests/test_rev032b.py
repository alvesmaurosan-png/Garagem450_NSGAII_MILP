import json, sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from reconciliar_economia_rev032b import run

@pytest.fixture
def setup(tmp_path):
    source=Path(__file__).resolve().parents[1]
    (tmp_path/'parametros').mkdir()
    (tmp_path/'resultados'/'bau_REV032').mkdir(parents=True)
    for name in ('bau_rev032.json','Base_Mestre_450_Reconciliada_REV02.xlsx'):
        (tmp_path/'parametros'/name).write_bytes((source/'parametros'/name).read_bytes())
    p=tmp_path/'resultados'/'bau_REV032'/'auditoria_REV032.json'
    p.write_text(json.dumps({'physical':{'annual_ac_kwh':32038034.272552636,'peak_pcc_import_kw':3841.5203747807027},'BAU_no_2500_kw_cap':True}),encoding='utf-8')
    config=json.loads((source/'parametros'/'economia_rev032b.json').read_text(encoding='utf-8'))
    return tmp_path,config

def test_bloqueio_total(setup):
    root,cfg=setup
    r=run(cfg,root)
    assert r['cost_rows']==294 and r['blocked_cost_rows']==294
    assert r['master_active_records']==10
    assert r['F1_brl_per_pkm'] is None and r['LCOE_brl_per_kwh'] is None
    assert r['pcc_2500_applied_to_bau'] is False
    assert len(list((root/'resultados'/'bau_REV032b').glob('*')))==5

def test_uma_regra_validada_nao_desbloqueia_f1(setup):
    root,cfg=setup
    cfg['categories']['grid_energy']={'rule':'annual_energy','status':'VALIDATED','source':'tarifa auditada hipotetica para teste',
        'price_base_year':2026,'justification':'teste unitario apenas','parameters':{'tariff_brl_per_kwh':0.5}}
    r=run(cfg,root)
    assert r['validated_cost_rows']==21
    assert r['blocked_cost_rows']==273
    assert r['F1_brl_per_pkm'] is None

def test_sem_fonte_nao_habilita_regra(setup):
    root,cfg=setup
    cfg['categories']['fleet_purchase']['status']='VALIDATED'
    cfg['categories']['fleet_purchase']['parameters']={'unit_cost_brl_2026':100,'quantity':450}
    r=run(cfg,root)
    assert r['blocked_cost_rows']==294

def test_driver_alterado_rejeitado(setup):
    root,cfg=setup
    cfg['physical_drivers']['peak_pcc_import_kw']=2500
    with pytest.raises(ValueError,match='Driver fisico'):run(cfg,root)

import json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from reconciliar_economia_rev032a import run

def test_auditoria_sem_f1_e_sem_zerar_lacunas():
    root=Path(__file__).resolve().parents[1]
    cfg=json.loads((root/'parametros'/'bau_rev032.json').read_text(encoding='utf-8'))
    result=run(cfg,root)
    assert result['cost_rows']==294
    assert result['pending_cost_rows']==294
    assert result['F1_brl_per_pkm'] is None
    assert result['LCOE_brl_per_kwh'] is None
    assert result['pcc_2500_applied_to_bau'] is False
    assert result['master_active_records']==10

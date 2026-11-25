"""Testes controlados REV02.3a. Colocar em tests/."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from scipy.optimize import linprog
from otimizar_recarga_rev023a import prepare, decode, validate, run_search, fixed_milp


def toy():
    # Dois veiculos, 4 slots de 15 min; cada um precisa de 34.5 kWh.
    tr=np.zeros((2,4));tr[:,0]=34.5
    allowed=np.zeros((2,4),dtype=bool);allowed[:,1:]=True
    return prepare(tr,allowed,15)


def test_lp_and_constructive_upper():
    d=toy()
    lp=linprog(d['c'],A_ub=d['Aub'],b_ub=d['bub'],A_eq=d['Aeq'],b_eq=d['beq'],bounds=d['bounds'],method='highs')
    assert lp.success
    x,y,_=decode(d,lp.x)
    audit,_=validate(d,x,y)
    assert audit['valid']
    assert abs(x.sum()-69)<1e-6
    assert audit['ports_from_positive_lp']<=2


def test_fixed_ports_and_certification():
    d=toy()
    lp=linprog(d['c'],A_ub=d['Aub'],b_ub=d['bub'],A_eq=d['Aeq'],b_eq=d['beq'],bounds=d['bounds'],method='highs')
    assert lp.success
    # Uma porta pode fornecer 3*34.5 kWh em 3 slots, suficiente para 69 kWh.
    rec,sol=fixed_milp(d,1,None,10,.01)
    assert rec['classification']=='FEASIBLE_CERTIFIED_BY_AUDIT'
    assert sol is not None
    r,_=run_search(d,float(lp.x[d['pidx']]),lp.x,None,10,5,.01)
    assert r['minimum_certified'] and r['upper_bound_ports']==1


def test_infeasible_fixed_zero():
    d=toy()
    rec,sol=fixed_milp(d,0,None,10,.01)
    assert rec['classification']=='INFEASIBLE_CERTIFIED'
    assert sol is None

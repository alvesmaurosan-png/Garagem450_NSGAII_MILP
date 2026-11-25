import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "dados" / "processados"
REP = ROOT / "resultados" / "reproducao_REV01"


def test_450_veiculos_unicos():
    df = pd.read_csv(REP / "dia_sintetico_450_sessoes_REV01.csv")
    assert len(df) == 450
    assert df["vehicle_id"].nunique() == 450


def test_conservacao_energia():
    df = pd.read_csv(REP / "dia_sintetico_450_sessoes_REV01.csv")
    hourly = pd.read_csv(
        REP / "dia_sintetico_450_carga_horaria_REV01.csv"
    )
    assert np.isclose(
        df["energy_dc_kwh"].sum(),
        hourly["energy_dc_kwh"].sum(),
        atol=0.01,
        rtol=0,
    )


def test_janelas_temporais():
    df = pd.read_csv(REP / "dia_sintetico_450_sessoes_REV01.csv")
    assert (df["charge_start_min"] >= df["earliest_min"]).all()
    assert (df["charge_end_min"] <= df["deadline_min"]).all()
    assert (df["charge_end_min"] <= 1440).all()


def test_metricas_reproduzidas():
    metrics = json.loads(
        (REP / "dia_sintetico_450_validacao_REV01.json").read_text(
            encoding="utf-8"
        )
    )
    assert metrics["synthetic_vehicles"] == 450
    assert metrics["peak_concurrent_sessions"] == 157
    assert np.isclose(
        metrics["energy_synthetic_dc_kwh"],
        85369.312027,
        atol=0.01,
    )


def test_comparacao_referencia():
    for name in (
        "dia_sintetico_450_sessoes_REV01.csv",
        "dia_sintetico_450_carga_horaria_REV01.csv",
    ):
        reference = pd.read_csv(REF / name)
        reproduced = pd.read_csv(REP / name)
        pd.testing.assert_frame_equal(
            reference,
            reproduced,
            check_exact=False,
            rtol=1e-8,
            atol=1e-5,
        )

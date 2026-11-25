
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "dados" / "originais" / "sessoes_conciliadas_115.csv"
OUTPUT = ROOT / "resultados" / "reproducao_REV01"

ANCHOR = 10560
N_VEHICLES = 450
TOL = 2e-5


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)

    source = pd.read_csv(SOURCE, encoding="utf-8-sig")

    assert len(source) == 115
    assert source["block_id"].nunique() == 115
    assert (source["power_dc_kw"] > 0).all()

    rows = []

    for j in range(N_VEHICLES):
        a = source.iloc[j % len(source)]
        replica = j // len(source)

        offset = int(((j * 37 + replica * 11) % 61) - 30)

        earliest = float(a["earliest_charge_min"]) + offset
        start = float(a["charge_start_abs_min"]) + offset
        end = float(a["charge_end_abs_min"]) + offset
        deadline = float(a["deadline_min"]) + offset

        correction = max(0, ANCHOR - earliest)

        earliest += correction
        start += correction
        end += correction
        deadline += correction

        ret = float(a["return_abs_min"]) + offset + correction

        rows.append({
            "vehicle_id": f"SYN_{j + 1:03d}",
            "source_block_id": a["block_id"],
            "source_vehicle_id": a["vehicle_id_representative"],
            "source_cycle_id": a["cycle_id"],
            "source_charger_id": a["charger_id"],
            "replica_index": replica,
            "offset_min": offset,
            "return_min": round(ret - ANCHOR, 6),
            "earliest_min": round(earliest - ANCHOR, 6),
            "charge_start_min": round(start - ANCHOR, 6),
            "charge_end_min": round(end - ANCHOR, 6),
            "deadline_min": round(deadline - ANCHOR, 6),
            "energy_dc_kwh": float(a["energy_dc_kwh"]),
            "power_dc_kw": float(a["power_dc_kw"]),
            "energy_basis": "observed_sample_replication",
            "distance_km": None,
            "passengers_mean": None,
            "pkm": None,
        })

    df = pd.DataFrame(rows)

    assert len(df) == 450
    assert df["vehicle_id"].nunique() == 450

    assert (
        (df["charge_start_min"] >= df["earliest_min"] - 1e-6)
        & (df["charge_end_min"] <= df["deadline_min"] + 1e-6)
        & (df["charge_end_min"] <= 1440)
    ).all()

    expected_energy = (
        df["power_dc_kw"]
        * (df["charge_end_min"] - df["charge_start_min"])
        / 60
    )

    assert np.allclose(
        df["energy_dc_kwh"],
        expected_energy,
        rtol=0,
        atol=TOL,
    )

    hourly_rows = []

    for hour in range(24):
        start = hour * 60
        stop = start + 60

        overlap = np.maximum(
            0,
            np.minimum(df["charge_end_min"].to_numpy(), stop)
            - np.maximum(df["charge_start_min"].to_numpy(), start),
        )

        energy = float(
            np.sum(df["power_dc_kw"].to_numpy() * overlap / 60)
        )

        simultaneous = int(np.sum(
            (df["charge_start_min"].to_numpy() < stop)
            & (df["charge_end_min"].to_numpy() > start)
        ))

        hourly_rows.append({
            "hour": hour,
            "energy_dc_kwh": energy,
            "mean_power_dc_kw": energy,
            "active_sessions_overlapping_hour": simultaneous,
        })

    hourly = pd.DataFrame(hourly_rows)

    assert np.isclose(
        df["energy_dc_kwh"].sum(),
        hourly["energy_dc_kwh"].sum(),
        atol=0.01,
        rtol=0,
    )

    events = []

    for r in df.itertuples():
        events.append((r.charge_start_min, 1, r.power_dc_kw))
        events.append((r.charge_end_min, -1, -r.power_dc_kw))

    concurrent = 0
    power = 0.0
    peak_concurrent = 0
    peak_power = 0.0

    for _, delta_n, delta_kw in sorted(
        events, key=lambda x: (x[0], x[1])
    ):
        concurrent += delta_n
        power += delta_kw
        peak_concurrent = max(peak_concurrent, concurrent)
        peak_power = max(peak_power, power)

    metrics = {
        "sample_sessions": len(source),
        "synthetic_vehicles": len(df),
        "source_unique_vehicles": int(
            source["vehicle_id_representative"].nunique()
        ),
        "energy_sample_dc_kwh": float(
            source["energy_dc_kwh"].sum()
        ),
        "energy_synthetic_dc_kwh": float(
            df["energy_dc_kwh"].sum()
        ),
        "energy_hourly_dc_kwh": float(
            hourly["energy_dc_kwh"].sum()
        ),
        "peak_hourly_dc_kw": float(
            hourly["mean_power_dc_kw"].max()
        ),
        "peak_instantaneous_dc_kw": peak_power,
        "peak_concurrent_sessions": peak_concurrent,
        "source_charger_ids": int(
            source["charger_id"].nunique()
        ),
        "minimum_138kw_ports_for_fixed_schedule": peak_concurrent,
        "earliest_start_min": float(
            df["charge_start_min"].min()
        ),
        "latest_end_min": float(
            df["charge_end_min"].max()
        ),
        "deadlines_beyond_day": int(
            (df["deadline_min"] > 1440).sum()
        ),
        "pkm_status": "UNDEFINED_NO_DISTANCE_OR_OCCUPANCY",
        "service_status": "UNVALIDATED_NO_BLOCK_SCHEDULE",
        "grid_pcc_status": (
            "NOT_TESTED_NO_AC_LOSSES_OR_OPTIMIZED_DISPATCH"
        ),
        "source_sha256": hashlib.sha256(
            SOURCE.read_bytes()
        ).hexdigest(),
        "generator_version": (
            "REV01 deterministic modulo-115 offset [-30,+30]"
        ),
    }

    df.to_csv(
        OUTPUT / "dia_sintetico_450_sessoes_REV01.csv",
        index=False,
        float_format="%.6f",
    )

    hourly.to_csv(
        OUTPUT / "dia_sintetico_450_carga_horaria_REV01.csv",
        index=False,
        float_format="%.6f",
    )

    (OUTPUT / "dia_sintetico_450_validacao_REV01.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    print("\nREPRODUCAO REV01 CONCLUIDA")


if __name__ == "__main__":
    main()


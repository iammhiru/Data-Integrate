"""
tools/oee_sim_check.py
──────────────────────
Mô phỏng N giờ dữ liệu simulator (KHÔNG cần Kafka/PostgreSQL) để kiểm tra
OEE dự kiến mà batch_kpi sẽ tính được:

    A = run_sec / planned_sec
    P = ideal_time_sec / run_sec  (ideal_time_sec = total × 60 / design_speed)
    Q = good_count / total_count
    OEE = A × P × Q

Cũng kiểm tra bất biến: TotalCounter == GoodCounter + DefectCounter, và
AlarmCode chỉ khác 0 khi FAULTED.

Chạy:
    python tools/oee_sim_check.py [giờ_mô_phỏng]
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.tag_loader import load_all_tags  # noqa: E402
from services.simulator import (  # noqa: E402
    STATE_FAULTED,
    STATE_MAINTENANCE,
    STATE_RUNNING,
    STATE_STARTING,
    STATE_STOPPED,
    SimulatedSource,
)

TICK_S = 0.2


def main() -> int:
    hours = float(sys.argv[1]) if len(sys.argv) > 1 else 6.0
    tags = load_all_tags()
    source = SimulatedSource(tags=tags, enqueue=lambda _p: None)

    n_ticks = int(hours * 3600 / TICK_S)
    acc: dict[str, dict] = {}

    for i in range(n_ticks):
        now = i * TICK_S
        # Chỉ tiến trạng thái + sản lượng (không phát 404 tag mỗi nhịp —
        # với mục đích kiểm tra OEE thì không cần).
        for rt in source._runtimes.values():
            rt.sim_time += TICK_S
            source._drift_speed(rt, TICK_S)
            source._advance_state(rt, TICK_S)
            source._advance_production(rt, TICK_S)
        for rt in source._runtimes.values():
            st = acc.setdefault(rt_key(rt, source), {
                "state_sec": Counter(), "total": 0, "good": 0, "defect": 0,
                "alarm_bad": 0, "alarm_ok": 0, "design": rt.design_speed,
            })
            st["state_sec"][rt.state] += TICK_S
            st["total"] = rt.total
            st["good"] = rt.good
            st["defect"] = rt.defect
            if rt.state == STATE_FAULTED and rt.alarm_code == 0:
                st["alarm_bad"] += 1
            if rt.state != STATE_FAULTED and rt.alarm_code != 0:
                st["alarm_bad"] += 1

    print(f"\n=== Mô phỏng {hours:.1f} giờ — {n_ticks} tick ===\n")
    print(f"{'máy':<22}{'A':>7}{'P':>7}{'Q':>7}{'OEE':>8}{'run%':>7}{'NG%':>7}  trạng thái")

    oee_list = []
    for key, st in sorted(acc.items()):
        sec = st["state_sec"]
        total_s = sum(sec.values())
        run_s = sec.get(STATE_RUNNING, 0.0)
        # planned = tổng thời gian (không trừ bảo trì — theo công thức batch)
        planned_s = total_s
        a = run_s / planned_s if planned_s else 0.0
        # ideal_time_sec = total × 60 / design_speed ; P = ideal / run
        ideal = st["total"] * 60.0 / st["design"] if st["design"] else 0.0
        p = ideal / run_s if run_s else 0.0
        q = st["good"] / st["total"] if st["total"] else 0.0
        oee = a * p * q
        oee_list.append(oee)
        if st["alarm_bad"]:
            print(f"  !! {key}: alarm không nhất quán {st['alarm_bad']} lần")
        # bất biến Total = Good + Defect
        if st["total"] != st["good"] + st["defect"]:
            print(f"  !! {key}: Total({st['total']}) != Good+Defect "
                  f"({st['good']}+{st['defect']})")

        dist = " ".join(
            f"{name}={sec.get(code, 0) / total_s * 100:.1f}%"
            for code, name in ((STATE_RUNNING, "RUN"), (STATE_STOPPED, "STOP"),
                               (STATE_FAULTED, "FLT"), (STATE_MAINTENANCE, "MNT"),
                               (STATE_STARTING, "STR"))
        )
        print(f"{key:<22}{a * 100:>6.1f}%{p * 100:>6.1f}%{q * 100:>6.1f}%"
              f"{oee * 100:>7.1f}%{run_s / total_s * 100:>6.1f}%"
              f"{(st['defect'] / st['total'] * 100 if st['total'] else 0):>6.2f}%  {dist}")

    if oee_list:
        avg = sum(oee_list) / len(oee_list)
        print(f"\nOEE trung bình: {avg * 100:.1f}%  "
              f"(min {min(oee_list) * 100:.1f}% / max {max(oee_list) * 100:.1f}%)")
    return 0


def rt_key(rt, source) -> str:
    for key, r in source._runtimes.items():
        if r is rt:
            return key.split(".")[-1]
    return "?"


if __name__ == "__main__":
    sys.exit(main())

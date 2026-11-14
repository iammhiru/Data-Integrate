"""
tools/sim_pipeline_check.py
───────────────────────────
Mô phỏng đúng như batch_kpi đọc dữ liệu:
  · Mỗi phút: chốt trạng thái + counter delta.
  · Tính lại A / P / Q / OEE đúng công thức trong `spark/apps/batch_kpi.py`
    và `services/state-api/analytics.py`.

Mục đích: xác nhận dữ liệu simulator → PostgreSQL → UI sẽ ra OEE thực tế
(65%–85%), không còn hiện tượng "P > 1", "Total = Good = Defect", "alarm
không nhất quán".

Chạy:
    python tools/sim_pipeline_check.py [phút]
"""

from __future__ import annotations

import sys
from collections import defaultdict
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
    minutes = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    tags = load_all_tags()
    source = SimulatedSource(tags=tags, enqueue=lambda _p: None)

    # machine_id -> {state_sec, total_d, good_d, defect_d}
    per_min: dict[str, dict] = defaultdict(lambda: {
        "state_sec": defaultdict(float), "total": 0, "good": 0, "defect": 0,
        "design": 0.0,
    })
    prev = {mid: (rt.total, rt.good, rt.defect) for mid, rt in source._runtimes.items()}
    alarms_bad = 0
    alarm_nonzero_outside_fault = 0

    n_ticks = int(minutes * 60 / TICK_S)
    for i in range(n_ticks):
        for rt in source._runtimes.values():
            rt.sim_time += TICK_S
            source._drift_speed(rt, TICK_S)
            source._advance_state(rt, TICK_S)
            source._advance_production(rt, TICK_S)
            if rt.state == STATE_FAULTED and rt.alarm_code == 0:
                alarms_bad += 1
            if rt.state != STATE_FAULTED and rt.alarm_code != 0:
                alarm_nonzero_outside_fault += 1
        # Chốt theo phút
        if (i + 1) % int(60 / TICK_S) == 0:
            for mid, rt in source._runtimes.items():
                d = per_min[mid]
                d["state_sec"][rt.state] += 60.0
                d["design"] = rt.design_speed
                d["total"] += rt.total - prev[mid][0]
                d["good"] += rt.good - prev[mid][1]
                d["defect"] += rt.defect - prev[mid][2]
                prev[mid] = (rt.total, rt.good, rt.defect)

    print(f"\n=== Mô phỏng {minutes} phút — mô phỏng đúng công thức batch ===\n")
    print(f"{'máy':<22}{'A':>8}{'P':>8}{'Q':>8}{'OEE':>9}{'tổng':>10}{'đạt':>10}{'NG':>7}")

    oees, bad_p, bad_invariant = [], 0, 0
    for mid, d in sorted(per_min.items()):
        sec = d["state_sec"]
        total_s = sum(sec.values())
        run_s = sec.get(STATE_RUNNING, 0.0)
        planned_s = total_s
        a = run_s / planned_s if planned_s else 0.0
        ideal = d["total"] * 60.0 / d["design"] if d["design"] else 0.0
        p = ideal / run_s if run_s else 0.0
        q = d["good"] / d["total"] if d["total"] else 0.0
        oee = a * p * q
        if p > 1.0:
            bad_p += 1
        if d["total"] != d["good"] + d["defect"]:
            bad_invariant += 1
        if d["design"]:
            oees.append(oee)
            print(f"{mid:<22}{a * 100:>7.1f}%{p * 100:>7.1f}%{q * 100:>7.1f}%"
                  f"{oee * 100:>8.1f}%{d['total']:>10,}{d['good']:>10,}{d['defect']:>7,}")

    print(f"\nOEE trung bình (máy có DesignSpeed): "
          f"{sum(oees) / len(oees) * 100:.1f}%" if oees else "n/a")
    print(f"P > 1 (sai): {bad_p}   |   Total != Good+Defect: {bad_invariant}")
    print(f"Alarm sai: FAULTED mà code=0 → {alarms_bad}; không FAULTED mà code!=0 → "
          f"{alarm_nonzero_outside_fault}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

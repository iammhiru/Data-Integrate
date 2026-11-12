"""
Kiểm tra THỰC TẾ: simulator có sinh giá trị hợp lý cho mọi tag không.

Cách làm: dựng lại logic generate() của mock-simulator.ts bằng cách chạy
TypeScript? Không cần — thay vào đó dùng Node + tsx để import thật.

Cách đơn giản & đáng tin: dùng Playwright để đọc UI, hoặc đơn giản hơn —
parse source để tìm các tên tag được nhắc đến trong simulator.
"""
import re
import io
import collections

base = r"e:\Work\SFSVcongty\Laird\Code\Data-Integrate\dashboard\frontend\src\mock"
sim = io.open(base + r"\mock-simulator.ts", encoding="utf-8").read()
cat = io.open(base + r"\catalog.gen.ts", encoding="utf-8").read()

pairs = re.findall(
    r'"name":\s*"(\w+)",\s*"dataType":\s*"(\w+)",\s*"unit":\s*(null|"[^"]*")', cat
)
by_type = collections.defaultdict(set)
unit_of = {}
for n, d, u in pairs:
    by_type[d].add(n)
    unit_of[n] = u.strip('"') if u != "null" else None

# Mọi khái niệm tag được nhắc tên trong simulator (dùng ở mọi ngữ cảnh)
mentioned = set(re.findall(r'"(\w+)"', sim))

# Những tag có BẢN CHẤT riêng (không nên rơi vào giá trị mặc định chung)
SPECIAL_INT = {
    "MachineState", "MachineMode", "AlarmCode", "HeadCount",
    "BottlesPerCase", "CansPerCase", "CavityCount", "LayerCount",
    "RejectReason", "CaseFormat", "InspectResult", "PrintQuality",
    "SeamQuality", "CIPPhase",
}
SPECIAL_BOOL = {
    "EmergencyStop", "Starved", "Blocked", "CirculationOn", "HeatingOn",
    "InkLow", "FilmLow", "HopperLevelLow", "LabelRollLow",
    "CameraFault", "CapMissing", "CaseJam", "GripperFault", "LabelMissing",
    "TorqueHigh",
}
SPECIAL_FLOAT = {
    "DesignSpeed", "CurrentSpeed", "LabelRollRemaining", "FilmRemaining",
    "MoldTemp", "HeaterTemp", "ProductTemp", "WaterTemp", "RinseWaterTemp",
    "TankTemp", "DefectRate", "FillLevel", "HopperLevel", "InkLevel",
    "ChemicalDose", "pH", "Conductivity", "WaterConductivity",
}

print("=== Int chưa có giá trị riêng ===")
miss_i = [n for n in sorted(by_type["Int"]) if n not in SPECIAL_INT]
print("   ", miss_i or "(không)")

print("=== Boolean chưa có giá trị riêng ===")
miss_b = [n for n in sorted(by_type["Boolean"]) if n not in SPECIAL_BOOL]
print("   ", miss_b or "(không)")

print("=== Float chưa có giá trị riêng (rơi vào UNIT_PROFILE) ===")
miss_f = [n for n in sorted(by_type["Float"]) if n not in SPECIAL_FLOAT]
print("   ", miss_f or "(không)")

# Đơn vị dùng chưa có trong UNIT_PROFILE?
m = re.search(r"const UNIT_PROFILE[^=]*=\{(.*?)\n\};", sim, re.S)
prof = set()
if m:
    prof = set(re.findall(r'["\']?([\w/%^.]+)["\']?\s*:\s*\[', m.group(1)))
print("\n=== UNIT_PROFILE keys ===")
print("   ", sorted(prof))

units_used = {unit_of[n] for n in by_type["Float"] if unit_of.get(n)}
missing_units = sorted(u for u in units_used if u not in prof)
print("=== unit của Float chưa có profile ===")
print("   ", missing_units or "(không)")

print("\n=== Long chưa xử lý riêng ===")
print("   ", sorted(by_type["Long"]))

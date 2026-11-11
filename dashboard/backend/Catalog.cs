namespace Factory.Api;

public record TagDefinition(string TagCode, string TagName, string ValueType, string? Unit, string Description);
public record MachineDefinition(string MachineId, string MachineName, string MachineType, string LineId, TagDefinition[] Tags);
public sealed class Catalog
{
    // Mirrors postgres/init/02_seed_master_data.sql; DB master replaces this fallback.
    public static readonly TagDefinition[] TelemetryFields = [
        new("temperature", "temperature", "Double", "°C", "Nhiệt độ"),
        new("pressure", "pressure", "Double", "bar", "Áp suất"),
        new("speed", "speed", "Double", "rpm", "Tốc độ"),
        new("energy", "energy", "Double", "kWh", "Điện năng theo nguồn"),
        new("vibration", "vibration", "Double", null, "Độ rung (nguồn chưa định nghĩa đơn vị)"),
        new("status", "status", "String", null, "RUNNING / IDLE / STOPPED"),
        new("operatingMode", "operatingMode", "String", null, "Chế độ vận hành")
    ];
    public static readonly TagDefinition[] Fields = [..TelemetryFields.Where(t => t.TagCode is not ("vibration" or "operatingMode")),
        new("productionRate", "productionRate", "Double", "pcs/min", "Tốc độ sản xuất theo cửa sổ 1 phút"),
        new("totalQty", "totalQty", "Double", "pcs", "Tổng sản lượng trong cửa sổ 1 phút"),
        new("goodQty", "goodQty", "Double", "pcs", "Sản lượng đạt trong cửa sổ 1 phút"),
        new("rejectQty", "rejectQty", "Double", "pcs", "Sản lượng lỗi trong cửa sổ 1 phút"),
        new("avgTemperature1m", "avgTemperature1m", "Double", "°C", "Nhiệt độ trung bình 1 phút"),
        new("maxTemperature1m", "maxTemperature1m", "Double", "°C", "Nhiệt độ lớn nhất 1 phút"),
        new("avgPressure1m", "avgPressure1m", "Double", "bar", "Áp suất trung bình 1 phút"),
        new("avgSpeed1m", "avgSpeed1m", "Double", "rpm", "Tốc độ trung bình 1 phút"),
        new("sumEnergy1m", "sumEnergy1m", "Double", "kWh", "Tổng energy theo Spark trong cửa sổ 1 phút"),
        new("sampleCount1m", "sampleCount1m", "Double", null, "Số mẫu trong cửa sổ 1 phút"),
        new("missingCount1m", "missingCount1m", "Double", null, "Số mẫu thiếu trường trong cửa sổ 1 phút")
    ];
    private MachineDefinition[] machines = Enumerable.Range(1, 100).Select(i => new MachineDefinition($"M{i:000}", $"Machine {i:000}", new[] { "CNC", "PRESS", "INJECTION", "PACKING" }[i % 4], $"LINE-{(i - 1) / 20 + 1}", Fields)).ToArray();
    public MachineDefinition[] Machines => Volatile.Read(ref machines);
    public string Source { get; private set; } = "repository-seed";
    public void Replace(MachineDefinition[] value) { if (value.Length > 0) { Interlocked.Exchange(ref machines, value); Source = "postgres-master"; } }
    public bool HasTag(string machine, string tag) => Machines.Any(m => m.MachineId == machine) && Fields.Any(t => t.TagCode == tag);
}

using System.Text.Json;
namespace Factory.Api;

public record TagValue(string MachineId, string TagCode, string TagName, JsonElement Value, string ValueType, string? Unit, string Quality, DateTimeOffset EventTime, DateTimeOffset ReceivedAt, string EventId);
public record Point(DateTimeOffset Time, JsonElement Value, string Quality);
public record Snapshot(long Revision, string Mode, string SourceStatus, string Topic, string CatalogSource, TagValue[] Tags);
public sealed class TelemetryStore(IConfiguration config, Catalog catalog)
{
    public static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web);
    private readonly object gate = new();
    private readonly Dictionary<string, TagValue> latest = [];
    private readonly Dictionary<string, Queue<Point>> history = [];
    private readonly Dictionary<string, DateTimeOffset> versions = [];
    private readonly HashSet<string> seen = [];
    private readonly Queue<string> seenOrder = [];
    private readonly Queue<object> errors = [];
    private long received, accepted, duplicate, late, invalid, revision, missingFields;
    private string sourceStatus = "starting";
    private string? lastError;
    public string Mode => config["Telemetry:Mode"] ?? "Mock";
    public string Topic => config["Kafka:Topic"] ?? "realtime-metrics";
    public string InputFormat => config["Kafka:Format"] ?? "Metrics";
    public string SourceStatus { get { lock (gate) return sourceStatus; } }
    public void SetSource(string status, string? error = null) { lock (gate) { sourceStatus = status; lastError = error; } }
    public bool Apply(string json, string? key = null)
    {
        lock (gate)
        {
            received++;
            try
            {
                using var doc = JsonDocument.Parse(json);
                var e = doc.RootElement;
                string Str(JsonElement p, string n) => p.GetProperty(n).GetString() is { Length: > 0 } s ? s : throw new FormatException($"Missing {n}");
                var id = Str(e, "eventId");
                if (!Guid.TryParse(id, out _)) throw new FormatException("Invalid eventId");
                if (e.GetProperty("schemaVersion").GetInt32() != 1 || Str(e, "eventType") != "machine.telemetry") throw new FormatException("Expected repository envelope v1 machine.telemetry");
                Str(e, "source");
                var machine = Str(e, "machineId");
                if (key != null && key != machine) throw new FormatException("Kafka key differs from machineId");
                if (!catalog.Machines.Any(m => m.MachineId == machine)) throw new FormatException("Machine not in master catalog");
                var time = e.GetProperty("timestamp").GetDateTimeOffset();
                if (time.Offset != TimeSpan.Zero) throw new FormatException("timestamp must be UTC");
                if (e.TryGetProperty("ingestedAt", out var ingest) && ingest.ValueKind != JsonValueKind.Null) ingest.GetDateTimeOffset();
                var payload = e.GetProperty("payload");
                if (payload.ValueKind != JsonValueKind.Object) throw new FormatException("payload must be object");
                var changes = new List<(TagDefinition Field, JsonElement Value)>();
                foreach (var field in Catalog.TelemetryFields)
                {
                    var value = payload.TryGetProperty(field.TagName, out var v) ? v.Clone() : JsonSerializer.SerializeToElement<object?>(null);
                    if (value.ValueKind != JsonValueKind.Null)
                    {
                        if (field.ValueType == "String" ? value.ValueKind != JsonValueKind.String : value.ValueKind != JsonValueKind.Number || !value.TryGetDouble(out var n) || !double.IsFinite(n)) throw new FormatException($"Invalid payload.{field.TagName}");
                        if (field.TagName == "status" && value.GetString() is not ("RUNNING" or "IDLE" or "STOPPED")) throw new FormatException("Invalid status");
                    }
                    changes.Add((field, value));
                }
                if (!seen.Add(id)) { duplicate++; return false; }
                seenOrder.Enqueue(id); if (seenOrder.Count > 50000) seen.Remove(seenOrder.Dequeue());
                // Envelope represents one machine snapshot; apply atomically, never partially.
                if (latest.TryGetValue(machine + "/status", out var old) && time <= old.EventTime) { late++; return false; }
                var now = DateTimeOffset.UtcNow;
                foreach (var (field, value) in changes)
                {
                    var k = machine + "/" + field.TagCode;
                    var quality = value.ValueKind == JsonValueKind.Null ? "Missing" : "Present";
                    if (quality == "Missing") missingFields++;
                    latest[k] = new(machine, field.TagCode, field.TagName, value, field.ValueType, field.Unit, quality, time, now, id);
                    if (!history.TryGetValue(k, out var queue)) history[k] = queue = new();
                    queue.Enqueue(new(time, value, quality)); while (queue.Count > 180) queue.Dequeue();
                }
                accepted++; revision++; return true;
            }
            catch (Exception ex) when (ex is JsonException or KeyNotFoundException or InvalidOperationException or FormatException or ArgumentException)
            {
                invalid++; errors.Enqueue(new { at = DateTimeOffset.UtcNow, reason = ex.Message }); while (errors.Count > 20) errors.Dequeue(); return false;
            }
        }
    }
    public bool ApplyMetric(string json, string? key = null)
    {
        lock (gate)
        {
            received++;
            try
            {
                using var doc = JsonDocument.Parse(json);
                var e = doc.RootElement;
                var machine = e.GetProperty("machineId").GetString() ?? throw new FormatException("Missing machineId");
                if (key != null && key != machine) throw new FormatException("Kafka key differs from machineId");
                if (!catalog.Machines.Any(m => m.MachineId == machine)) throw new FormatException("Machine not in master catalog");
                var type = e.GetProperty("metricType").GetString();
                var time = e.GetProperty("lastEventTime").GetDateTimeOffset();
                var version = e.GetProperty("emittedAt").GetDateTimeOffset();
                var start = e.GetProperty("windowStart").GetDateTimeOffset();
                var end = e.GetProperty("windowEnd").GetDateTimeOffset();
                if (time.Offset != TimeSpan.Zero || version.Offset != TimeSpan.Zero || start.Offset != TimeSpan.Zero || end.Offset != TimeSpan.Zero || end <= start) throw new FormatException("Invalid UTC metric timestamps/window");
                (string Source, string Target)[] mapping = type switch
                {
                    "machine.status.5s" => [("status", "status"), ("avgTemperature", "temperature"), ("avgPressure", "pressure"), ("avgSpeed", "speed"), ("sumEnergy", "energy")],
                    "machine.metric.1m" => [("avgTemperature", "avgTemperature1m"), ("maxTemperature", "maxTemperature1m"), ("avgPressure", "avgPressure1m"), ("avgSpeed", "avgSpeed1m"), ("sumEnergy", "sumEnergy1m"), ("sampleCount", "sampleCount1m"), ("missingCount", "missingCount1m")],
                    "production.rate.1m" => [("productionRate", "productionRate"), ("totalQty", "totalQty"), ("goodQty", "goodQty"), ("rejectQty", "rejectQty")],
                    _ => throw new FormatException("Unsupported metricType")
                };
                var updates = new List<(TagDefinition Field, JsonElement Value)>();
                foreach (var (sourceField, target) in mapping)
                {
                    var field = Catalog.Fields.First(t => t.TagCode == target);
                    var value = e.TryGetProperty(sourceField, out var v) ? v.Clone() : JsonSerializer.SerializeToElement<object?>(null);
                    if (value.ValueKind != JsonValueKind.Null)
                    {
                        if (target == "status") { if (value.ValueKind != JsonValueKind.String || value.GetString() is not ("RUNNING" or "IDLE" or "STOPPED")) throw new FormatException("Invalid metric status"); }
                        else if (value.ValueKind != JsonValueKind.Number || !value.TryGetDouble(out var n) || !double.IsFinite(n)) throw new FormatException($"Invalid {sourceField}");
                    }
                    updates.Add((field, value));
                }
                var id = "metric:" + Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(System.Text.Encoding.UTF8.GetBytes(json)));
                if (!seen.Add(id)) { duplicate++; return false; }
                seenOrder.Enqueue(id); if (seenOrder.Count > 50000) seen.Remove(seenOrder.Dequeue());
                var changed = false;
                foreach (var (field, value) in updates)
                {
                    var k = machine + "/" + field.TagCode;
                    // Spark republishes open windows. Same event time with later emittedAt is a correction.
                    var previous = versions.TryGetValue(k, out var savedVersion) ? savedVersion : DateTimeOffset.MinValue;
                    if (latest.TryGetValue(k, out var old) && (time < old.EventTime || (time == old.EventTime && version <= previous))) continue;
                    var quality = value.ValueKind == JsonValueKind.Null ? "Missing" : "Present";
                    if (quality == "Missing") missingFields++;
                    latest[k] = new(machine, field.TagCode, field.TagName, value, field.ValueType, field.Unit, quality, time, DateTimeOffset.UtcNow, id);
                    versions[k] = version;
                    if (!history.TryGetValue(k, out var points)) history[k] = points = new();
                    points.Enqueue(new(time, value, quality)); while (points.Count > 180) points.Dequeue();
                    changed = true;
                }
                if (!changed) { late++; return false; }
                accepted++; revision++; return true;
            }
            catch (Exception ex) when (ex is JsonException or KeyNotFoundException or InvalidOperationException or FormatException or ArgumentException)
            {
                invalid++; errors.Enqueue(new { at = DateTimeOffset.UtcNow, reason = ex.Message }); while (errors.Count > 20) errors.Dequeue(); return false;
            }
        }
    }
    public Snapshot Snapshot() { lock (gate) return new(revision, Mode, sourceStatus, Topic, catalog.Source, latest.Values.ToArray()); }
    public Point[] Series(string machine, string tag) { lock (gate) return history.TryGetValue(machine + "/" + tag, out var q) ? q.ToArray() : []; }
    public object Diagnostics() { lock (gate) return new { mode = Mode, topic = Topic, sourceStatus, received, accepted, duplicate, late, invalid, missingFields, revision, lastError, errors = errors.ToArray() }; }
}

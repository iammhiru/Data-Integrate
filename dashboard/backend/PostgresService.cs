using Npgsql;
namespace Factory.Api;

public sealed class PostgresService : IAsyncDisposable
{
    private readonly NpgsqlDataSource? source;
    public bool Configured => source != null;
    public string Status { get; private set; } = "not-configured";
    public PostgresService(IConfiguration config)
    {
        var connection = config.GetConnectionString("Postgres");
        if (!string.IsNullOrWhiteSpace(connection)) { source = NpgsqlDataSource.Create(connection); Status = "configured"; }
    }
    public void MarkError() => Status = "error";
    public async Task<List<Dictionary<string, object?>>> Query(string sql, DateOnly? from, DateOnly? to, string? machine, CancellationToken token)
    {
        if (source == null) throw new InvalidOperationException("Postgres not configured");
        await using var command = source.CreateCommand(sql); command.CommandTimeout = 15;
        if (from != null)
        {
            command.Parameters.AddWithValue("from", from.Value); command.Parameters.AddWithValue("to", to!.Value);
            command.Parameters.AddWithValue("machine", NpgsqlTypes.NpgsqlDbType.Text, (object?)machine ?? DBNull.Value);
        }
        await using var reader = await command.ExecuteReaderAsync(token);
        var rows = new List<Dictionary<string, object?>>();
        while (await reader.ReadAsync(token))
        {
            var row = new Dictionary<string, object?>();
            for (var i = 0; i < reader.FieldCount; i++) row[reader.GetName(i)] = reader.IsDBNull(i) ? null : reader.GetValue(i);
            rows.Add(row);
        }
        Status = "connected"; return rows;
    }
    public async Task RefreshMaster(Catalog catalog, TelemetryStore store, CancellationToken token)
    {
        var rows = await Query("SELECT machine_id, machine_name, machine_type, line FROM machine ORDER BY machine_id LIMIT 1000", null, null, null, token);
        catalog.Replace(rows.Select(r => new MachineDefinition((string)r["machine_id"]!, (string)r["machine_name"]!, (string?)r["machine_type"] ?? "UNKNOWN", (string?)r["line"] ?? "UNKNOWN", Catalog.Fields)).ToArray());
        // Current source has the table but not the writer yet. Empty is legitimate.
        var latest = await Query("SELECT machine_id, status, temperature, pressure, speed, energy, event_time FROM machine_status_current WHERE event_time IS NOT NULL LIMIT 1000", null, null, null, token);
        foreach (var row in latest)
        {
            var payload = new Dictionary<string, object?>();
            foreach (var f in new[] { "status", "temperature", "pressure", "speed", "energy" }) payload[f] = row[f];
            var timestamp = new DateTimeOffset(DateTime.SpecifyKind((DateTime)row["event_time"]!, DateTimeKind.Utc));
            store.Apply(MockEvents.Create((string)row["machine_id"]!, payload, timestamp, source: "postgres-current"));
        }
    }
    public async Task<object> Analytics(DateOnly from, DateOnly to, string? machine, CancellationToken token)
    {
        var datasets = new Dictionary<string, object>();
        foreach (var table in new[] { "production_metric", "quality_metric", "data_quality_metric", "oee_metric" })
        {
            var filter = table == "data_quality_metric" ? "" : " AND (@machine IS NULL OR machine_id = @machine)";
            var rows = await Query($"SELECT * FROM {table} WHERE date BETWEEN @from AND @to{filter} ORDER BY date DESC LIMIT 1001", from, to, machine, token);
            datasets[table] = new { rows = rows.Take(1000), truncated = rows.Count > 1000, scope = table == "data_quality_metric" ? "pipeline-all-machines" : "selected-machines" };
        }
        var down = await Query("SELECT * FROM downtime_event WHERE start_time >= (@from::date::timestamp AT TIME ZONE 'UTC') AND start_time < ((@to::date + 1)::timestamp AT TIME ZONE 'UTC') AND (@machine IS NULL OR machine_id = @machine) ORDER BY start_time DESC LIMIT 1001", from, to, machine, token);
        datasets["downtime_event"] = new { rows = down.Take(1000), truncated = down.Count > 1000 };
        var metrics = await Query("SELECT * FROM machine_metric_1m WHERE window_start >= (@from::date::timestamp AT TIME ZONE 'UTC') AND window_start < ((@to::date + 1)::timestamp AT TIME ZONE 'UTC') AND (@machine IS NULL OR machine_id = @machine) ORDER BY window_start DESC LIMIT 1001", from, to, machine, token);
        datasets["machine_metric_1m"] = new { rows = metrics.Take(1000), truncated = metrics.Count > 1000 };
        return new { source = "postgres", from, to, machineId = machine, datasets, notes = new[] { "No metric is fabricated; empty rows are displayed as no data.", "data_quality_metric covers all machines; no machine_id in upstream table." } };
    }
    public async ValueTask DisposeAsync() { if (source != null) await source.DisposeAsync(); }
}

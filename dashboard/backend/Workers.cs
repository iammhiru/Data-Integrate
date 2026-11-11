using System.Text.Json;
using Confluent.Kafka;
using Microsoft.AspNetCore.SignalR;
namespace Factory.Api;

public static class MockEvents
{
    public static string Metric(string machine, string type, object values, DateTimeOffset time)
    {
        var seconds = type == "machine.status.5s" ? 5 : 60;
        var start = DateTimeOffset.FromUnixTimeSeconds(time.ToUnixTimeSeconds() / seconds * seconds);
        var fields = new Dictionary<string, object?> { ["machineId"] = machine, ["metricType"] = type, ["lastEventTime"] = time, ["emittedAt"] = time, ["maxIngestedAt"] = time, ["windowStart"] = start, ["windowEnd"] = start.AddSeconds(seconds), ["latencyMs"] = 0 };
        foreach (var p in JsonSerializer.SerializeToElement(values).EnumerateObject()) fields[p.Name] = p.Value.Clone();
        return JsonSerializer.Serialize(fields);
    }
    public static string Create(string machine, object payload, DateTimeOffset time, string? id = null, string source = "kepware-opcua") => JsonSerializer.Serialize(new
    {
        eventId = id ?? Guid.NewGuid().ToString(), eventType = "machine.telemetry", source, machineId = machine,
        timestamp = time.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ"),
        ingestedAt = DateTimeOffset.UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ"), schemaVersion = 1, payload
    });
}
public class TelemetryHub : Hub { }
public sealed class TelemetryWorker(TelemetryStore store, Catalog catalog, IConfiguration config, ILogger<TelemetryWorker> log) : BackgroundService
{
    protected override Task ExecuteAsync(CancellationToken token) => store.Mode == "Mock" ? RunMock(token) : Task.Run(() => RunKafka(token), token);
    private async Task RunMock(CancellationToken token)
    {
        store.SetSource("mock-running"); var tick = 0;
        try
        {
            while (!token.IsCancellationRequested)
            {
                var time = DateTimeOffset.UtcNow;
                foreach (var (m, i) in catalog.Machines.Select((m, i) => (m, i)))
                {
                    var status = (tick / 12 + i) % 13 == 0 ? "STOPPED" : i % 7 == 0 ? "IDLE" : "RUNNING";
                    var payload = new { temperature = tick % 20 == 17 && i == 0 ? (double?)null : Math.Round((status == "RUNNING" ? 72 : 40) + Math.Sin(tick / 5.0 + i) * 3, 2), pressure = 5.5, speed = status == "RUNNING" ? 1450 + i : 0, energy = 1.2, vibration = 2.1, status, operatingMode = "AUTO" };
                    if (store.InputFormat == "Telemetry") store.Apply(MockEvents.Create(m.MachineId, payload, time), m.MachineId);
                    else
                    {
                        store.ApplyMetric(MockEvents.Metric(m.MachineId, "machine.status.5s", new { status, avgTemperature = payload.temperature, avgPressure = payload.pressure, avgSpeed = payload.speed, sumEnergy = payload.energy }, time), m.MachineId);
                        store.ApplyMetric(MockEvents.Metric(m.MachineId, "machine.metric.1m", new { avgTemperature = payload.temperature, maxTemperature = payload.temperature, avgPressure = payload.pressure, avgSpeed = payload.speed, sumEnergy = 30.0, sampleCount = 30, missingCount = 0 }, time), m.MachineId);
                        store.ApplyMetric(MockEvents.Metric(m.MachineId, "production.rate.1m", new { productionRate = 120, totalQty = 120, goodQty = 118, rejectQty = 2 }, time), m.MachineId);
                    }
                }
                tick++; await Task.Delay(1500, token);
            }
        }
        catch (OperationCanceledException) when (token.IsCancellationRequested) { }
    }
    private void RunKafka(CancellationToken token)
    {
        var settings = new ConsumerConfig
        {
            BootstrapServers = config["Kafka:BootstrapServers"], GroupId = config["Kafka:GroupId"],
            AutoOffsetReset = Enum.Parse<AutoOffsetReset>(config["Kafka:AutoOffsetReset"] ?? "Earliest", true),
            EnableAutoCommit = true, EnableAutoOffsetStore = false, AllowAutoCreateTopics = false,
            SecurityProtocol = Enum.Parse<SecurityProtocol>(config["Kafka:SecurityProtocol"] ?? "Plaintext", true)
        };
        if (config["Kafka:SaslUsername"] is { Length: > 0 } user)
        {
            settings.SaslUsername = user; settings.SaslPassword = config["Kafka:SaslPassword"];
            settings.SaslMechanism = Enum.Parse<SaslMechanism>(config["Kafka:SaslMechanism"] ?? "Plain", true);
        }
        if (config["Kafka:SslCaLocation"] is { Length: > 0 } ca) settings.SslCaLocation = ca;
        using var consumer = new ConsumerBuilder<string, string>(settings)
            .SetErrorHandler((_, e) => store.SetSource("error", e.Reason))
            .SetPartitionsAssignedHandler((_, _) => store.SetSource("subscribed")).Build();
        consumer.Subscribe(store.Topic); store.SetSource("connecting");
        try
        {
            while (!token.IsCancellationRequested)
            {
                try
                {
                    var record = consumer.Consume(TimeSpan.FromMilliseconds(250));
                    if (record == null) continue;
                    store.SetSource("receiving");
                    if (store.InputFormat == "Metrics") store.ApplyMetric(record.Message.Value, record.Message.Key);
                    else store.Apply(record.Message.Value, record.Message.Key);
                    consumer.StoreOffset(record); // Live view only; not a durable sink or exactly-once delivery.
                }
                catch (ConsumeException ex) { store.SetSource("error", ex.Error.Reason); log.LogWarning("Kafka: {Reason}", ex.Error.Reason); token.WaitHandle.WaitOne(1000); }
            }
        }
        finally { consumer.Close(); store.SetSource("stopped"); }
    }
}
public sealed class BroadcastWorker(TelemetryStore store, IHubContext<TelemetryHub> hub, IConfiguration config) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken token)
    {
        using var timer = new PeriodicTimer(TimeSpan.FromMilliseconds(Math.Clamp(config.GetValue("Telemetry:BroadcastMilliseconds", 1000), 250, 5000)));
        try { while (await timer.WaitForNextTickAsync(token)) await hub.Clients.All.SendAsync("Snapshot", store.Snapshot(), token); }
        catch (OperationCanceledException) when (token.IsCancellationRequested) { }
    }
}
public sealed class MasterWorker(PostgresService db, Catalog catalog, TelemetryStore store) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken token)
    {
        if (!db.Configured || store.Mode == "Mock") return;
        while (!token.IsCancellationRequested)
        {
            try { await db.RefreshMaster(catalog, store, token); }
            catch (Exception ex) when (ex is not OperationCanceledException) { db.MarkError(); }
            try { await Task.Delay(TimeSpan.FromSeconds(30), token); } catch (OperationCanceledException) { break; }
        }
    }
}

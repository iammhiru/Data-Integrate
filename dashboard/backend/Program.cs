using Factory.Api;
if (args.Contains("--healthcheck"))
{
    try { using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(4) }; using var r = await client.GetAsync("http://127.0.0.1:8080/health"); Environment.Exit(r.IsSuccessStatusCode ? 0 : 1); }
    catch { Environment.Exit(1); }
    return;
}
var builder = WebApplication.CreateBuilder(args);
builder.Configuration.AddJsonFile("appsettings.Local.json", optional: true).AddEnvironmentVariables();
var mode = builder.Configuration["Telemetry:Mode"] ?? "Mock";
if (mode is not ("Mock" or "Kafka")) throw new InvalidOperationException("Telemetry:Mode must be Mock or Kafka");
if ((builder.Configuration["Kafka:Format"] ?? "Metrics") is not ("Metrics" or "Telemetry")) throw new InvalidOperationException("Kafka:Format must be Metrics or Telemetry");
builder.Services.AddSingleton<Catalog>(); builder.Services.AddSingleton<TelemetryStore>(); builder.Services.AddSingleton<PostgresService>();
builder.Services.AddSignalR(); builder.Services.AddHostedService<MasterWorker>(); builder.Services.AddHostedService<TelemetryWorker>(); builder.Services.AddHostedService<BroadcastWorker>();
var app = builder.Build(); app.UseDefaultFiles(); app.UseStaticFiles();
app.MapGet("/health", (TelemetryStore s, PostgresService db) => Results.Ok(new { status = "ok", mode, source = s.SourceStatus, postgres = db.Status }));
app.MapGet("/api/catalog", (Catalog c) => c.Machines);
app.MapGet("/api/snapshot", (TelemetryStore s) => s.Snapshot());
app.MapGet("/api/diagnostics", (TelemetryStore s, PostgresService db) => new { telemetry = s.Diagnostics(), postgres = db.Status });
app.MapGet("/api/machines/{machine}/series", (string machine, string tagCode, Catalog c, TelemetryStore s) => !c.HasTag(machine, tagCode) ? Results.NotFound() : Results.Ok(new { scope = "session", points = s.Series(machine, tagCode) }));
app.MapGet("/api/analytics", async (string? from, string? to, string? machineId, PostgresService db, CancellationToken token) =>
{
    if (!DateOnly.TryParseExact(from, "yyyy-MM-dd", out var start) || !DateOnly.TryParseExact(to, "yyyy-MM-dd", out var end) || end < start || end.DayNumber - start.DayNumber > 30 || machineId?.Length > 64)
        return Results.BadRequest(new { message = "Dùng from/to dạng yyyy-MM-dd, khoảng tối đa 31 ngày và machineId tối đa 64 ký tự." });
    if (!db.Configured) return Results.Json(new { message = "Chưa cấu hình PostgreSQL; dữ liệu phân tích không được giả lập." }, statusCode: 503);
    try { return Results.Ok(await db.Analytics(start, end, string.IsNullOrWhiteSpace(machineId) ? null : machineId, token)); }
    catch (Exception ex) when (ex is Npgsql.NpgsqlException or TimeoutException) { db.MarkError(); return Results.Json(new { message = "Không truy vấn được PostgreSQL. Kiểm tra kết nối và schema của repo." }, statusCode: 503); }
});
app.MapHub<TelemetryHub>("/hubs/telemetry");
app.Map("/api/{**path}", () => Results.NotFound());
app.MapFallbackToFile("index.html"); app.Run();

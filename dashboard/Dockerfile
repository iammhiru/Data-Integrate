# syntax=docker/dockerfile:1
FROM node:24-bookworm-slim AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# live = UI doc state-api qua WebSocket; mock = simulator trong trinh duyet.
# Van co the ghi de luc chay bang ?source=mock | ?source=live.
ARG VITE_DATA_SOURCE=mock
ENV VITE_DATA_SOURCE=${VITE_DATA_SOURCE}
RUN npm run build

FROM mcr.microsoft.com/dotnet/sdk:10.0 AS backend
WORKDIR /src
COPY backend/Factory.Api.csproj backend/
RUN dotnet restore backend/Factory.Api.csproj
COPY backend/ backend/
RUN dotnet publish backend/Factory.Api.csproj -c Release -o /out --no-restore /p:UseAppHost=false
COPY --from=frontend /src/frontend/dist /out/wwwroot

FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS runtime
WORKDIR /app
# Npgsql probes GSSAPI during PostgreSQL negotiation even with password auth.
RUN apt-get update && apt-get install -y --no-install-recommends libgssapi-krb5-2 && rm -rf /var/lib/apt/lists/*
COPY --from=backend --chown=app:app /out/ ./
# Urls in appsettings.json otherwise binds localhost inside the container.
ENV Urls=http://0.0.0.0:8080 \
    ASPNETCORE_HTTP_PORTS="" \
    Telemetry__Mode=Mock \
    DOTNET_EnableDiagnostics=0
USER app
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=6s --start-period=20s --retries=3 CMD ["dotnet", "Factory.Api.dll", "--healthcheck"]
ENTRYPOINT ["dotnet", "Factory.Api.dll"]

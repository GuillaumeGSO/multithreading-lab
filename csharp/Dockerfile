# Build stage — the repo layout is mirrored (/build/openapi.yaml + /build/csharp)
# so Api.csproj's ../../openapi.yaml resolves to the API contract.
FROM mcr.microsoft.com/dotnet/sdk:10.0-alpine AS build
WORKDIR /build/csharp

# Restore layer — cached until any csproj changes
COPY csharp/WordSearch.sln .
COPY csharp/Api/Api.csproj Api/
COPY csharp/Bench/Bench.csproj Bench/
COPY csharp/Tests/Tests.csproj Tests/
RUN dotnet restore

# Build and publish (the Api build generates its contracts from openapi.yaml)
COPY openapi.yaml /build/openapi.yaml
COPY csharp/Api/ Api/
COPY csharp/Bench/ Bench/
RUN dotnet publish Api/Api.csproj -c Release -o /out/api
RUN dotnet publish Bench/Bench.csproj -c Release -o /out/bench

FROM mcr.microsoft.com/dotnet/aspnet:10.0-alpine
# Accent stripping relies on Unicode normalization (FormD), which needs ICU:
# the alpine runtime image ships in globalization-invariant mode without it.
RUN apk add --no-cache icu-libs
ENV DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=false
WORKDIR /app

COPY --from=build /out/api ./
COPY --from=build /out/bench/Bench.dll ./Bench.dll
COPY --from=build /out/bench/Bench.runtimeconfig.json ./Bench.runtimeconfig.json
COPY assets/ /app/assets/
COPY benchmarks/cases.json /app/cases.json
COPY openapi.yaml /app/openapi.yaml

ENV ASSETS_ROOT=/app/assets
ENV OPENAPI_PATH=/app/openapi.yaml
ENV PORT=8005
EXPOSE 8005

ENTRYPOINT ["dotnet", "/app/Api.dll"]

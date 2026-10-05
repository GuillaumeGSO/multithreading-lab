FROM mcr.microsoft.com/dotnet/sdk:9.0-alpine AS build
WORKDIR /build

# Restore layer — cached until any csproj changes
COPY csharp/WordSearch.sln .
COPY csharp/Api/Api.csproj Api/
COPY csharp/Bench/Bench.csproj Bench/
COPY csharp/Tests/Tests.csproj Tests/
RUN dotnet restore

# Build and publish
COPY csharp/Api/ Api/
COPY csharp/Bench/ Bench/
RUN dotnet publish Api/Api.csproj -c Release -o /out/api
RUN dotnet publish Bench/Bench.csproj -c Release -o /out/bench

FROM mcr.microsoft.com/dotnet/aspnet:9.0-alpine
WORKDIR /app

COPY --from=build /out/api ./
COPY --from=build /out/bench/Bench.dll ./Bench.dll
COPY --from=build /out/bench/Bench.runtimeconfig.json ./Bench.runtimeconfig.json
COPY assets/ /app/assets/
COPY benchmarks/cases.json /app/cases.json

ENV ASSETS_ROOT=/app/assets
ENV PORT=8005
EXPOSE 8005

ENTRYPOINT ["dotnet", "/app/Api.dll"]

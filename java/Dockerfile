# Build stage — the repo layout is mirrored (/build/openapi.yaml + /build/java)
# so the pom's ../openapi.yaml resolves to the API contract.
FROM maven:3.9-eclipse-temurin-26 AS build
WORKDIR /build/java
COPY java/pom.xml .
RUN mvn dependency:go-offline -q
COPY openapi.yaml /build/openapi.yaml
COPY java/src/ src/
RUN mvn package -DskipTests -q

# Run stage
FROM eclipse-temurin:25-jre-alpine
WORKDIR /app
COPY --from=build /build/java/target/search-*.jar app.jar
COPY assets/ /app/assets/
COPY benchmarks/cases.json /app/cases.json
ENV ASSETS_ROOT=/app/assets
# Run as an unprivileged user; the app only reads its files.
RUN adduser -D -H app
USER app
EXPOSE 8002
# -XX:+UseCompactObjectHeaders: product flag in JDK 25 (JEP 519); shrinks object
# headers to 8 bytes, lowering heap footprint on the word-list workload.
ENTRYPOINT ["java", "-XX:+UseCompactObjectHeaders", "-jar", "/app/app.jar"]

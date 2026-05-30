# Build stage
FROM maven:3.9-eclipse-temurin-25 AS build
WORKDIR /build
COPY java/pom.xml .
RUN mvn dependency:go-offline -q
COPY java/src/ src/
RUN mvn package -DskipTests -q

# Run stage
FROM eclipse-temurin:25-jre-alpine
WORKDIR /app
COPY --from=build /build/target/search-*.jar app.jar
COPY assets/ /app/assets/
COPY benchmarks/cases.json /app/cases.json
ENV ASSETS_ROOT=/app/assets
EXPOSE 8002
# -XX:+UseCompactObjectHeaders: product flag in JDK 25 (JEP 519); shrinks object
# headers to 8 bytes, lowering heap footprint on the word-list workload.
ENTRYPOINT ["java", "-XX:+UseCompactObjectHeaders", "-jar", "/app/app.jar"]

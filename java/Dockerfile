# Build stage
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /build
COPY java/pom.xml .
RUN mvn dependency:go-offline -q
COPY java/src/ src/
RUN mvn package -DskipTests -q

# Run stage
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
COPY --from=build /build/target/search-*.jar app.jar
COPY assets/ /app/assets/
ENV ASSETS_ROOT=/app/assets
EXPOSE 8002
ENTRYPOINT ["java", "-jar", "/app/app.jar"]

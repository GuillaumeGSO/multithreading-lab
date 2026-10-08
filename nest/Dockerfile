# Build stage — install all deps, generate the API types from openapi.yaml and
# compile TypeScript to dist/. The repo layout is mirrored (/build/openapi.yaml
# + /build/nest) so the generate script's ../openapi.yaml resolves.
FROM node:22-alpine AS build
WORKDIR /build/nest
COPY nest/package.json nest/package-lock.json ./
RUN npm ci
COPY openapi.yaml /build/openapi.yaml
COPY nest/tsconfig.json nest/tsconfig.build.json nest/nest-cli.json ./
COPY nest/src ./src
RUN npm run build

# Runtime stage — production deps only, compiled output, shared word lists.
FROM node:22-alpine
WORKDIR /app
COPY nest/package.json nest/package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY --from=build /build/nest/dist ./dist
COPY assets/ /app/assets/
COPY benchmarks/cases.json /app/cases.json
COPY openapi.yaml /app/openapi.yaml
ENV ASSETS_ROOT=/app/assets
ENV OPENAPI_PATH=/app/openapi.yaml
ENV PORT=8006
# Run as the image's unprivileged user; the app only reads its files.
USER node
EXPOSE 8006
CMD ["node", "dist/main.js"]

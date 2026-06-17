# Build stage — install all deps and compile TypeScript to dist/.
FROM node:22-alpine AS build
WORKDIR /build
COPY nest/package.json nest/package-lock.json* ./
RUN npm install
COPY nest/tsconfig.json nest/tsconfig.build.json nest/nest-cli.json ./
COPY nest/src ./src
RUN npm run build

# Runtime stage — production deps only, compiled output, shared word lists.
FROM node:22-alpine
WORKDIR /app
COPY nest/package.json nest/package-lock.json* ./
RUN npm install --omit=dev && npm cache clean --force
COPY --from=build /build/dist ./dist
COPY assets/ /app/assets/
COPY benchmarks/cases.json /app/cases.json
ENV ASSETS_ROOT=/app/assets
ENV PORT=8006
EXPOSE 8006
CMD ["node", "dist/main.js"]

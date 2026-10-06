// HTTP entry point. Boots NestJS on the Fastify adapter and binds 0.0.0.0 so
// the container is reachable. The worker pool is created with the SearchModule
// providers and torn down via shutdown hooks.
import { readFileSync } from 'fs';
import { join } from 'path';
import { NestFactory } from '@nestjs/core';
import {
  FastifyAdapter,
  NestFastifyApplication,
} from '@nestjs/platform-fastify';
import { OpenAPIObject, SwaggerModule } from '@nestjs/swagger';
import { load } from 'js-yaml';
import { AppModule } from './app.module';
import { AllExceptionsFilter } from './common/error.filter';

// loadSpec reads the API contract — the repository's openapi.yaml — from
// OPENAPI_PATH (default: openapi.yaml at the repository root, relative to dist/).
function loadSpec(): OpenAPIObject {
  const path =
    process.env.OPENAPI_PATH || join(__dirname, '..', '..', 'openapi.yaml');
  return load(readFileSync(path, 'utf-8')) as OpenAPIObject;
}

async function bootstrap(): Promise<void> {
  const app = await NestFactory.create<NestFastifyApplication>(
    AppModule,
    new FastifyAdapter(),
    { logger: ['error', 'warn'] },
  );

  // The spec is served verbatim (never generated from decorators): Swagger UI
  // at /docs, the document at /openapi.json and /openapi.yaml.
  SwaggerModule.setup('docs', app, loadSpec(), {
    jsonDocumentUrl: '/openapi.json',
    yamlDocumentUrl: '/openapi.yaml',
  });

  app.useGlobalFilters(new AllExceptionsFilter());
  // Triggers WorkerPool.onApplicationShutdown on SIGTERM (docker stop).
  app.enableShutdownHooks();

  const port = parseInt(process.env.PORT || '8006', 10);
  await app.listen(port, '0.0.0.0');
}

void bootstrap();

// createApp builds the fully configured application (Fastify adapter, body
// limit, served OpenAPI spec, error filter) without listening, so the entry
// point and the HTTP tests share exactly the same setup.
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

// 64 KiB is far above any valid request (≤ 32 letters, ≤ 31 hints).
const BODY_LIMIT_BYTES = 64 * 1024;

// loadSpec reads the API contract — the repository's openapi.yaml — from
// OPENAPI_PATH (default: openapi.yaml at the repository root, relative to dist/).
function loadSpec(): OpenAPIObject {
  const path =
    process.env.OPENAPI_PATH || join(__dirname, '..', '..', 'openapi.yaml');
  return load(readFileSync(path, 'utf-8')) as OpenAPIObject;
}

export async function createApp(): Promise<NestFastifyApplication> {
  const app = await NestFactory.create<NestFastifyApplication>(
    AppModule,
    new FastifyAdapter({ bodyLimit: BODY_LIMIT_BYTES }),
    { logger: ['error', 'warn'] },
  );

  // The spec is served verbatim (never generated from decorators): Swagger UI
  // at /docs, the document at /openapi.json and /openapi.yaml.
  SwaggerModule.setup('docs', app, loadSpec(), {
    jsonDocumentUrl: '/openapi.json',
    yamlDocumentUrl: '/openapi.yaml',
  });

  app.useGlobalFilters(new AllExceptionsFilter());
  return app;
}

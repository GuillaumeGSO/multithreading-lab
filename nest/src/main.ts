// HTTP entry point. Boots NestJS on the Fastify adapter and binds 0.0.0.0 so
// the container is reachable. The worker pool is created with the SearchModule
// providers and torn down via shutdown hooks.
import { NestFactory } from '@nestjs/core';
import {
  FastifyAdapter,
  NestFastifyApplication,
} from '@nestjs/platform-fastify';
import { AppModule } from './app.module';
import { AllExceptionsFilter } from './common/error.filter';

async function bootstrap(): Promise<void> {
  const app = await NestFactory.create<NestFastifyApplication>(
    AppModule,
    new FastifyAdapter(),
    { logger: ['error', 'warn'] },
  );
  app.useGlobalFilters(new AllExceptionsFilter());
  // Triggers WorkerPool.onApplicationShutdown on SIGTERM (docker stop).
  app.enableShutdownHooks();

  const port = parseInt(process.env.PORT || '8006', 10);
  await app.listen(port, '0.0.0.0');
}

void bootstrap();

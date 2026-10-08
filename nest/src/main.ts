// HTTP entry point. Boots the application (see app.ts) and binds 0.0.0.0 so
// the container is reachable. The worker pool is created with the SearchModule
// providers and torn down via shutdown hooks.
import { createApp } from './app';

async function bootstrap(): Promise<void> {
  const app = await createApp();
  // Triggers WorkerPool.onApplicationShutdown on SIGTERM (docker stop).
  app.enableShutdownHooks();

  const port = parseInt(process.env.PORT || '8006', 10);
  await app.listen(port, '0.0.0.0');
}

void bootstrap();

import { Controller, Get } from '@nestjs/common';

@Controller()
export class HealthController {
  // GET /health — liveness check.
  @Get('health')
  health(): { status: string } {
    return { status: 'ok' };
  }
}

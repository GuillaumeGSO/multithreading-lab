import { Controller, Get } from '@nestjs/common';
import { HealthResponse } from '../search/search.types';

@Controller()
export class HealthController {
  @Get('health')
  health(): HealthResponse {
    return { status: 'ok' };
  }
}

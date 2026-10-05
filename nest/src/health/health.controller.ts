import { Controller, Get } from '@nestjs/common';
import { ApiOperation, ApiTags } from '@nestjs/swagger';

@ApiTags('health')
@Controller()
export class HealthController {
  @ApiOperation({ summary: 'Liveness check' })
  @Get('health')
  health(): { status: string } {
    return { status: 'ok' };
  }
}

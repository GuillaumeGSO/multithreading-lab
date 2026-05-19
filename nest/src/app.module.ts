import { Module } from '@nestjs/common';
import { HealthModule } from './health/health.module';
import { SearchModule } from './search/search.module';

@Module({
  imports: [HealthModule, SearchModule],
})
export class AppModule {}

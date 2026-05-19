import { Module } from '@nestjs/common';
import { SearchController } from './search.controller';
import { SearchService } from './search.service';
import { WorkerPool } from './worker-pool';

@Module({
  controllers: [SearchController],
  providers: [SearchService, WorkerPool],
})
export class SearchModule {}

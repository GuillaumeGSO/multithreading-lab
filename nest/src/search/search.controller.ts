import { Body, Controller, HttpCode, Post } from '@nestjs/common';
import { SearchService } from './search.service';
import {
  SearchFileRequest,
  SearchManyRequest,
  SearchResponse,
} from './search.types';

// Routes and bodies follow the searchFile / searchMany operations of
// openapi.yaml; the types are generated from it. Both answer 200 (as the
// contract specifies) rather than Nest's POST default of 201.
@Controller()
export class SearchController {
  constructor(private readonly service: SearchService) {}

  @Post('search/file')
  @HttpCode(200)
  searchFile(@Body() req: SearchFileRequest): Promise<SearchResponse> {
    return this.service.searchFile(req);
  }

  @Post('search/many')
  @HttpCode(200)
  searchMany(@Body() req: SearchManyRequest): Promise<SearchResponse> {
    return this.service.searchMany(req);
  }
}

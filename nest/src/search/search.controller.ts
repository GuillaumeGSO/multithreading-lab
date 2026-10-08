import { Body, Controller, HttpCode, Post } from '@nestjs/common';
import { SearchService } from './search.service';
import { validateFileRequest, validateManyRequest } from './search.validation';
import { SearchResponse } from './search.types';

// Routes and bodies follow the searchFile / searchMany operations of
// openapi.yaml; the types are generated from it. Bodies are untrusted JSON, so
// each is validated against the contract's bounds before reaching the service.
// Both answer 200 (as the contract specifies) rather than Nest's POST default
// of 201.
@Controller()
export class SearchController {
  constructor(private readonly service: SearchService) {}

  @Post('search/file')
  @HttpCode(200)
  searchFile(@Body() body: unknown): Promise<SearchResponse> {
    return this.service.searchFile(validateFileRequest(body));
  }

  @Post('search/many')
  @HttpCode(200)
  searchMany(@Body() body: unknown): Promise<SearchResponse> {
    return this.service.searchMany(validateManyRequest(body));
  }
}

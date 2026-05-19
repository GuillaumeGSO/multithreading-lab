import { Body, Controller, Post } from '@nestjs/common';
import { SearchService } from './search.service';
import { SearchFileDto, SearchManyDto, SearchResponse } from './dto/search.dto';

@Controller()
export class SearchController {
  constructor(private readonly service: SearchService) {}

  // POST /search/file — words of a fixed length.
  @Post('search/file')
  searchFile(@Body() dto: SearchFileDto): Promise<SearchResponse> {
    return this.service.searchFile(dto);
  }

  // POST /search/many — words across every length up to len(cars).
  @Post('search/many')
  searchMany(@Body() dto: SearchManyDto): Promise<SearchResponse> {
    return this.service.searchMany(dto);
  }
}

import { Body, Controller, Post } from '@nestjs/common';
import { ApiOperation, ApiResponse, ApiTags } from '@nestjs/swagger';
import { SearchService } from './search.service';
import { SearchFileDto, SearchManyDto, SearchResponse } from './dto/search.dto';

@ApiTags('search')
@Controller()
export class SearchController {
  constructor(private readonly service: SearchService) {}

  @ApiOperation({ summary: 'Search words of a fixed length', description: 'Returns words of exactly nb_car characters that can be formed from the available letter pool and satisfy every positional hint.' })
  @ApiResponse({ status: 200, type: SearchResponse })
  @Post('search/file')
  searchFile(@Body() dto: SearchFileDto): Promise<SearchResponse> {
    return this.service.searchFile(dto);
  }

  @ApiOperation({ summary: 'Search words across all lengths', description: 'Returns words for every length from 1 up to len(cars), ordered longest-first.' })
  @ApiResponse({ status: 200, type: SearchResponse })
  @Post('search/many')
  searchMany(@Body() dto: SearchManyDto): Promise<SearchResponse> {
    return this.service.searchMany(dto);
  }
}

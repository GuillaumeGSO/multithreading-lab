// Request/response shapes for the search endpoints. Plain classes rather than
// interfaces so that @nestjs/swagger can read the metadata at runtime via
// reflect-metadata. No class-validator decorators — validation is intentionally
// minimal, mirroring the Go reference: the algorithm signals bad input.
import { ApiProperty } from '@nestjs/swagger';
import { Hint } from '../search';

export class HintDto implements Hint {
  @ApiProperty({ description: '1-indexed position of the constraint', example: 3 })
  pos!: number;

  @ApiProperty({
    description: 'Expected character at pos; null means no character constraint',
    example: 'e',
    nullable: true,
  })
  car: string | null = null;

  @ApiProperty({ description: 'When true, the character must NOT appear at pos', default: false })
  inverted: boolean = false;
}

export class SearchFileDto {
  @ApiProperty({ description: 'Language code — dictionary subfolder under assets/', default: 'fr', example: 'fr' })
  lang?: string;

  @ApiProperty({ description: 'Exact word length to search for', example: 5 })
  nb_car?: number;

  @ApiProperty({ description: 'Available letters; empty means no letter-pool constraint', type: [String], default: [] })
  lst_car?: string[];

  @ApiProperty({ description: 'Positional constraints applied after the letter-pool filter', type: [HintDto], default: [] })
  lst_hint?: HintDto[];

  @ApiProperty({ description: 'Each letter may only be used once (Scrabble-style)', default: false })
  strict?: boolean;
}

export class SearchManyDto {
  @ApiProperty({ description: 'Language code — dictionary subfolder under assets/', default: 'fr', example: 'fr' })
  lang?: string;

  @ApiProperty({ description: 'Available letters as a string; max word length equals len(cars)', example: 'artes' })
  cars?: string;

  @ApiProperty({ description: 'Positional constraints applied across every length scanned', type: [HintDto], default: [] })
  lst_hint?: HintDto[];
}

export class SearchResponse {
  @ApiProperty({ description: 'Matching words in scan order (longest-first for /search/many)', type: [String] })
  words!: string[];

  @ApiProperty({ description: 'Total number of matching words' })
  count!: number;
}

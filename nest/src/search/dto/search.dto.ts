// Request/response shapes for the search endpoints. These are plain interfaces
// used only for typing — validation is intentionally minimal, mirroring the Go
// reference: decode the body and let the algorithm signal bad input.
import { Hint } from '../search';

export interface SearchFileDto {
  lang?: string;
  nb_car?: number;
  lst_car?: string[];
  lst_hint?: Hint[];
  strict?: boolean;
}

export interface SearchManyDto {
  lang?: string;
  cars?: string;
  lst_hint?: Hint[];
}

export interface SearchResponse {
  words: string[];
  count: number;
}

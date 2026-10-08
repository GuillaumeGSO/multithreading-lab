// Runtime validation of request bodies against the bounds in openapi.yaml.
// The generated types (src/generated/api.d.ts) are compile-time only, so the
// untrusted JSON body is checked here before it reaches the worker pool. Any
// violation becomes a BadRequestException, answered as a 400 ErrorResponse.
import { BadRequestException } from '@nestjs/common';
import { SearchFileRequest, SearchManyRequest } from './search.types';

const LANGS: readonly string[] = ['fr', 'en'];
const MIN_WORD_LENGTH = 1;
const MAX_WORD_LENGTH = 31;
const MAX_LETTERS = 32;
const MAX_HINTS = 31;
const MIN_POSITION = 1;
const MAX_POSITION = 31;

function fail(message: string): never {
  throw new BadRequestException(message);
}

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

function isIntIn(v: unknown, min: number, max: number): v is number {
  return Number.isInteger(v) && (v as number) >= min && (v as number) <= max;
}

function checkLang(lang: unknown): void {
  if (lang !== undefined && lang !== null && !LANGS.includes(lang as string)) {
    fail(`lang: must be one of ${LANGS.join(', ')}`);
  }
}

function checkOptionalBool(v: unknown, field: string): void {
  if (v !== undefined && v !== null && typeof v !== 'boolean') {
    fail(`${field}: must be a boolean`);
  }
}

function checkHints(hints: unknown): void {
  if (hints === undefined || hints === null) return;
  if (!Array.isArray(hints)) fail('hints: must be an array');
  if (hints.length > MAX_HINTS) fail(`hints: at most ${MAX_HINTS} items`);
  hints.forEach((h: unknown, i) => {
    if (!isObject(h)) fail(`hints[${i}]: must be an object`);
    if (!isIntIn(h.position, MIN_POSITION, MAX_POSITION)) {
      fail(`hints[${i}].position: must be an integer between ${MIN_POSITION} and ${MAX_POSITION}`);
    }
    if (h.letter !== undefined && h.letter !== null && typeof h.letter !== 'string') {
      fail(`hints[${i}].letter: must be a string`);
    }
    checkOptionalBool(h.excluded, `hints[${i}].excluded`);
  });
}

export function validateFileRequest(body: unknown): SearchFileRequest {
  if (!isObject(body)) fail('request body must be a JSON object');
  checkLang(body.lang);
  if (!isIntIn(body.wordLength, MIN_WORD_LENGTH, MAX_WORD_LENGTH)) {
    fail(`wordLength: must be an integer between ${MIN_WORD_LENGTH} and ${MAX_WORD_LENGTH}`);
  }
  const letters = body.letters;
  if (letters !== undefined && letters !== null) {
    if (!Array.isArray(letters) || !letters.every((c) => typeof c === 'string')) {
      fail('letters: must be an array of strings');
    }
    if (letters.length > MAX_LETTERS) fail(`letters: at most ${MAX_LETTERS} items`);
  }
  checkHints(body.hints);
  checkOptionalBool(body.strict, 'strict');
  return body as unknown as SearchFileRequest;
}

export function validateManyRequest(body: unknown): SearchManyRequest {
  if (!isObject(body)) fail('request body must be a JSON object');
  checkLang(body.lang);
  if (typeof body.letters !== 'string') fail('letters: required string');
  if ([...body.letters].length > MAX_LETTERS) {
    fail(`letters: at most ${MAX_LETTERS} characters`);
  }
  checkHints(body.hints);
  return body as unknown as SearchManyRequest;
}


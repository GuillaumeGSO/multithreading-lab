// HTTP-level tests: request validation at the API boundary. They run against
// the COMPILED app in dist/ (the worker pool needs plain JavaScript), so they
// belong to `npm run test:integration`. Every request outside the contract's
// bounds (openapi.yaml) must be a 400 ErrorResponse, never a 5xx.
import * as path from 'path';
import type { NestFastifyApplication } from '@nestjs/platform-fastify';

import { createApp } from '../dist/app';

const PIN = { position: 1, letter: 'a' };

const INVALID: Array<[string, unknown]> = [
  ['/search/file', { wordLength: 5, letters: ['a'], hints: [{ position: 0, letter: 'a' }] }],
  ['/search/many', { letters: 'abc', hints: [{ position: -1, letter: 'a' }] }],
  ['/search/file', { wordLength: 5, letters: ['a'], hints: [{ position: 32, letter: 'a' }] }],
  ['/search/file', { lang: '../../etc', wordLength: 5, letters: ['a'] }],
  ['/search/file', { lang: '/etc', wordLength: 5, letters: ['a'] }],
  ['/search/many', { lang: 'xx', letters: 'abc' }],
  ['/search/file', { wordLength: 0, letters: ['a'] }],
  ['/search/file', { wordLength: -1, letters: ['a'] }],
  ['/search/file', { wordLength: 32, letters: ['a'] }],
  ['/search/file', { letters: ['a'] }],
  ['/search/file', { wordLength: 5, letters: Array(33).fill('a') }],
  ['/search/file', { wordLength: 5, hints: Array(32).fill(PIN) }],
  ['/search/many', { letters: 'a'.repeat(33) }],
  ['/search/many', { hints: [PIN] }],
  ['/search/many', { letters: 123 }],
  ['/search/file', { wordLength: 5 }],
];

describe('HTTP API validation', () => {
  let app: NestFastifyApplication;

  beforeAll(async () => {
    // Set before the pool spawns workers so they inherit it via env.
    process.env.ASSETS_ROOT = path.resolve(__dirname, '../../assets');
    process.env.OPENAPI_PATH = path.resolve(__dirname, '../../openapi.yaml');
    app = await createApp();
    await app.init();
    await app.getHttpAdapter().getInstance().ready();
  });

  afterAll(async () => {
    await app.close();
  });

  const post = (url: string, payload: string) =>
    app.inject({ method: 'POST', url, payload, headers: { 'content-type': 'application/json' } });

  it.each(INVALID)('%s %j is a 400 ErrorResponse', async (url, body) => {
    const res = await post(url, JSON.stringify(body));
    expect(res.statusCode).toBe(400);
    expect(typeof res.json().error).toBe('string');
  });

  it.each(['/search/file', '/search/many'])('%s rejects malformed JSON with 400', async (url) => {
    const res = await post(url, '{not json');
    expect(res.statusCode).toBe(400);
    expect(typeof res.json().error).toBe('string');
  });

  it('rejects an oversized body with a 4xx ErrorResponse', async () => {
    const res = await post('/search/many', JSON.stringify({ letters: 'a'.repeat(70000) }));
    expect(res.statusCode).toBeGreaterThanOrEqual(400);
    expect(res.statusCode).toBeLessThan(500);
    expect(typeof res.json().error).toBe('string');
  });

  it('accepts valid requests at the bounds', async () => {
    const file = await post('/search/file', JSON.stringify({
      lang: 'fr', wordLength: 5, letters: ['e', 'l', 'i', 's', 'a'], hints: [{ position: 1, letter: 's' }],
    }));
    expect(file.statusCode).toBe(200);
    expect(file.json().count).toBe(file.json().words.length);
    const many = await post('/search/many', JSON.stringify({ lang: 'en', letters: 'a'.repeat(32) }));
    expect(many.statusCode).toBe(200);
  });
});

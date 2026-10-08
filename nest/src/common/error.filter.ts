// AllExceptionsFilter normalizes every failure into the contract's
// ErrorResponse: a `{"error": "..."}` body.
//   * HttpException (e.g. BadRequestException from request validation) keeps
//     its status and message.
//   * Fastify client errors (malformed JSON, oversized body) carry a 4xx
//     `statusCode` and keep it with their message.
//   * The algorithm's own rejection ("letters and hints cannot both be
//     empty", raised inside a worker) is a client error: 400.
//   * Anything else is an unexpected server fault: logged, and answered with
//     a generic 500 so internal details never reach the client.
import {
  ArgumentsHost,
  Catch,
  ExceptionFilter,
  HttpException,
  Logger,
} from '@nestjs/common';
import { FastifyReply } from 'fastify';
import { ErrorResponse } from '../search/search.types';

// Messages the search algorithm throws for requests it rejects.
const CLIENT_ERROR_MESSAGES = [
  'letters and hints cannot both be empty',
  'invalid lang: ',
];

@Catch()
export class AllExceptionsFilter implements ExceptionFilter {
  private readonly logger = new Logger(AllExceptionsFilter.name);

  catch(exception: unknown, host: ArgumentsHost): void {
    const reply = host.switchToHttp().getResponse<FastifyReply>();
    const [status, message] = this.describe(exception);
    const body: ErrorResponse = { error: message };
    void reply.status(status).send(body);
  }

  private describe(exception: unknown): [number, string] {
    if (exception instanceof HttpException) {
      const response = exception.getResponse();
      if (typeof response === 'string') {
        return [exception.getStatus(), response];
      }
      const body = response as { message?: string | string[] };
      const message = Array.isArray(body.message)
        ? body.message.join(', ')
        : body.message ?? exception.message;
      return [exception.getStatus(), message];
    }
    if (exception instanceof Error) {
      const statusCode = (exception as { statusCode?: unknown }).statusCode;
      if (typeof statusCode === 'number' && statusCode >= 400 && statusCode < 500) {
        return [statusCode, exception.message];
      }
      if (CLIENT_ERROR_MESSAGES.some((m) => exception.message.startsWith(m))) {
        return [400, exception.message];
      }
    }
    this.logger.error(exception instanceof Error ? exception.stack : String(exception));
    return [500, 'internal error'];
  }
}

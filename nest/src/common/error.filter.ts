// AllExceptionsFilter normalizes every failure into the contract's
// ErrorResponse: a `{"error": "..."}` body. This covers Fastify's JSON-parse
// errors, the algorithm's thrown Error ("letters and hints cannot both be
// empty"), and any HttpException.
import {
  ArgumentsHost,
  Catch,
  ExceptionFilter,
  HttpException,
} from '@nestjs/common';
import { FastifyReply } from 'fastify';
import { ErrorResponse } from '../search/search.types';

@Catch()
export class AllExceptionsFilter implements ExceptionFilter {
  catch(exception: unknown, host: ArgumentsHost): void {
    const reply = host.switchToHttp().getResponse<FastifyReply>();

    let status = 400;
    let message = 'internal error';

    if (exception instanceof HttpException) {
      status = exception.getStatus();
      const response = exception.getResponse();
      if (typeof response === 'string') {
        message = response;
      } else {
        const body = response as { message?: string | string[] };
        message = Array.isArray(body.message)
          ? body.message.join(', ')
          : body.message ?? exception.message;
      }
    } else if (exception instanceof Error) {
      message = exception.message;
    }

    const body: ErrorResponse = { error: message };
    void reply.status(status).send(body);
  }
}

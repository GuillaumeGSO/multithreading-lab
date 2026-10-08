package com.lab.search.config;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ReadListener;
import jakarta.servlet.ServletException;
import jakarta.servlet.ServletInputStream;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletRequestWrapper;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/// Rejects request bodies over 64 KiB with 413 and the contract's ErrorResponse.
/// 64 KiB is far above any valid request (≤ 32 letters, ≤ 31 hints). A declared
/// Content-Length is checked up front; a chunked body is counted while it is read.
@Component
public class BodySizeLimitFilter extends OncePerRequestFilter {

    static final int MAX_BODY_BYTES = 64 * 1024;
    private static final String TOO_LARGE = "{\"error\":\"request body is too large\"}";

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        if (request.getContentLengthLong() > MAX_BODY_BYTES) {
            reject(response);
            return;
        }
        try {
            chain.doFilter(new LimitedRequest(request), response);
        } catch (BodyTooLargeException e) {
            if (!response.isCommitted()) {
                response.reset();
                reject(response);
            }
        } catch (ServletException e) {
            if (e.getCause() instanceof BodyTooLargeException && !response.isCommitted()) {
                response.reset();
                reject(response);
            } else {
                throw e;
            }
        }
    }

    private static void reject(HttpServletResponse response) throws IOException {
        response.setStatus(HttpServletResponse.SC_REQUEST_ENTITY_TOO_LARGE);
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.getWriter().write(TOO_LARGE);
    }

    /// Thrown while reading a body past the limit. Spring may wrap it (e.g. in
    /// HttpMessageNotReadableException); handlers check the cause to answer 413.
    public static final class BodyTooLargeException extends IOException {
        BodyTooLargeException() {
            super("request body is too large");
        }
    }

    /// Wraps the request so reading past the limit throws BodyTooLargeException.
    private static final class LimitedRequest extends HttpServletRequestWrapper {
        private ServletInputStream limited;

        LimitedRequest(HttpServletRequest request) {
            super(request);
        }

        @Override
        public ServletInputStream getInputStream() throws IOException {
            if (limited == null) {
                limited = new LimitedInputStream(super.getInputStream());
            }
            return limited;
        }
    }

    private static final class LimitedInputStream extends ServletInputStream {
        private final ServletInputStream in;
        private long count;

        LimitedInputStream(ServletInputStream in) {
            this.in = in;
        }

        private int counted(int n) throws BodyTooLargeException {
            if (n > 0 && (count += n) > MAX_BODY_BYTES) throw new BodyTooLargeException();
            return n;
        }

        @Override
        public int read() throws IOException {
            int b = in.read();
            if (b >= 0) counted(1);
            return b;
        }

        @Override
        public int read(byte[] buf, int off, int len) throws IOException {
            return counted(in.read(buf, off, len));
        }

        @Override public boolean isFinished() { return in.isFinished(); }
        @Override public boolean isReady() { return in.isReady(); }
        @Override public void setReadListener(ReadListener listener) { in.setReadListener(listener); }
    }
}

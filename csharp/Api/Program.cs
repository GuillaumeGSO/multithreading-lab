using Microsoft.AspNetCore.Http.HttpResults;
using Scalar.AspNetCore;
using WordSearch.Api;
using WordSearch.Api.Contracts;
using WordSearch.Api.Search;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddSingleton<ParallelSearchService>();
// Surface unreadable request bodies as BadHttpRequestException in every
// environment so the middleware below can answer with ErrorResponse.
builder.Services.Configure<RouteHandlerOptions>(o => o.ThrowOnBadRequest = true);
builder.Services.AddSingleton(OpenApiSpec.Load());
// 64 KiB is far above any valid request (≤ 32 letters, ≤ 31 hints).
builder.WebHost.ConfigureKestrel(o => o.Limits.MaxRequestBodySize = 64 * 1024);

var app = builder.Build();

var port = Environment.GetEnvironmentVariable("PORT") ?? "8005";
app.Urls.Add($"http://0.0.0.0:{port}");

// Every failure is answered with the contract's ErrorResponse:
//   * malformed/unreadable JSON or an oversized body (BadHttpRequestException)
//     keeps its 4xx status (400, or 413 past the body limit);
//   * anything else is a server fault: logged, answered with a generic 500 so
//     internal details never reach the client.
app.Use(async (ctx, next) =>
{
    try
    {
        await next(ctx);
    }
    catch (BadHttpRequestException ex) when (!ctx.Response.HasStarted)
    {
        ctx.Response.StatusCode = ex.StatusCode;
        await ctx.Response.WriteAsJsonAsync(new ErrorResponse { Error = ex.Message });
    }
    catch (Exception ex) when (!ctx.Response.HasStarted)
    {
        app.Logger.LogError(ex, "unexpected error");
        ctx.Response.StatusCode = StatusCodes.Status500InternalServerError;
        await ctx.Response.WriteAsJsonAsync(new ErrorResponse { Error = "internal error" });
    }
});

// Error statuses produced without a body (e.g. Kestrel's 413 past the body
// limit, or 404) are given the contract's ErrorResponse shape.
app.UseStatusCodePages(async ctx =>
{
    var status = ctx.HttpContext.Response.StatusCode;
    var reason = Microsoft.AspNetCore.WebUtilities.ReasonPhrases.GetReasonPhrase(status);
    await ctx.HttpContext.Response.WriteAsJsonAsync(new ErrorResponse { Error = reason });
});

// The API contract (openapi.yaml) is served verbatim; nothing is generated from code.
app.MapGet("/openapi.yaml", (OpenApiSpec spec) => Results.Text(spec.Yaml, "application/yaml"));
app.MapGet("/openapi.json", (OpenApiSpec spec) => Results.Text(spec.Json, "application/json"));
app.MapGet("/docs", () => Results.Redirect("/docs/v1"));
app.MapScalarApiReference("/docs", options => options.WithOpenApiRoutePattern("/openapi.json"));

app.MapGet("/health", () => TypedResults.Ok(new HealthResponse { Status = "ok" }));

app.MapPost("/search/file", async Task<Results<Ok<SearchResponse>, BadRequest<ErrorResponse>>> (
    SearchFileRequest req, ParallelSearchService svc) =>
{
    if (RequestValidation.Validate(req) is { } invalid)
        return TypedResults.BadRequest(new ErrorResponse { Error = invalid });
    try
    {
        var words = await svc.SearchInFileAsync(
            LangCode(req.Lang), req.WordLength, req.Letters?.ToList(), ToHints(req.Hints), req.Strict ?? false);
        return TypedResults.Ok(new SearchResponse { Words = words.ToList(), Count = words.Count });
    }
    catch (ArgumentException ex)
    {
        return TypedResults.BadRequest(new ErrorResponse { Error = ex.Message });
    }
});

app.MapPost("/search/many", async Task<Results<Ok<SearchResponse>, BadRequest<ErrorResponse>>> (
    SearchManyRequest req, ParallelSearchService svc) =>
{
    if (RequestValidation.Validate(req) is { } invalid)
        return TypedResults.BadRequest(new ErrorResponse { Error = invalid });
    try
    {
        var words = await svc.SearchInManyAsync(LangCode(req.Lang), req.Letters ?? "", ToHints(req.Hints));
        return TypedResults.Ok(new SearchResponse { Words = words.ToList(), Count = words.Count });
    }
    catch (ArgumentException ex)
    {
        return TypedResults.BadRequest(new ErrorResponse { Error = ex.Message });
    }
});

app.Run();

// The wire value of the generated Lang enum ("fr" / "en"); absent means the spec's default.
static string LangCode(Lang? lang) => (lang ?? Lang.Fr).ToString().ToLowerInvariant();

// Maps the generated contract hints onto the search algorithm's Hint.
static IReadOnlyList<WordSearch.Api.Search.Hint> ToHints(ICollection<WordSearch.Api.Contracts.Hint>? hints) =>
    hints?.Select(h => new WordSearch.Api.Search.Hint(h.Position, h.Letter, h.Excluded ?? false)).ToList()
    ?? [];

// Exposes the entry point to WebApplicationFactory in the HTTP tests.
public partial class Program;

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

var app = builder.Build();

var port = Environment.GetEnvironmentVariable("PORT") ?? "8005";
app.Urls.Add($"http://0.0.0.0:{port}");

// Malformed or unreadable JSON bodies surface as BadHttpRequestException;
// answer them with the contract's ErrorResponse instead of an empty 400.
app.Use(async (ctx, next) =>
{
    try
    {
        await next(ctx);
    }
    catch (BadHttpRequestException ex) when (!ctx.Response.HasStarted)
    {
        ctx.Response.StatusCode = StatusCodes.Status400BadRequest;
        await ctx.Response.WriteAsJsonAsync(new ErrorResponse { Error = ex.Message });
    }
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
    try
    {
        var words = await svc.SearchInFileAsync(
            req.Lang ?? "fr", req.WordLength, req.Letters?.ToList(), ToHints(req.Hints), req.Strict ?? false);
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
    try
    {
        var words = await svc.SearchInManyAsync(req.Lang ?? "fr", req.Letters ?? "", ToHints(req.Hints));
        return TypedResults.Ok(new SearchResponse { Words = words.ToList(), Count = words.Count });
    }
    catch (ArgumentException ex)
    {
        return TypedResults.BadRequest(new ErrorResponse { Error = ex.Message });
    }
});

app.Run();

// Maps the generated contract hints onto the search algorithm's Hint.
static IReadOnlyList<WordSearch.Api.Search.Hint> ToHints(ICollection<WordSearch.Api.Contracts.Hint>? hints) =>
    hints?.Select(h => new WordSearch.Api.Search.Hint(h.Position, h.Letter, h.Excluded ?? false)).ToList()
    ?? [];

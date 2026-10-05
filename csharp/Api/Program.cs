using Scalar.AspNetCore;
using System.Text.Json;
using WordSearch.Api.Models;
using WordSearch.Api.Search;

var builder = WebApplication.CreateBuilder(args);

builder.Services.ConfigureHttpJsonOptions(opts =>
{
    opts.SerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower;
    opts.SerializerOptions.PropertyNameCaseInsensitive = true;
});

builder.Services.AddSingleton<ParallelSearchService>();
builder.Services.AddOpenApi(options =>
{
    options.AddDocumentTransformer((doc, _, _) =>
    {
        doc.Info.Title = "Word Search API";
        doc.Info.Description =
            "Filters words from dictionary files by available letters, positional hints, " +
            "and word length. C#/.NET 9 implementation — Task.WhenAll fan-out via ThreadPool.";
        doc.Info.Version = "1.0.0";
        return Task.CompletedTask;
    });
});

var app = builder.Build();

var port = Environment.GetEnvironmentVariable("PORT") ?? "8005";
app.Urls.Add($"http://0.0.0.0:{port}");

app.MapOpenApi();
app.MapScalarApiReference();

app.MapGet("/health", () => Results.Ok(new { status = "ok" }))
   .WithName("Health")
   .WithSummary("Liveness check");

app.MapPost("/search/file", async (SearchFileRequest req, ParallelSearchService svc) =>
{
    try
    {
        var words = await svc.SearchInFileAsync(
            req.Lang ?? "fr", req.NbCar, req.LstCar, req.LstHint, req.Strict);
        return Results.Ok(SearchResponse.Of(words));
    }
    catch (ArgumentException ex)
    {
        return Results.BadRequest(new { error = ex.Message });
    }
})
.WithName("SearchFile")
.WithSummary("Search words of a fixed length")
.WithDescription("Returns words of exactly NbCar characters that can be formed from the available letter pool and satisfy every positional hint.");

app.MapPost("/search/many", async (SearchManyRequest req, ParallelSearchService svc) =>
{
    try
    {
        var words = await svc.SearchInManyAsync(
            req.Lang ?? "fr", req.Cars ?? "", req.LstHint);
        return Results.Ok(SearchResponse.Of(words));
    }
    catch (ArgumentException ex)
    {
        return Results.BadRequest(new { error = ex.Message });
    }
})
.WithName("SearchMany")
.WithSummary("Search words across all lengths")
.WithDescription("Returns words for every length from 1 up to len(Cars), ordered longest-first.");

app.Run();

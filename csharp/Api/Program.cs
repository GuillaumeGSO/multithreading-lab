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

var app = builder.Build();

var port = Environment.GetEnvironmentVariable("PORT") ?? "8005";
app.Urls.Add($"http://0.0.0.0:{port}");

app.MapGet("/health", () => Results.Ok(new { status = "ok" }));

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
});

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
});

app.Run();

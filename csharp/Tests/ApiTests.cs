using System.Net;
using System.Text;
using System.Text.Json;
using Microsoft.AspNetCore.Mvc.Testing;
using Xunit;

namespace WordSearch.Tests;

/// <summary>
/// HTTP-level tests: request validation at the API boundary. Every request
/// outside the contract's bounds (openapi.yaml) must be a 400 ErrorResponse,
/// never a 5xx.
/// </summary>
public class ApiTests : IClassFixture<WebApplicationFactory<Program>>
{
    private const string Pin = """{"position":1,"letter":"a"}""";
    private readonly HttpClient _client;

    public ApiTests(WebApplicationFactory<Program> factory) => _client = factory.CreateClient();

    private Task<HttpResponseMessage> Post(string path, string body) =>
        _client.PostAsync(path, new StringContent(body, Encoding.UTF8, "application/json"));

    private static string Repeat(string s, int n) => string.Concat(Enumerable.Repeat(s, n));

    public static TheoryData<string, string> InvalidRequests => new()
    {
        { "/search/file", """{"wordLength":5,"letters":["a"],"hints":[{"position":0,"letter":"a"}]}""" },
        { "/search/many", """{"letters":"abc","hints":[{"position":-1,"letter":"a"}]}""" },
        { "/search/file", """{"wordLength":5,"letters":["a"],"hints":[{"position":32,"letter":"a"}]}""" },
        { "/search/file", """{"lang":"../../etc","wordLength":5,"letters":["a"]}""" },
        { "/search/file", """{"lang":"/etc","wordLength":5,"letters":["a"]}""" },
        { "/search/many", """{"lang":"xx","letters":"abc"}""" },
        { "/search/many", """{"lang":5,"letters":"abc"}""" },
        { "/search/file", """{"wordLength":0,"letters":["a"]}""" },
        { "/search/file", """{"wordLength":-1,"letters":["a"]}""" },
        { "/search/file", """{"wordLength":32,"letters":["a"]}""" },
        { "/search/file", """{"letters":["a"]}""" },
        { "/search/file", "{\"wordLength\":5,\"letters\":[" + Repeat("\"a\",", 32) + "\"a\"]}" },
        { "/search/file", "{\"wordLength\":5,\"hints\":[" + Repeat(Pin + ",", 31) + Pin + "]}" },
        { "/search/many", "{\"letters\":\"" + Repeat("a", 33) + "\"}" },
        { "/search/many", "{\"hints\":[" + Pin + "]}" },
        { "/search/many", """{"letters":123}""" },
        { "/search/file", """{"wordLength":5,"hints":[null]}""" },
        { "/search/file", """{"wordLength":5}""" },
        { "/search/file", "{not json" },
        { "/search/many", "{not json" },
    };

    [Theory]
    [MemberData(nameof(InvalidRequests))]
    public async Task InvalidRequestIs400(string path, string body)
    {
        var res = await Post(path, body);
        var text = await res.Content.ReadAsStringAsync();
        Assert.True(res.StatusCode == HttpStatusCode.BadRequest, $"{(int)res.StatusCode}: {text}");
        Assert.False(string.IsNullOrEmpty(JsonDocument.Parse(text).RootElement.GetProperty("error").GetString()));
    }

    // The in-memory TestServer does not apply Kestrel's MaxRequestBodySize (the
    // container answers 413); here the body is still rejected as a 4xx.
    [Fact]
    public async Task OversizedBodyIsClientError()
    {
        var res = await Post("/search/many", "{\"letters\":\"" + Repeat("a", 70000) + "\"}");
        Assert.InRange((int)res.StatusCode, 400, 499);
        var text = await res.Content.ReadAsStringAsync();
        Assert.False(string.IsNullOrEmpty(JsonDocument.Parse(text).RootElement.GetProperty("error").GetString()));
    }

    [Fact]
    public async Task ValidRequestsAtTheBoundsAre200()
    {
        var file = await Post("/search/file",
            """{"lang":"fr","wordLength":5,"letters":["e","l","i","s","a"],"hints":[{"position":1,"letter":"s"}]}""");
        Assert.Equal(HttpStatusCode.OK, file.StatusCode);
        var body = JsonDocument.Parse(await file.Content.ReadAsStringAsync()).RootElement;
        Assert.Equal(body.GetProperty("words").GetArrayLength(), body.GetProperty("count").GetInt32());
        Assert.True(body.GetProperty("count").GetInt32() > 0);

        var many = await Post("/search/many", "{\"lang\":\"en\",\"letters\":\"" + Repeat("a", 32) + "\"}");
        Assert.Equal(HttpStatusCode.OK, many.StatusCode);
    }
}

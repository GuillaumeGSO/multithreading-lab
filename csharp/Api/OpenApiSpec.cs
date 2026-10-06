using YamlDotNet.Serialization;

namespace WordSearch.Api;

/// <summary>
/// The API contract — the repository's openapi.yaml — loaded once at startup and
/// kept both verbatim (YAML) and converted to JSON for /openapi.json.
/// </summary>
public sealed record OpenApiSpec(string Yaml, string Json)
{
    /// <summary>Reads the spec from OPENAPI_PATH (default: openapi.yaml at the repository root).</summary>
    public static OpenApiSpec Load()
    {
        var path = Environment.GetEnvironmentVariable("OPENAPI_PATH")
            ?? Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..", "openapi.yaml");
        var yaml = File.ReadAllText(path);

        // Unquoted scalars are typed (int/bool/null) so the JSON keeps the YAML's types.
        var document = new DeserializerBuilder()
            .WithAttemptingUnquotedStringTypeDeserialization()
            .Build()
            .Deserialize<object>(yaml);
        var json = new SerializerBuilder().JsonCompatible().Build().Serialize(document);
        return new OpenApiSpec(yaml, json);
    }
}

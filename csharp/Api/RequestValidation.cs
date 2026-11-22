using System.ComponentModel.DataAnnotations;
using System.Text.Json;
using WordSearch.Api.Contracts;

namespace WordSearch.Api;

/// <summary>
/// Validates request bodies against the constraints NSwag generates from
/// openapi.yaml ([Range], [MaxLength], [StringLength], [Required]). Minimal APIs
/// do not run DataAnnotations by themselves, and the validator does not recurse
/// into collections, so each hint is checked explicitly.
/// </summary>
public static class RequestValidation
{
    /// <summary>The first violation in a /search/file body, or null when valid.</summary>
    public static string? Validate(SearchFileRequest req) =>
        CheckLang(req.Lang) ?? CheckObject(req, prefix: null) ?? CheckHints(req.Hints);

    /// <summary>The first violation in a /search/many body, or null when valid.</summary>
    public static string? Validate(SearchManyRequest req) =>
        CheckLang(req.Lang) ?? CheckObject(req, prefix: null) ?? CheckHints(req.Hints);

    /// <summary>
    /// The first violation that binding hides, or null when there is none. Checked
    /// on the raw JSON because the generated DTOs cannot tell them apart:
    ///   * every optional field is typed nullable, so `"strict": null` would bind
    ///     like an absent field (only Hint.letter is nullable in the contract);
    ///   * the enum converter also reads integers, so `"lang": 0` would bind as fr.
    /// </summary>
    public static string? CheckRawJson(JsonElement root)
    {
        if (root.ValueKind != JsonValueKind.Object) return null; // left to the binder
        foreach (var field in root.EnumerateObject())
        {
            if (field.Value.ValueKind == JsonValueKind.Null) return $"{field.Name}: must not be null";
            if (field.Name == "lang" && field.Value.ValueKind != JsonValueKind.String)
                return "lang: must be one of fr, en";
            if (field.Value.ValueKind != JsonValueKind.Array) continue;
            var i = 0;
            foreach (var item in field.Value.EnumerateArray())
            {
                var path = $"{field.Name}[{i++}]";
                if (item.ValueKind == JsonValueKind.Null) return $"{path}: must not be null";
                if (field.Name != "hints" || item.ValueKind != JsonValueKind.Object) continue;
                foreach (var prop in item.EnumerateObject())
                {
                    if (prop.Name != "letter" && prop.Value.ValueKind == JsonValueKind.Null)
                        return $"{path}.{prop.Name}: must not be null";
                }
            }
        }
        return null;
    }

    // Integers are refused by CheckRawJson; this guards the bound value as well.
    private static string? CheckLang(Lang? lang) =>
        lang is { } l && !Enum.IsDefined(l) ? "lang: must be one of fr, en" : null;

    private static string? CheckHints(ICollection<Contracts.Hint>? hints)
    {
        if (hints == null) return null;
        var i = 0;
        foreach (var hint in hints)
        {
            var prefix = $"hints[{i++}]";
            if (hint == null) return $"{prefix}: must be an object";
            if (CheckObject(hint, prefix) is { } error) return error;
        }
        return null;
    }

    private static string? CheckObject(object model, string? prefix)
    {
        var results = new List<ValidationResult>();
        if (Validator.TryValidateObject(model, new ValidationContext(model), results, validateAllProperties: true))
            return null;
        var first = results[0];
        var field = string.Join(", ", first.MemberNames.Select(Camel));
        var path = prefix == null ? field : $"{prefix}.{field}";
        return $"{path}: {first.ErrorMessage}";
    }

    // Report the wire (camelCase) name rather than the C# property name.
    private static string Camel(string name) =>
        name.Length == 0 ? name : char.ToLowerInvariant(name[0]) + name[1..];
}

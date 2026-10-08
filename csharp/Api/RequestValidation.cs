using System.ComponentModel.DataAnnotations;
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

    // The enum converter also accepts integers, so an undefined value can get through.
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

#!/usr/bin/env python3
"""Generate C++ request/response models from the API contract (openapi.yaml).

Reads `components.schemas` and writes a header with one struct per schema plus
nlohmann::json `from_json` / `to_json` overloads. Invoked by CMake at build time;
the output lives in the build tree and is never committed.

Mapping rules (OpenAPI 3.0 subset used by the contract):
  * string -> std::string, integer -> int, boolean -> bool,
    array -> std::vector<T>, $ref -> the referenced struct.
  * required field          -> plain member; from_json throws when it is absent.
  * optional with a default -> plain member initialised to that default.
  * optional without default, or nullable -> std::optional<T>.
  * $ref to a scalar schema (e.g. a string enum) -> that scalar, inheriting the
    referenced schema's default and constraints; only object schemas become structs.

Validation: each struct also gets `validate(const T&)`, generated from the
schema's constraints (integer minimum/maximum, string enum/maxLength counted in
code points, array maxItems, and nested $ref objects). It throws
std::invalid_argument naming the offending field.

Usage: gen_models.py <openapi.yaml> <output header>
"""

import sys
from pathlib import Path

import yaml

SCALARS = {"string": "std::string", "integer": "int", "boolean": "bool"}


def ref_name(ref: str) -> str:
    return ref.rsplit("/", 1)[-1]


# components.schemas of the spec being generated (set in main()).
SCHEMAS: dict = {}


def is_object(schema: dict) -> bool:
    return schema.get("type", "object") == "object"


def resolve(schema: dict) -> dict:
    """Inline a $ref to a scalar schema: the referenced schema with any sibling
    keys on top. Refs to object schemas are left as refs (they become structs)."""
    if "$ref" not in schema:
        return schema
    target = SCHEMAS[ref_name(schema["$ref"])]
    if is_object(target):
        return schema
    merged = dict(target)
    merged.update({k: v for k, v in schema.items() if k != "$ref"})
    return merged


def cpp_type(schema: dict) -> str:
    schema = resolve(schema)
    if "$ref" in schema:
        return ref_name(schema["$ref"])
    kind = schema.get("type")
    if kind == "array":
        return f"std::vector<{cpp_type(schema['items'])}>"
    if kind in SCALARS:
        return SCALARS[kind]
    raise ValueError(f"unsupported schema type: {schema}")


def cpp_literal(value, schema: dict) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(value, list) and not value:
        return "{}"
    raise ValueError(f"unsupported default {value!r} for {schema}")


def dependencies(schema: dict) -> set[str]:
    deps = set()
    for prop in schema.get("properties", {}).values():
        target = resolve(prop.get("items", prop))
        if "$ref" in target:
            deps.add(ref_name(target["$ref"]))
    return deps


def ordered(schemas: dict) -> list[str]:
    """Schema names with every referenced struct declared before its users."""
    done: list[str] = []

    def visit(name: str) -> None:
        if name in done:
            return
        for dep in sorted(dependencies(schemas[name])):
            visit(dep)
        done.append(name)

    for name in schemas:
        if is_object(schemas[name]):
            visit(name)
    return done


def comment(text: str | None, indent: str) -> list[str]:
    if not text:
        return []
    return [f"{indent}// {line}".rstrip() for line in text.strip().splitlines()]


def render_struct(name: str, schema: dict) -> list[str]:
    required = set(schema.get("required", []))
    props = {field: resolve(prop) for field, prop in schema.get("properties", {}).items()}
    out = comment(schema.get("description"), "")
    out.append(f"struct {name} {{")
    for field, prop in props.items():
        base = cpp_type(prop)
        out += comment(prop.get("description"), "    ")
        if field in required and not prop.get("nullable"):
            init = " = 0" if base == "int" else " = false" if base == "bool" else ""
            out.append(f"    {base} {field}{init};")
        elif "default" in prop and not prop.get("nullable"):
            out.append(f"    {base} {field} = {cpp_literal(prop['default'], prop)};")
        else:
            out.append(f"    std::optional<{base}> {field};")
    out.append("};")
    out.append("")

    # from_json: required fields must be present; others keep their default.
    # Integers must be JSON integers (the library would truncate 5.5 to 5).
    out.append(f"inline void from_json(const nlohmann::json& j, {name}& o) {{")
    for field, prop in props.items():
        base = cpp_type(prop)
        if prop.get("type") == "integer":
            out.append(f'    if (j.contains("{field}") && !j["{field}"].is_null() && !j["{field}"].is_number_integer()) '
                       f'throw std::invalid_argument("{field}: must be an integer");')
        if field in required and not prop.get("nullable"):
            out.append(f'    j.at("{field}").get_to(o.{field});')
        elif "default" in prop and not prop.get("nullable"):
            out.append(f'    if (j.contains("{field}") && !j["{field}"].is_null()) j["{field}"].get_to(o.{field});')
        else:
            out.append(f'    if (j.contains("{field}") && !j["{field}"].is_null()) o.{field} = j["{field}"].get<{base}>();')
    out.append("}")
    out.append("")

    out.append(f"inline void to_json(nlohmann::json& j, const {name}& o) {{")
    out.append("    j = nlohmann::json::object();")
    for field, prop in props.items():
        if field in required and not prop.get("nullable") or "default" in prop and not prop.get("nullable"):
            out.append(f'    j["{field}"] = o.{field};')
        else:
            out.append(f'    if (o.{field}) j["{field}"] = *o.{field};')
    out.append("}")
    out.append("")

    out.append(f"inline void validate(const {name}& o) {{")
    out.append("    (void)o;")
    for field, prop in props.items():
        optional = not (field in required and not prop.get("nullable")) and not (
            "default" in prop and not prop.get("nullable"))
        value = f"(*o.{field})" if optional else f"o.{field}"
        checks = render_checks(field, prop, value)
        if not checks:
            continue
        if optional:
            out.append(f"    if (o.{field}) {{")
            out += ["    " + c for c in checks]
            out.append("    }")
        else:
            out += checks
    out.append("}")
    out.append("")
    return out


def render_checks(field: str, prop: dict, value: str) -> list[str]:
    """C++ statements enforcing the constraints of one property on `value`."""
    out = []

    def check(cond: str, message: str) -> None:
        out.append(f'    if ({cond}) throw std::invalid_argument("{field}: {message}");')

    kind = prop.get("type")
    if kind == "integer":
        if "minimum" in prop:
            lo = prop["minimum"]
            check(f"{value} < {lo}", f"must be >= {lo}")
        if "maximum" in prop:
            hi = prop["maximum"]
            check(f"{value} > {hi}", f"must be <= {hi}")
    elif kind == "string":
        if "enum" in prop:
            cond = " && ".join(f"{value} != {cpp_literal(v, prop)}" for v in prop["enum"])
            check(cond, "must be one of " + ", ".join(prop["enum"]))
        if "maxLength" in prop:
            limit = prop["maxLength"]
            check(f"detail::codepoints({value}) > {limit}", f"at most {limit} characters")
    elif kind == "array":
        if "maxItems" in prop:
            limit = prop["maxItems"]
            check(f"{value}.size() > {limit}", f"at most {limit} items")
        if "$ref" in resolve(prop["items"]):
            out.append(f"    for (const auto& item : {value}) validate(item);")
    elif "$ref" in prop:
        out.append(f"    validate({value});")
    return out


def main() -> None:
    spec_path, out_path = Path(sys.argv[1]), Path(sys.argv[2])
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    schemas = spec["components"]["schemas"]
    SCHEMAS.update(schemas)
    version = spec["info"]["version"]

    lines = [
        f"// Generated from {spec_path.name} by cpp/codegen/gen_models.py — do not edit.",
        "#pragma once",
        "",
        "#include <nlohmann/json.hpp>",
        "",
        "#include <cstddef>",
        "#include <optional>",
        "#include <stdexcept>",
        "#include <string>",
        "#include <vector>",
        "",
        "namespace api {",
        "",
        "namespace detail {",
        "// Number of UTF-8 code points in s (continuation bytes are not counted).",
        "inline std::size_t codepoints(const std::string& s) {",
        "    std::size_t n = 0;",
        "    for (unsigned char c : s) n += (c & 0xC0) != 0x80;",
        "    return n;",
        "}",
        "}  // namespace detail",
        "",
        "// info.version of the contract these models were generated from.",
        f'inline constexpr const char* kVersion = "{version}";',
        "",
    ]
    for name in ordered(schemas):
        lines += render_struct(name, schemas[name])
    lines.append("}  // namespace api")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

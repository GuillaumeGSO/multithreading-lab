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

Usage: gen_models.py <openapi.yaml> <output header>
"""

import sys
from pathlib import Path

import yaml

SCALARS = {"string": "std::string", "integer": "int", "boolean": "bool"}


def ref_name(ref: str) -> str:
    return ref.rsplit("/", 1)[-1]


def cpp_type(schema: dict) -> str:
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
        target = prop.get("items", prop)
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
        visit(name)
    return done


def comment(text: str | None, indent: str) -> list[str]:
    if not text:
        return []
    return [f"{indent}// {line}".rstrip() for line in text.strip().splitlines()]


def render_struct(name: str, schema: dict) -> list[str]:
    required = set(schema.get("required", []))
    props = schema.get("properties", {})
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
    out.append(f"inline void from_json(const nlohmann::json& j, {name}& o) {{")
    for field, prop in props.items():
        base = cpp_type(prop)
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
    return out


def main() -> None:
    spec_path, out_path = Path(sys.argv[1]), Path(sys.argv[2])
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    schemas = spec["components"]["schemas"]
    version = spec["info"]["version"]

    lines = [
        f"// Generated from {spec_path.name} by cpp/codegen/gen_models.py — do not edit.",
        "#pragma once",
        "",
        "#include <nlohmann/json.hpp>",
        "",
        "#include <optional>",
        "#include <string>",
        "#include <vector>",
        "",
        "namespace api {",
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

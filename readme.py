#!/usr/bin/env python3
"""Generates Go operation usage snippets from an sdkgen.lock TypeAPI specification file."""

import argparse
import json
import re
from pathlib import Path


def to_pascal_case(name: str) -> str:
    """Convert snake_case, camelCase, dot.case, or hyphenated names to exported Go PascalCase."""
    if not name:
        return ""
    parts = re.split(r"[._-]+", name)
    return "".join(p.capitalize() for p in parts if p)


def map_schema_to_type(schema: dict) -> str:
    """Map a TypeAPI schema definition to its corresponding clean Go type name."""
    if not schema or not isinstance(schema, dict):
        return "any"

    schema_type = schema.get("type")

    if schema_type == "reference":
        return to_pascal_case(schema.get("target", "any"))

    type_mapping = {
        "string": "string",
        "integer": "int",
        "number": "float64",
        "boolean": "bool",
        "any": "any",
    }

    if schema_type == "array":
        item_type = map_schema_to_type(schema.get("schema", {}))
        return f"[]{item_type}"

    if schema_type == "map":
        val_type = map_schema_to_type(schema.get("schema", {}))
        return f"map[string]{val_type}"

    return type_mapping.get(schema_type, "any")


def generate_usage(lock_file_path: Path) -> str:
    """Read sdkgen.lock TypeAPI spec and generate clean Go operation snippets."""
    if not lock_file_path.is_file():
        return "// No sdkgen.lock found to generate usage examples."

    try:
        with open(lock_file_path, "r", encoding="utf-8") as f:
            spec = json.load(f)
    except (json.JSONDecodeError, OSError):
        return "// Failed to parse sdkgen.lock."

    api_key = next(iter(spec.keys()), None)
    if not api_key or "operations" not in spec[api_key]:
        return "// No operations found in spec."

    operations = spec[api_key].get("operations", {})
    lines = []

    for op_id, op in operations.items():
        if "." in op_id:
            tag, method_raw = op_id.split(".", 1)
            tag_accessor = f"client.{to_pascal_case(tag)}()"
        else:
            method_raw = op_id
            tag_accessor = "client"

        method_name = to_pascal_case(method_raw)
        args_spec = op.get("arguments", {})
        call_args = []

        for arg_name, arg_data in args_spec.items():
            param_in = arg_data.get("in")
            schema = arg_data.get("schema", {})
            type_name = map_schema_to_type(schema)

            if param_in == "path":
                call_args.append(f'"{arg_name}"')
            elif param_in == "body":
                call_args.append(f"{type_name}{{}}")
            elif param_in in ("query", "header"):
                if schema.get("type") == "string":
                    call_args.append(f'"{arg_name}"')
                elif schema.get("type") == "integer":
                    call_args.append("1")
                elif schema.get("type") == "boolean":
                    call_args.append("true")
                else:
                    call_args.append("nil")

        return_spec = op.get("return", {})
        return_schema = return_spec.get("schema", {})
        return_type = map_schema_to_type(return_schema) if return_schema else None

        description = op.get("description", "").strip()
        if description:
            first_line = description.split(".")[0] + "."
            lines.append(f"// {first_line}")

        call_str = ", ".join(call_args)
        if return_type and return_type != "void":
            lines.append(f"response, err := {tag_accessor}.{method_name}({call_str})")
        else:
            lines.append(f"err := {tag_accessor}.{method_name}({call_str})")

        lines.append("")

    return "\n".join(lines).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Go usage snippets from sdkgen.lock.")
    parser.add_argument("--lock-file", type=Path, default=Path("sdkgen.lock"))
    args = parser.parse_args()

    usage_output = generate_usage(args.lock_file)
    print(usage_output)


if __name__ == "__main__":
    main()

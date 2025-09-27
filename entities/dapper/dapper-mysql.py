# Licensed under the MIT License (MIT)

import os
import sys
import xml.etree.ElementTree as ET

INDENT = "\t"
NEWLINE = "\n"
OUTPUT_PATH = "SakilaDapper/Model/ModelsGenerated.cs"
OUTPUT_MAP_PATH = "SakilaDapper/Model/MappersGenerated.cs"
NAMESPACE = "SakilaDapper.Model"

def resolve_type(db_type: str) -> str:
    if db_type.startswith("tinyint(1)"):
        return "bool"
    if any(db_type.startswith(t) for t in ["tinyint", "smallint", "mediumint", "int"]):
        if "unsigned" in db_type:
            return "uint"
        return "int"
    if db_type.startswith("bigint"):
        if "unsigned" in db_type:
            return "ulong"
        return "long"
    if any(db_type.startswith(t) for t in ["timestamp", "datetime"]):
        return "DateTime"
    if any(db_type.startswith(t) for t in ["varchar", "char", "tinytext", "mediumtext", "text", "longtext", "set", "enum", "geometry"]):
        return "string"
    if db_type.startswith("year"):
        return "int"
    if db_type.startswith("date"):
        return "DateOnly"
    if db_type.startswith("decimal"):
        return "decimal"
    if db_type.startswith("blob"):
        return "byte[]"
    raise ValueError(f"Unknown type: {db_type}")

def resolve_type_from_column(column: ET.Element) -> str:
    db_type = column.get("DatabaseType").lower()
    nullable = column.get("Nullable", "false").lower() == "true"
    resolved_type = resolve_type(db_type)
    if nullable and resolved_type not in ["string", "byte[]"]:
        return resolved_type + "?"
    return resolved_type

def get_class_lines(table: ET.Element):
    class_name = table.get("ClassName")
    table_comment = table.get("Comment")

    yield ""
    if table_comment:
        yield "/// <summary>"
        yield f"/// {table_comment}"
        yield "/// </summary>"
    yield f"public partial class {class_name}"
    yield "{"
    
    for column in table.findall("Column"):
        field_name = column.get("FieldName")
        comment = column.get("Comment")

        if comment:
            yield f"{INDENT}/// <summary>"
            yield f"{INDENT}/// {comment}"
            yield f"{INDENT}/// </summary>"

        csharp_type = resolve_type_from_column(column)
        yield f"{INDENT}public {csharp_type} {field_name} {{ get; set; }}"

    yield "}"

def get_mappers_lines(table: ET.Element) -> str:
    class_name = table.get("ClassName")
    items = [
        f'("{col.get("Name")}", nameof({class_name}.{col.get("FieldName")}))'
        for col in table.findall("Column")
    ]
    
    if not items:
        return
    
    yield f"{INDENT*2}Register<{class_name}>("
    yield from (f"{INDENT*3}{line}," for line in items[:-1])
    yield f"{INDENT*3}{items[-1]}"
    yield f"{INDENT*2});"

xml_data = sys.stdin.read()
tree = ET.ElementTree(ET.fromstring(xml_data))
root = tree.getroot()

output_file = os.path.abspath(OUTPUT_PATH)

mappers = []
classes = []
for db in root.findall("Database"):
    for schema in db.findall("Schema"):
        for table in schema.findall("Table"):
            classes.extend(get_class_lines(table))
            mappers.extend(get_mappers_lines(table))

content_lines = [
    "using System;",
    "using System.ComponentModel.DataAnnotations;",
    "using System.ComponentModel.DataAnnotations.Schema;",
    "",
    f"namespace {NAMESPACE};",
]
content_lines.extend(classes)

content = NEWLINE.join(content_lines)
with open(output_file, "w", encoding="utf-8", newline=NEWLINE) as f:
    f.write(content)

mappers_lines = [
    "using Dapper;",
    "namespace SakilaDapper.Model;",
    "",
    "public class MapperGenerated",
    "{",
    INDENT + "private static void Register<T>(params (string Column, string Property)[] map)",
    INDENT + "{",
    INDENT*2 + "var type = typeof(T);",
    INDENT*2 + "var propMap = map.ToDictionary(",
    INDENT*3 + "kvp => kvp.Column,",
    INDENT*3 + "kvp => type.GetProperty(kvp.Property)",
    INDENT*4 + "?? throw new InvalidOperationException($\"Property {kvp.Property} not found on {type}\")",
    INDENT*2 + ");",
    "",
    INDENT*2 + "SqlMapper.SetTypeMap(typeof(T),",
    INDENT*3 + "new CustomPropertyTypeMap(typeof(T),",
    INDENT*3 + "(_, columnName) => propMap[columnName]",
    INDENT*2 + "));",
    INDENT + "}",
    "",
    INDENT + "public static void Register()",
    INDENT + "{"
]

mappers_lines.extend(mappers)
mappers_lines.append(INDENT + "}")
mappers_lines.append("}")

output_map_file = os.path.abspath(OUTPUT_MAP_PATH)
map_content = NEWLINE.join(mappers_lines)
with open(output_map_file, "w", encoding="utf-8", newline=NEWLINE) as f:
    f.write(map_content)
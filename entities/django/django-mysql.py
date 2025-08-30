# Licensed under the MIT License (MIT)

import sys
import xml.etree.ElementTree as ET

INDENT = "    "
NEWLINE = "\n"
ROOT_PATH = "models.py"

def resolve_type(column: ET.Element) -> str:
    args = []
    db_type = column.get("DatabaseType").lower()
    if column.get("Nullable", "false").lower() == "true":
        args.append("null=True")

    db_type_args = []
    if "(" in db_type:
        parentheses_content = db_type.split('(')[1].split(')')[0]
        db_type_args = parentheses_content.split(',')

    if db_type.startswith("tinyint(1)"):
        return f"models.BooleanField({", ".join(args)})"
    if db_type.startswith("tinyint"):
        return f"models.SmallIntegerField({", ".join(args)})"
    if db_type.startswith("int") or db_type.startswith("mediumint"):
        return f"models.IntegerField({", ".join(args)})"
    if db_type.startswith("bigint"):
        return f"models.BigIntegerField({", ".join(args)})"
    if "text" in db_type:
        return f"models.TextField({", ".join(args)})"
    if "char" in db_type:
        if len(db_type_args) == 1:
            args.insert(0, f"max_length={db_type_args[0]}")
        return f"models.CharField({", ".join(args)})"
    if "datetime" in db_type or "timestamp" in db_type:
        return f"models.DateTimeField({", ".join(args)})"
    if "decimal" in db_type or "numeric" in db_type:
        precision = 20
        scale = 6
        if len(db_type_args) == 2:
            precision, scale = map(str.strip, db_type_args)
        args.append(f"max_digits=" + precision.strip())
        args.append(f"decimal_places=" + scale.strip())
        return f"models.DecimalField({", ".join(args)})"
    if db_type in ("float", "double", "real"):
        return f"models.FloatField({", ".join(args)})"
    return f"models.TextField({", ".join(args)})"

def generate_table(table: ET.Element) -> str:
    pk_columns = [c for c in table.findall("Column") if c.get("PrimaryKey", "false").lower() == "true"]
    if len(pk_columns) > 1:
        print("Composite PK is not supported (table " + table.get("Name") + ")")
        return None

    #view
    if not pk_columns:
        print("Tables without PK or views is not supported (" + table.get("Name") + ")")
        return None

    class_name = table.get("ClassName")
    lines = [f"class {class_name}(models.Model):"]

    fk_column_names = {fk.get("FromColumn") for fk in table.findall("ForeignKey")}

    for column in table.findall("Column"):
        name = column.get("FieldName")
        column_name = column.get("Name")
        if column_name in fk_column_names:
            continue

        is_pk = column.get("PrimaryKey", "false").lower() == "true"
        auto = column.get("AutoIncrement", "false").lower() == "true"

        if is_pk and auto:
            lines.append(f"{INDENT}{name} = models.AutoField(primary_key=True)")
            continue

        field = resolve_type(column)
        lines.append(f"{INDENT}{name} = {field}")

    # Foreign keys
    for fk in table.findall("ForeignKey"):
        field_name = fk.get("FieldName")
        target_class = fk.get("ToClassName")
        nullable = fk.get("Nullable", "false").lower() == "true"
        nullopt = ", null=True" if nullable else ""
        lines.append(f"{INDENT}{field_name} = models.ForeignKey('{target_class}', on_delete=models.CASCADE{nullopt})")

    lines.append("")
    return NEWLINE.join(lines)

# main
xml_data = sys.stdin.read()
tree = ET.ElementTree(ET.fromstring(xml_data))
root = tree.getroot()

output = ["from django.db import models", ""]

for db in root.findall("Database"):
    for schema in db.findall("Schema"):
        for table in schema.findall("Table"):
            model_code = generate_table(table)
            if model_code:
                output.append(model_code)

with open(ROOT_PATH, "w", encoding="utf-8", newline='') as f:
    f.write(NEWLINE.join(output))

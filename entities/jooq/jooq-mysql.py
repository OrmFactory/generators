# Licensed under the MIT License. See LICENSE file in the project root for details.

import os
import sys
import xml.etree.ElementTree as ET

PACKAGE_NAME = "com.example.jooq"
INDENT = "    "
NEWLINE = "\n"
ROOT_PATH = "../src/main/java/com/example/jooq"


def resolve_type(column: ET.Element) -> str:
    db_type = column.get("DatabaseType", "").lower()
    if db_type.startswith("tinyint(1)"):
        return "Boolean"
    if any(db_type.startswith(t) for t in ["tinyint", "smallint", "mediumint", "int"]):
        return "Integer"
    if any(db_type.startswith(t) for t in ["timestamp", "datetime"]):
        return "java.time.LocalDateTime"
    if any(db_type.startswith(t) for t in ["varchar", "char", "text", "set", "enum", "geometry"]):
        return "String"
    if db_type.startswith("year"):
        return "Integer"
    if db_type.startswith("decimal"):
        return "java.math.BigDecimal"
    if db_type.startswith("blob"):
        return "byte[]"
    raise ValueError(f"Unknown type: {db_type}")


def resolve_sql_datatype(column: ET.Element) -> str:
    db_type = column.get("DatabaseType", "").lower()
    length = column.get("Length")
    base = None

    if db_type.startswith("tinyint(1)"):
        base = "SQLDataType.BOOLEAN"
    elif any(db_type.startswith(t) for t in ["tinyint", "smallint", "mediumint", "int"]):
        base = "SQLDataType.INTEGER"
    elif any(db_type.startswith(t) for t in ["timestamp", "datetime"]):
        base = "SQLDataType.LOCALDATETIME"
    elif any(db_type.startswith(t) for t in ["varchar", "char", "text", "set", "enum", "geometry"]):
        base = f"SQLDataType.VARCHAR({length})" if length else "SQLDataType.VARCHAR"
    elif db_type.startswith("year"):
        base = "SQLDataType.INTEGER"
    elif db_type.startswith("decimal"):
        base = "SQLDataType.DECIMAL"
    elif db_type.startswith("blob"):
        base = "SQLDataType.BLOB"
    else:
        base = "SQLDataType.OTHER"

    nullable = column.get("Nullable")
    if nullable and nullable.lower() == "true":
        return f"{base}.nullable(true)"
    return base


def lower_first(s: str) -> str:
    return s[:1].lower() + s[1:] if s else s


def write_file(directory: str, filename: str, content: str):
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, filename), "w", encoding="utf-8") as f:
        f.write(content)


def generate_table_class(table: ET.Element) -> str:
    table_name = table.get("Name")
    class_name = table.get("ClassName")
    comment = table.get("Comment")

    lines = [
        f"package {PACKAGE_NAME};",
        "",
        "import org.jooq.*;",
        "import org.jooq.Record;",
        "import org.jooq.impl.*;",
        "import org.jooq.impl.Internal;",
        "import java.math.*;",
        "import java.time.*;",
        "",
    ]

    if comment:
        lines.append(f"/** {comment} */")

    lines.append(f"public class {class_name} extends TableImpl<Record> {{")
    lines.append("")
    lines.append(f"{INDENT}public static final {class_name} {class_name.upper()} = new {class_name}();")
    lines.append("")

    pk_columns = []
    column_name_to_field = {}

    # Columns
    for column in table.findall("Column"):
        field_name = column.get("FieldName")
        column_name = column.get("Name")
        column_name_to_field[column_name] = field_name
        java_type = resolve_type(column)
        sql_type = resolve_sql_datatype(column)
        col_comment = column.get("Comment")
        nullable = column.get("Nullable", "false").lower() == "true"
        nullable_clause = ""
        if nullable == False:
            nullable_clause = ".nullable(false)"

        if col_comment:
            lines.append(f"{INDENT}/** {col_comment} */")

        lines.append(
            f"{INDENT}public final TableField<Record, {java_type}> {field_name} = "
            f"createField(DSL.name(\"{column_name}\"), {sql_type}{nullable_clause}, this);"
        )
        lines.append("")

        if column.get("PrimaryKey", "").lower() == "true":
            pk_columns.append(field_name)

    # Primary key
    if pk_columns:
        joined = ", ".join(pk_columns)
        lines.append(f"{INDENT}public final UniqueKey<Record> PK = Internal.createUniqueKey(this, {joined});")
        lines.append("")

    # Foreign keys
    for fk in table.findall("ForeignKey"):
        fk_name = fk.get("Name")
        field_name = fk.get("FieldName")
        from_column = fk.get("FromColumn")
        to_class = fk.get("ToClassName")
        to_field = fk.get("ToFieldName")
        is_virtual = fk.get("Virtual", "false").lower() == "true"
        enforced = "false" if is_virtual else "true"
        from_field_name = column_name_to_field.get(from_column)

        lines.append(f"{INDENT}public final ForeignKey<Record, Record> {field_name} = Internal.createForeignKey(")
        lines.append(f"{INDENT*2}this,")
        lines.append(f"{INDENT*2}DSL.name(\"{fk_name}\"),")
        lines.append(f"{INDENT*2}new TableField[]{{ {from_field_name} }},")
        lines.append(f"{INDENT*2}{PACKAGE_NAME}.{to_class}.{to_class.upper()}.PK,")
        lines.append(f"{INDENT*2}new TableField[]{{ {PACKAGE_NAME}.{to_class}.{to_class.upper()}.{to_field} }},")
        lines.append(f"{INDENT*2}{enforced}")
        lines.append(f"{INDENT});")
        lines.append("")

    # Constructor
    lines.append(f"{INDENT}private {class_name}() {{")
    lines.append(f"{INDENT*2}super(DSL.name(\"{table_name}\"));")
    lines.append(f"{INDENT}}}")
    lines.append("}")

    return NEWLINE.join(lines)
    

def main():
    xml_data = sys.stdin.read()
    tree = ET.ElementTree(ET.fromstring(xml_data))
    root = tree.getroot()
    output_dir = os.path.abspath(ROOT_PATH)

    for db in root.findall("Database"):
        for schema in db.findall("Schema"):
            for table in schema.findall("Table"):
                code = generate_table_class(table)
                class_name = table.get("ClassName")
                write_file(output_dir, f"{class_name}.java", code)


if __name__ == "__main__":
    main()

# Licensed under the MIT License. See LICENSE file in the project root for details.

import os
import sys
from typing import List
import xml.etree.ElementTree as ET

PACKAGE_NAME = "com.example"
INDENT = "    "
NEWLINE = "\n"
ROOT_PATH = "Models"

def resolve_type(column: ET.Element) -> str:
    db_type = column.get("DatabaseType").lower()
    nullable = column.get("Nullable", "false").lower() == "true"

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

def lower_first_char(s: str) -> str:
    return s[:1].lower() + s[1:] if s else s

def generate_composite_key_class(composite_key_class_name: str, key_columns: List[ET.Element]) -> str:
    lines = [f"package {PACKAGE_NAME}.model;", "", f"public class {composite_key_class_name} {{"]
    for column in key_columns:
        field_name = column.get("FieldName")
        java_type = resolve_type(column)
        lines.append(f"{INDENT}private {java_type} {lower_first_char(field_name)};")
        lines.append("")
        lines.extend(generate_field_accessors(field_name, java_type))
    lines.append("}")
    return NEWLINE.join(lines)

def write_file(directory: str, filename: str, content: str):
    with open(os.path.join(directory, filename), "w", encoding="utf-8") as f:
        f.write(content)

def generate_field_accessors(field_name: str, field_type: str) -> List[str]:
    lower = lower_first_char(field_name)
    return [
        f"{INDENT}public void set{field_name}({field_type} {lower}) {{",
        f"{INDENT*2}this.{lower} = {lower};",
        f"{INDENT}}}",
        "",
        f"{INDENT}public {field_type} get{field_name}() {{",
        f"{INDENT*2}return {lower};",
        f"{INDENT}}}",
        ""
    ]

def generate_table_entity(table: ET.Element, composite_key_class_name: str | None) -> str:
    fields = []
    accessors = []
    imports = ["import jakarta.persistence.*;"]

    for column in table.findall("Column"):
        column_name = column.get("Name")
        field_name = column.get("FieldName")
        comment = column.get("Comment")
        
        if column.get("PrimaryKey"):
            fields.append(f"{INDENT}@Id")
            if column.get("AutoIncrement"):
                fields.append(f"{INDENT}@GeneratedValue(strategy=GenerationType.AUTO)")

        fields.append(f"{INDENT}@Column(name = \"{column_name}\")")

        if comment:
            fields.append(f"{INDENT}/** {comment} */")

        java_type = resolve_type(column)
        fields.append(f"{INDENT}private {java_type} {lower_first_char(field_name)};")
        fields.append("")
        accessors.extend(generate_field_accessors(field_name, java_type))

    for fk in table.findall('ForeignKey'):
        from_col = fk.get('FromColumn')
        field_name = fk.get('FieldName')
        type_decl = fk.get('ClassName')
        fields.append(f"{INDENT}@ManyToOne(fetch = FetchType.LAZY)")
        fields.append(f"{INDENT}@JoinColumn(name = \"{from_col}\", insertable=false, updatable=false)")
        fields.append(f"{INDENT}private {type_decl} {lower_first_char(field_name)};")
        accessors.extend(generate_field_accessors(field_name, type_decl))

    reverse_keys = table.findall('ReverseKey')
    if reverse_keys:
        imports.append("import java.util.List;")
    for fk in reverse_keys:
        target = fk.get('ToClassName')
        to_field_name = fk.get('ToFieldName')
        field_name = fk.get('FieldName')
        lowerFieldName = lower_first_char(to_field_name)
        fields.append(f"{INDENT}@OneToMany(mappedBy = \"{lowerFieldName}\", fetch = FetchType.LAZY)")
        fields.append(f"{INDENT}private List<{target}> {lower_first_char(field_name)};")
        accessors.extend(generate_field_accessors(field_name, f"List<{target}>"))

    table_name = table.findtext('TableName')
    class_name = table.findtext('ClassName')
    comment = table.findtext('Comment')

    lines = [
        f"package {PACKAGE_NAME}.model;",
        "",
        *imports,
        ""
    ]
    if composite_key_class_name:
        lines.append(f"import {PACKAGE_NAME}.model.{composite_key_class_name};")
    lines.append("@Entity")
    lines.append(f"@Table(name = \"{table_name}\")")
    if composite_key_class_name:
        lines.append(f"@IdClass({composite_key_class_name}.class)")
    if comment:
        lines.append(f"/** {comment} */")
    lines.append(f"public class {class_name} {{")
    lines.extend(fields)
    lines.extend(accessors)
    lines.append("}")
    return NEWLINE.join(lines)

def generate_table_repository(class_name: str, key_type: str) -> str:
    return NEWLINE.join([
        f"package {PACKAGE_NAME}.model;",
        "",
        "import org.springframework.data.repository.CrudRepository;",
        f"import {PACKAGE_NAME}.model.{class_name};",
        "",
        f"public interface {class_name}Repository extends CrudRepository<{class_name}, {key_type}> {{",
        "}"
    ])

# main
xml_data = sys.stdin.read()
tree = ET.ElementTree(ET.fromstring(xml_data))
root = tree.getroot()
output_dir = os.path.abspath(ROOT_PATH)
os.makedirs(output_dir, exist_ok=True)

for db in root.findall('Database'):
    for schema in db.findall('Schema'):
        for table in schema.findall('Table'):
            composite_key_class_name = None
            primary_keys = [col for col in table.findall('Column') if col.get('PrimaryKey')]
            class_name = table.get("ClassName")

            if len(primary_keys) > 1:
                composite_key_class_name = class_name + "Id"
                composite_key_code = generate_composite_key_class(composite_key_class_name, primary_keys)
                write_file(output_dir, composite_key_class_name + ".java", composite_key_code)

            if primary_keys:
                entity_code = generate_table_entity(table, composite_key_class_name)
                write_file(output_dir, class_name + ".java", entity_code)
    
                pk_column = primary_keys[0];
                key_type = resolve_type(pk_column)
                repository_code = generate_table_repository(class_name, composite_key_class_name or key_type)
                write_file(output_dir, class_name + "Repository.java", repository_code)

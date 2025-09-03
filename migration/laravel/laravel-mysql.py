# Licensed under the MIT License (MIT)

import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime

INDENT = "    "
NEWLINE = "\n"

up = []
down = []
actions = []

def parse_column_list(s):
    columns = s.split(",")
    return '[' + ', '.join(f"'{c.strip()}'" for c in columns) + ']'

def parse_column_element(column_element):
    name = column_element.get('Name')
    data_type = column_element.get('Type')
    nullable = column_element.get('Nullable', 'false').lower() == 'true'
    default = column_element.get('Default', '')
    comment = column_element.get('Comment', '')
    auto_increment = column_element.get('AutoIncrement', 'false').lower() == 'true'

    method = f"$table->{laravel_type(data_type)}('{name}')"
    if auto_increment:
        method += '->increments()'
    if nullable:
        method += '->nullable(true)'
    if default:
        if default.lower() == 'null':
            method += "->default(null)"
        else:
            method += f"->default('{default}')"
    if comment:
        method += f"->comment('{comment}')"

    return method

def laravel_type(db_type):
    mapping = {
        'integer': 'integer',
        'string': 'string',
        'text': 'text',
        'boolean': 'boolean',
        'datetime': 'dateTime',
        'date': 'date',
        'float': 'float',
        'double': 'double',
        'bigint': 'bigInteger',
        'smallint': 'smallInteger',
        'tinyint': 'tinyInteger',
        'char': 'char',
        'decimal': 'decimal'
    }
    return mapping.get(db_type.lower(), db_type)

def handle_create_table(diff):
    table = diff.attrib['Name']
    actions.append(f"create_{table}_table")

    up.append(f"Schema::create('{table}', function (Blueprint $table) {{")
    for column in diff.findall('Column'):
        up.append(INDENT + parse_column_element(column) + ';')

    for pk in diff.findall('PrimaryKey'):
        cols = parse_column_list(pk.get('Columns'))
        up.append(INDENT + f"$table->primary({cols}, '{pk.get('Name', 'pk_' + table)}');")

    for idx in diff.findall('Index'):
        up.append(INDENT + f"$table->index({parse_column_list(idx.get('Columns'))}, '{idx.get('Name')}');")

    for uq in diff.findall('Unique'):
        up.append(INDENT + f"$table->unique({parse_column_list(uq.get('Columns'))}, '{uq.get('Name')}');")

    for fk in diff.findall('ForeignKey'):
        up.append(INDENT + handle_foreign_key_inline(fk))

    up.append("});")

    down.append(f"Schema::dropIfExists('{table}');")

def handle_drop_table(diff):
    table = diff.attrib['Name']
    actions.append(f"drop_table_{table}")
    up.append(f"Schema::dropIfExists('{table}');")
    down.append(f"echo \"Cannot safely revert this migration: table '{table}' was dropped and data is lost.\";")
    down.append("return false;")

def handle_alter_table(diff):
    table = diff.find('Name').text
    actions.append(f"alter_{table}_table")
    unable_to_revert = False

    rename_to = diff.attrib.get('RenameTo')
    if rename_to:
        up.append(f"Schema::rename('{table}', '{rename_to}');")
        down.append(f"Schema::rename('{rename_to}', '{table}');")
        table = rename_to

    for col in diff.findall('DropColumn'):
        name = col.get('Name')
        up.append(f"Schema::table('{table}', function (Blueprint $table) {{ $table->dropColumn('{name}'); }});")
        down.append(f"echo \"Cannot safely revert this migration: column '{name}' was dropped.\";")
        unable_to_revert = True

    for col in diff.findall('AddColumn'):
        up.append(f"Schema::table('{table}', function (Blueprint $table) {{ {parse_column_element(col)}; }});")
        down.append(f"Schema::table('{table}', function (Blueprint $table) {{ $table->dropColumn('{col.get('Name')}'); }});")

    for ch in diff.findall('ChangeColumn'):
        new_col = ch.find('NewColumn')
        old_col = ch.find('OldColumn')
        up.append(f"Schema::table('{table}', function (Blueprint $table) {{ $table->renameColumn('{old_col.get('Name')}', '{new_col.get('Name')}'); }});")
        down.append(f"Schema::table('{table}', function (Blueprint $table) {{ $table->renameColumn('{new_col.get('Name')}', '{old_col.get('Name')}'); }});")

    if unable_to_revert:
        down.append("return false;")

def handle_foreign_key_inline(fk):
    name = fk.get('Name')
    from_col = fk.get('FromColumn')
    to_col = fk.get('ToColumn')
    to_table = fk.get('ToTable')
    on_delete = fk.get('OnDelete')
    on_update = fk.get('OnUpdate')

    fk_stmt = f"$table->foreign('{from_col}')->references('{to_col}')->on('{to_table}')"
    if on_delete:
        fk_stmt += f"->onDelete('{on_delete}')"
    if on_update:
        fk_stmt += f"->onUpdate('{on_update}')"
    fk_stmt += f"->name('{name}');"

    return fk_stmt

def get_filename():
    now = datetime.now()
    suffix = actions[0] if len(actions) == 1 else 'migration'
    return now.strftime(f"%Y_%m_%d_%H%M%S_{suffix}.php")

def generate_class():
    lines = [
        "<?php",
        "use Illuminate\\Database\\Migrations\\Migration;",
        "use Illuminate\\Database\\Schema\\Blueprint;",
        "use Illuminate\\Support\\Facades\\Schema;",
        "",
        f"return new class extends Migration {{",
        INDENT + "public function up(): void",
        INDENT + "{"
    ]
    for line in up:
        lines.append(INDENT * 2 + line)
    lines.append(INDENT + "}")
    lines.append("")
    lines.append(INDENT + "public function down(): void")
    lines.append(INDENT + "{")
    for line in down:
        lines.append(INDENT * 2 + line)
    lines.append(INDENT + "}")
    lines.append("};")
    return NEWLINE.join(lines)

def main():
    xml_data = sys.stdin.read()
    tree = ET.ElementTree(ET.fromstring(xml_data))
    root = tree.getroot()

    for diff in root:
        match diff.tag:
            case 'CreateTable':
                handle_create_table(diff)
            case 'DropTable':
                handle_drop_table(diff)
            case 'AlterTable':
                handle_alter_table(diff)

    os.makedirs("Laravel-Migrations", exist_ok=True)
    filename = get_filename()
    class_code = generate_class()

    with open(os.path.join("Laravel-Migrations", filename), "w", encoding="utf-8", newline='') as f:
        f.write(class_code)
    
    print(f"Migration written to Laravel-Migrations/{filename}")

if __name__ == "__main__":
    main()

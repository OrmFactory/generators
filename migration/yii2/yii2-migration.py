# This code is dedicated to the public domain under CC0 1.0.
# You may use it freely for any purpose. No warranty is provided.
# https://creativecommons.org/publicdomain/zero/1.0/

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
    if len(columns) < 2:
        return "'" + s + "'"
    return "[" + ", ".join(f"'{c.strip()}'" for c in columns) + "]"

def parse_column_element(column_element):
    name = column_element.get('Name')
    data_type = column_element.get('Type')
    nullable = column_element.get('Nullable', 'false').lower() == 'true'
    auto_increment = column_element.get('AutoIncrement', 'false').lower() == 'true'
    default = column_element.get('Default', '')
    comment = column_element.get('Comment', '')
    
    column_definition = f"$table->{data_type}('{name}')"
    
    if not nullable:
        column_definition += "->notNull()"
    
    if auto_increment:
        column_definition += "->autoIncrement()"
    
    if default:
        column_definition += f"->default('{default}')"
    
    if comment:
        column_definition += f"->comment('{comment}')"
    
    return column_definition
    
        
def handle_alter_table(diff):
    table_name = diff.find('Name').text
    table_name_down = table_name
    actions.append("alter_" + table_name + "_table")
    unable_to_revert = False

    rename_to = diff.attrib.get('RenameTo')
    if rename_to:
        up.append(f"$this->renameTable('{table_name}', '{rename_to}');")
        down.append(f"$this->renameTable('{rename_to}', '{table_name}');")
        table_name = rename_to

    # Drop primary key
    for pk in diff.findall('DropPrimaryKey'):
        name = pk.get('Name', f"pk_{table_name}")
        up.append(f"$this->dropPrimaryKey('{name}', '{table_name}');")
        
    # Drop index
    for idx in diff.findall('DropIndex'):
        name = idx.get('Name')
        up.append(f"$this->dropIndex('{name}', '{table_name}');")
        
    # Drop unique
    for uq in diff.findall('DropUnique'):
        name = uq.get('Name')
        up.append(f"$this->dropIndex('{name}', '{table_name}');")

    # Drop foreign key
    for fk in diff.findall('DropForeignKey'):
        name = fk.get('Name')
        up.append(f"$this->dropForeignKey('{name}', '{table_name}');")

    # Drop columns
    for column in diff.findall('DropColumn'):
        column_name = column.get('Name')
        up.append(f"$this->dropColumn('{table_name}', '{column_name}');")
        down.append(f"echo \"Cannot safely revert this migration: column '{column_name}' was dropped from table '{table_name}'.\";")
        unable_to_revert = True

    # Change columns
    for change_column in diff.findall('ChangeColumn'):
        new_column = change_column.find('NewColumn')
        old_column = change_column.find('OldColumn')
        old_column_name = old_column.get('Name')
        new_column_name = new_column.get('Name')
        up.append(f"$this->alterColumn('{table_name}', '{old_column_name}', {parse_column_element(new_column)});")
        down.append(f"$this->alterColumn('{table_name_down}', '{new_column_name}', {parse_column_element(old_column)});")

    # Add columns
    for column in diff.findall('AddColumn'):
        column_name = column.get('Name')
        up.append(f"$this->addColumn('{table_name}', '{column_name}', {parse_column_element(column)});")
        down.append(f"$this->dropColumn('{table_name_down}', '{column_name}');")
        
    # Add primary key
    for pk in diff.findall('AddPrimaryKey'):
        name = pk.get('Name', f"pk_{table_name}")
        columns = pk.get('Columns')
        up.append(f"$this->addPrimaryKey('{name}', '{table_name}', {parse_column_list(columns)});")
        down.append(f"$this->dropPrimaryKey('{name}', '{table_name_down}');")

    # Add index
    for idx in diff.findall('AddIndex'):
        name = idx.get('Name')
        columns = idx.get('Columns')
        up.append(f"$this->createIndex('{name}', '{table_name}', {parse_column_list(columns)});")
        down.append(f"$this->dropIndex('{name}', '{table_name_down}');")
        
    # Add unique
    for uq in diff.findall('AddUnique'):
        name = uq.get('Name')
        columns = uq.get('Columns')
        up.append(f"$this->createIndex('{name}', '{table_name}', {parse_column_list(columns)}, true);")
        down.append(f"$this->dropIndex('{name}', '{table_name_down}');")
    
    # Add foreign key
    for fk in diff.findall('AddForeignKey'):
        handle_foreign_key(table_name, fk)
        
    # Change table comment
    if 'Comment' in diff.attrib:
        new_comment = diff.attrib['Comment']
        up.append(f"$this->addCommentOnTable('{table_name}', '{new_comment}');")
        
    if unable_to_revert:
        down.append("return false;")

def handle_drop_table(diff):
    table = diff.attrib["Name"]
    up.append(f"$this->dropTable(\"{table}\");")
    actions.append("drop_table_" + table)
    down.append(f"echo \"Cannot safely revert this migration: table '{table}' was dropped and data is lost.\";")
    down.append("return false;")

def handle_foreign_key(table_name, foreign_key):
    name = foreign_key.get('Name')
    from_columns = foreign_key.get('FromColumn')
    to_columns = foreign_key.get('ToColumn')
    to_table = foreign_key.get('ToTable')
    on_delete = foreign_key.get('OnDelete', '')
    on_update = foreign_key.get('OnUpdate', '')

    lines = [f"'{table_name}'", parse_column_list(from_columns), f"'{to_table}'", parse_column_list(to_columns)]
    if on_delete and on_update:
        lines.append(f"'{on_delete}'")
        lines.append(f"'{on_update}'")

    up.append(f"$this->addForeignKey('{name}',")
    for line in lines[:-1]:
        up.append(INDENT + line + ",")
    up.append(INDENT + lines[-1] + ");")

    down.append(f"$this->dropForeignKey('{name}', '{table_name}');")

def handle_create_table(diff):
    table = diff.attrib["Name"]
    comment = diff.attrib.get("Comment")
    
    actions.append("create_" + table + "_table")
    up.append(f"$this->createTable(\"{table}\", [")
    
    column_lines = []
    for column in diff.findall('Column'):
        column_lines.append(INDENT + parse_column_element(column))
    
    # must be at least one column
    for line in column_lines[:-1]:
        up.append(line + ",")
    up.append(column_lines[-1])
    up.append("]);")
    
    # Handling primary key
    for primary_key in diff.findall('PrimaryKey'):
        columns = primary_key.get('Columns')
        name = primary_key.get('Name', f"pk_{table}")
        up.append(f"$this->addPrimaryKey('{name}', '{table}', {parse_column_list(columns)});")
    
    # Handling indexes
    for index in diff.findall('Index'):
        columns = index.get('Columns')
        name = index.get('Name')
        up.append(f"$this->createIndex('{name}', '{table}', {parse_column_list(columns)});")
    
    # Handling uniques
    for unique in diff.findall('Unique'):
        columns = unique.get('Columns')
        name = unique.get('Name')
        up.append(f"$this->createIndex('{name}', '{table}', {parse_column_list(columns)}, true);")
    
    for foreign_key in diff.findall('ForeignKey'):
        handle_foreign_key(table, foreign_key)
        
    down.append(f"$this->dropTable(\"{table}\");")

def get_class_name():
    name = actions[0]
    if len(actions) > 1:
        name = "migrations"
        
    formatted_datetime = datetime.now().strftime("%y%m%d_%H%M%S")
    return "m" + formatted_datetime + "_" + name

def get_class():
    class_lines = []
    class_lines.append("class " + get_class_name() + " extends Migration")
    class_lines.append("{")
    class_lines.append(INDENT + "public function safeUp()")
    class_lines.append(INDENT + "{")
    for line_up in up:
        class_lines.append(INDENT*2 + line_up)
    class_lines.append(INDENT + "}")
    class_lines.append("")
    class_lines.append(INDENT + "public function safeDown()")
    class_lines.append(INDENT + "{")
    for line_down in down:
        class_lines.append(INDENT*2 + line_down)
    class_lines.append(INDENT + "}")
    class_lines.append("}")
    return NEWLINE.join(class_lines)

def main():
    xml_data = sys.stdin.read()
    
    #uncomment for debug purposes
    #with open("migration_model.xml", "w", encoding="utf-8") as f:
    #    f.write(xml_data)
    
    tree = ET.ElementTree(ET.fromstring(xml_data))
    root = tree.getroot()
    
    for diff in root:
        match diff.tag:
            case "CreateTable":
                handle_create_table(diff)
            case "DropTable":
                handle_drop_table(diff)
            case "AlterTable":
                handle_alter_table(diff)
    
    filename = get_class_name() + ".php"
    class_text = get_class()
    
    print(class_text)
    
    directory = "Yii2-Migrations"
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, filename), "w", encoding="utf-8", newline='') as f:
        f.write(class_text)

if __name__ == "__main__":
    main()

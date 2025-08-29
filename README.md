# OrmFactory Generators

A collection of entity and migration generators for [OrmFactory](https://ormfactory.com).
All generators are distributed under the [MIT license](LICENSE).
## Repository Structure

```
/entities/<orm>/
generator.py # entity/model generator script

/migrations/<orm>/
<orm-database>.py # migration generator script

/icons/
<orm>.svg # ORM and database icons

/entity-index.json
entity generators index

/migration-index.json
migration generators index

/generator-index.schema.json
JSON Schema for index validation
```

- **entity-index.json** — list of entity (model) generators.
- **migration-index.json** — list of migration generators.
- **icons/** — SVG icons for ORMs and databases.
- **generator-index.schema.json** — schema for automatic index validation.

## Index Format

Example `entity-index.json`:

```json
{
  "generators": [
    {
      "name": "Hibernate Entity Generator",
      "orm": "hibernate",
      "databases": ["postgresql", "mysql"],
      "version": "1.0.0",
      "path": "generators/entities/hibernate/generator.py",
      "description": "JPA entities for Hibernate.",
      "icons": ["icons/hibernate.svg", "icons/postgresql.svg"]
    }
  ]
}
```

Fields:

- name - generator name
- orm - target ORM
- databases - supported databases
- version - generator version
- path - relative path to the script
- description - short description
- icons - list of icon paths (can be empty)

## Index Validation

On every push and PR, the JSON indexes are automatically validated against generator-`index.schema.json`

## Contributing Your Own Generator

You can add your own generator scripts to this repository.
Each generator is a standalone Python script and must be described in the appropriate index file.

### Steps to add a new generator

1. **Place your script**
   - Put your Python file under the corresponding directory:
     - `entity-generators/` — for entity (model) code generators.
     - `migration-generators/` — for migration generators.

2. **Add metadata**
   - Update the correct index file (`entity-generators/index.json` or `migration-generators/index.json`).
   - **Fields explained**:
     - `name` — Human-readable name of the generator.
     - `description` — Short explanation of what it does.
     - `databases` — Array of supported databases (PostgreSQL, MySQL, SQL Server, Oracle).
     - `script` — Relative path to the script inside the repo.
     - `icons` — (Optional) Array of relative paths to SVG icons.

3. **Open a Pull Request**
   - Describe what your generator does and provide examples if possible.
   - The CI will automatically check if the JSON indexes are still valid.

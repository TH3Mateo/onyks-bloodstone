import re
import base64
import json
from typing import Optional, Dict, Any
import subprocess
import xml.etree.ElementTree as ET
import pyaltiumlib
import io
import os
from sqlalchemy import text

def repositoryGetFolderList(url, path):
    if path:
        full_url = f"{url.rstrip('/')}/{path.strip('/')}"
    else:
        full_url = url
    command = ["svn", "list", "--xml", "--non-interactive", full_url]

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        root = ET.fromstring(result.stdout)
        items = []
        for entry in root.findall(".//entry"):
            kind = entry.get("kind")
            nameEntry = entry.find("name")
            name = nameEntry.text if nameEntry is not None else "unknown"
            _, ext = os.path.splitext(name)
            if ext.lower() == '.schlib':
                kind = 'schlib'
            elif ext.lower() == '.pcblib':
                kind = 'pcblib'
            items.append({
                "name":name,
                "type": kind
            })
        return items
    except Exception as e:
        return e

def repositoryGetPCBFileContent(url, path):
    if path:
        full_url = f"{url.rstrip('/')}/{path.strip('/')}"
    else:
        full_url = url
    command = ["svn", "cat", full_url]

    try:
        result = subprocess.run(command, capture_output=True, check=True)
    except Exception as e:
        print(f"Unexpected execution error: {e}")
        raise e
    libfile_obj = io.BytesIO(result.stdout)

    schlib_pcblib_name = str(path).split('/')[-1].lower()
    elements = []

    if schlib_pcblib_name.endswith('.schlib'):
        schlib_file = pyaltiumlib.read(schlib_pcblib_name, libfile_obj)
        symbols = schlib_file.list_parts()
        elements = [{"name": i, "type": 'symbol'} for i in symbols]
    elif schlib_pcblib_name.endswith('.pcblib'):
        pcblib_file = pyaltiumlib.read(schlib_pcblib_name, libfile_obj)
        footprints = pcblib_file.list_parts()
        elements = [{"name": i, "type": 'footprint'} for i in footprints]
    return elements

def repositoryGetRevision(url):
    command = ["svn", "info", "--show-item", "revision", "--non-interactive", url]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    return int(result.stdout.strip())

def repositoryComputeStatistics(url):
    """Counts SchLib/PcbLib files in the whole repository and the symbols/footprints
    inside them. Slow (every library file is downloaded and parsed), so callers cache
    the result per SVN revision. A file that fails to parse still counts as a file."""
    command = ["svn", "list", "-R", "--xml", "--non-interactive", url]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    root = ET.fromstring(result.stdout)

    statistics = {"symbols": 0, "footprints": 0, "schLibFiles": 0, "pcbLibFiles": 0, "unreadableFiles": 0}
    for entry in root.findall(".//entry"):
        if entry.get("kind") != "file":
            continue
        path = entry.findtext("name") or ""
        extension = os.path.splitext(path)[1].lower()
        if extension not in (".schlib", ".pcblib"):
            continue

        statistics["schLibFiles" if extension == ".schlib" else "pcbLibFiles"] += 1
        try:
            parts = repositoryGetPCBFileContent(url, path)
        except Exception:
            statistics["unreadableFiles"] += 1
            continue
        statistics["symbols" if extension == ".schlib" else "footprints"] += len(parts)

    return statistics

def safeViewName(table_id, table_name):
    safe_table_name = table_name.lower().replace(' ', '_').replace('-', '_')
    return f"table_{table_id}_{safe_table_name}"

async def getCategoryViewMap(db_connection):
    """Returns {category_name: view_name} for every category table, using the
    same naming convention as dbCreateOrUpdateElementViews."""
    result_tables = await db_connection.execute(text("SELECT DISTINCT id, name FROM private.tables"))
    tables = result_tables.fetchall()
    return {table_row[1]: safeViewName(table_row[0], table_row[1]) for table_row in tables}

def supplierColumnNames(suppliers):
    """Maps (id, name) pairs to the name of each supplier's code column in the CAD views,
    as {id: column}. The column is what users read in Altium's and KiCad's browsers, so
    it carries the supplier's name only ("supplier_lcsc"), not its internal id.

    Names are reduced to a plain lowercase identifier (Polish letters transliterated,
    anything else becomes "_"), which also keeps names like "Farnell (UK)" from breaking
    the generated SQL. Two suppliers that reduce to the same identifier are told apart
    by appending the id to the later one. The "supplier_" prefix stays: clients such as
    Chalcedon use it to recognise supplier columns. Clients should take the name from the
    API's `columnName` instead of recomputing it."""
    import unicodedata
    columns, used = {}, set()
    for supplier_id, name in sorted(suppliers):
        ascii_name = unicodedata.normalize("NFKD", name.replace("ł", "l").replace("Ł", "L"))
        ascii_name = ascii_name.encode("ascii", "ignore").decode()
        slug = re.sub(r"[^a-z0-9]+", "_", ascii_name.lower()).strip("_")
        column = f"supplier_{slug}" if slug else f"supplier_{supplier_id}"
        if column in used:
            column = f"{column}_{supplier_id}"
        used.add(column)
        columns[supplier_id] = column
    return columns

async def getSupplierColumnMap(db_connection):
    """Returns {supplier_name: column_name} for every supplier's per-table code column."""
    result_suppliers = await db_connection.execute(text("SELECT id, name FROM private.suppliers"))
    suppliers = result_suppliers.fetchall()
    by_id = supplierColumnNames(suppliers)
    return {supplier_name: by_id[supplier_id] for supplier_id, supplier_name in suppliers}

ALTIUM_SCHEMA = "altium"
KICAD_SCHEMA = "kicad"

TOOL_SCHEMAS = (ALTIUM_SCHEMA, KICAD_SCHEMA)

# Group roles (NOLOGIN). They hold the grants; real people are login roles that are
# granted membership in exactly one of them. Nothing here has a password, so no
# per-person credential ever has to live in the server's .env.
#
# The tool axis (altium/kicad) controls which schema is visible and is enforced by
# Postgres. The users/editors axis mirrors private.users.rank and is enforced by the
# BACKEND, not by these grants -- see dbEnsureUserRoleSystem() for why.
TOOL_GROUPS = {
    ALTIUM_SCHEMA: {"users": "altium_users", "editors": "altium_editors"},
    KICAD_SCHEMA: {"users": "kicad_users", "editors": "kicad_editors"},
}


def allToolGroups():
    return [name for groups in TOOL_GROUPS.values() for name in groups.values()]


def _quotedAlias(alias):
    """Column aliases are mixed case on purpose (Altium and KiCad match them verbatim),
    so they must stay double-quoted in the generated SQL."""
    return '"' + alias.replace('"', '""') + '"'


def _datasheetUrlExpression(alias):
    """CASE expression building the public URL of the element's main datasheet PDF."""
    public_files_url = os.getenv("PUBLIC_FILES_URL", "/files/").replace("'", "''")
    return (
        f"CASE WHEN datasheet THEN '{public_files_url}' || uuid::text || '.pdf' "
        f"ELSE NULL END AS {_quotedAlias(alias)}"
    )


def _libraryRefExpression(reference_column, path_column, alias):
    """CASE expression producing KiCad's "LibraryNickname:Name" format, where the
    nickname is the SchLib/PcbLib file name without its directory and extension."""
    nickname = rf"regexp_replace(regexp_replace({path_column}, '.*/', ''), '\.[^.]+$', '')"
    return (
        f"CASE WHEN {reference_column} IS NOT NULL AND {reference_column} <> '' "
        f"AND {path_column} IS NOT NULL AND {path_column} <> '' "
        f"THEN {nickname} || ':' || {reference_column} "
        f"ELSE NULL END AS {_quotedAlias(alias)}"
    )


async def dbCreateOrUpdateElementViews(db_connection):

    table_to_view_map = await getCategoryViewMap(db_connection)
    expected_views = set(table_to_view_map.values())

    await db_connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {ALTIUM_SCHEMA}"))
    await db_connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {KICAD_SCHEMA}"))

    # Clean up the previous single-schema layout entirely, plus any per-schema view
    # whose category no longer exists.
    result_existing_views = await db_connection.execute(text(f"""
        SELECT table_schema, table_name
        FROM information_schema.views
        WHERE table_schema IN ('public', '{ALTIUM_SCHEMA}', '{KICAD_SCHEMA}')
          AND table_name LIKE 'table\\_%'
    """))
    for view_schema, view_name in result_existing_views.fetchall():
        if view_schema == 'public' or view_name not in expected_views:
            await db_connection.execute(text(f"DROP VIEW IF EXISTS {view_schema}.{view_name} CASCADE"))

    supplier_column_map = await getSupplierColumnMap(db_connection)
    result_suppliers = await db_connection.execute(text("SELECT id, name FROM private.suppliers"))

    supplier_columns = ""
    for supplier_id, supplier_name in result_suppliers.fetchall():
        column_name = supplier_column_map[supplier_name]
        supplier_columns += f",\n            (suppliers->>'{supplier_id}')::text AS {column_name}"

    # Altium consumes the raw reference/path pairs and maps them onto its own
    # [Library Ref] / [Footprint Path N] component parameters.
    altium_columns = ",\n            ".join([
        "uuid",
        "part_name",
        "manufacturer",
        "description",
        "value",
        "availability",
        "library_ref",
        "library_path",
        "footprint_reference_1",
        "footprint_path_1",
        "footprint_reference_2",
        "footprint_path_2",
        "footprint_reference_3",
        "footprint_path_3",
        "created_at",
        _datasheetUrlExpression("HelpURL"),
    ])

    # KiCad instead needs a single pre-joined "Nickname:Name" string per symbol/footprint,
    # and recognises a field literally named "Datasheet" as the clickable link.
    kicad_columns = ",\n            ".join([
        "uuid",
        "part_name",
        "manufacturer",
        "description",
        "value",
        "availability",
        "created_at",
        _datasheetUrlExpression("Datasheet"),
        _libraryRefExpression("library_ref", "library_path", "Symbols"),
        _libraryRefExpression("footprint_reference_1", "footprint_path_1", "Footprints"),
    ])

    for table_name, view_name in table_to_view_map.items():

        safe_table_name_query = table_name.replace("'", "''")

        for schema, columns in ((ALTIUM_SCHEMA, altium_columns), (KICAD_SCHEMA, kicad_columns)):

            await db_connection.execute(text(f"DROP VIEW IF EXISTS {schema}.{view_name} CASCADE"))

            await db_connection.execute(text(f"""
            CREATE VIEW {schema}.{view_name} AS
            SELECT
            {columns}{supplier_columns}
            FROM private.elements
            WHERE "table" = '{safe_table_name_query}'
            ORDER BY created_at DESC
            """))

    await dbEnsureToolRoles(db_connection)

    library_definitions = await getLibraryDefinitions(db_connection, table_to_view_map)

    await db_connection.commit()

    await syncLibraryDatabases(library_definitions)

    return {"status": "success", "message": "Views updated and old ones cleaned up successfully"}


# Each CAD tool connects to its OWN database, which contains nothing but one view per
# component category, named exactly like the category.
#
# This cannot be achieved with privileges inside appdb: the ODBC driver lists tables
# straight from pg_class, which every role can read, so Altium showed users, tables,
# elements and the other tool's views even to an account with no access to them. Only a
# separate database has a separate catalog. Foreign tables are no answer either -- the
# driver lists those too -- so each view reads its rows through a SECURITY DEFINER
# function (functions are not listed) that fetches them from appdb over dblink.
LIBRARY_DATABASES = {ALTIUM_SCHEMA: "altium_lib", KICAD_SCHEMA: "kicad_lib"}

# Internal LOGIN roles, used only by that dblink connection. They have no password, so
# they cannot sign in from the network (pg_hba requires scram-sha-256 there); the
# connection is made over the database container's local socket.
LIBRARY_READERS = {ALTIUM_SCHEMA: "altium_lib_reader", KICAD_SCHEMA: "kicad_lib_reader"}

LIBRARY_INTERNAL_SCHEMA = "lib_internal"


def _quoteIdentifier(name):
    return '"' + name.replace('"', '""') + '"'


def _quoteLiteral(value):
    return "'" + value.replace("'", "''") + "'"


def _databaseUrl(database):
    from sqlalchemy.engine import URL
    return URL.create(
        "postgresql+asyncpg",
        username=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host="database",
        port=5432,
        database=database,
    )


async def dbEnsureToolRoles(db_connection):
    """Creates the four NOLOGIN group roles and the two internal reader roles, and
    (re-)applies grants inside appdb. Must run after every view rebuild, because DROP
    VIEW discards table grants.

    Personal accounts (members of the groups) get NOTHING in appdb -- not even CONNECT.
    They reach their data only through their tool's library database. Inside appdb the
    per-tool source views are readable solely by that tool's reader role.

    Both groups of a given tool get IDENTICAL grants on purpose. Everything reachable
    over ODBC is read-only, and category creation happens through the web app (which
    connects as appuser), so there is no action an "editor" could perform through a
    database connection that a "user" could not. The distinction lives in
    private.users.rank and has to be enforced by the web application."""

    appdb = os.getenv("POSTGRES_DB")

    for group_name in allToolGroups():
        await db_connection.execute(text(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{group_name}') THEN
                    CREATE ROLE {group_name} NOLOGIN;
                END IF;
            END
            $$;
        """))
        # Leftovers from when the groups read appdb directly.
        for schema in TOOL_SCHEMAS + ("private", "public"):
            await db_connection.execute(text(f"REVOKE ALL ON SCHEMA {schema} FROM {group_name}"))
            await db_connection.execute(text(f"REVOKE ALL ON ALL TABLES IN SCHEMA {schema} FROM {group_name}"))

    for schema, reader in LIBRARY_READERS.items():
        await db_connection.execute(text(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{reader}') THEN
                    CREATE ROLE {reader} LOGIN;
                END IF;
            END
            $$;
        """))
        await db_connection.execute(text(f"ALTER ROLE {reader} WITH LOGIN PASSWORD NULL"))
        await db_connection.execute(text(f'GRANT CONNECT ON DATABASE "{appdb}" TO {reader}'))
        await db_connection.execute(text(f"GRANT USAGE ON SCHEMA {schema} TO {reader}"))
        await db_connection.execute(text(f"GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO {reader}"))

        for other_schema in TOOL_SCHEMAS:
            if other_schema != schema:
                await db_connection.execute(text(f"REVOKE ALL ON SCHEMA {other_schema} FROM {reader}"))
                await db_connection.execute(text(f"REVOKE ALL ON ALL TABLES IN SCHEMA {other_schema} FROM {reader}"))
        await db_connection.execute(text(f"REVOKE ALL ON SCHEMA private FROM {reader}"))

    # By default every role may connect to every database; personal accounts must not
    # be able to open appdb and browse its catalog.
    await db_connection.execute(text(f'REVOKE CONNECT, TEMPORARY ON DATABASE "{appdb}" FROM PUBLIC'))

    return allToolGroups()


async def getLibraryDefinitions(db_connection, table_to_view_map):
    """Reads, from appdb, the column list and types of every per-tool source view, as
    {schema: [(category_name, source_view_name, [(column, sql_type), ...]), ...]}."""

    definitions = {}
    for schema in TOOL_SCHEMAS:
        definitions[schema] = []
        for category_name, view_name in table_to_view_map.items():
            result = await db_connection.execute(text("""
                SELECT a.attname, format_type(a.atttypid, a.atttypmod)
                FROM pg_attribute a
                JOIN pg_class c ON c.oid = a.attrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = :schema AND c.relname = :view
                  AND a.attnum > 0 AND NOT a.attisdropped
                ORDER BY a.attnum
            """), {"schema": schema, "view": view_name})
            columns = [(row[0], row[1]) for row in result.fetchall()]
            definitions[schema].append((category_name, view_name, columns))
    return definitions


async def syncLibraryDatabases(definitions):
    """Creates altium_lib / kicad_lib if missing and rebuilds their contents so that the
    only relations in each are the category views. Each rebuild runs in one transaction,
    so a CAD tool querying at that moment sees either the old or the new set, never a
    half-built one."""

    from sqlalchemy.ext.asyncio import create_async_engine

    appdb = os.getenv("POSTGRES_DB")
    groups_by_tool = {schema: list(groups.values()) for schema, groups in TOOL_GROUPS.items()}

    # CREATE DATABASE cannot run inside a transaction block.
    admin_engine = create_async_engine(_databaseUrl(appdb), isolation_level="AUTOCOMMIT")
    try:
        async with admin_engine.connect() as connection:
            for schema, database in LIBRARY_DATABASES.items():
                exists = await connection.scalar(
                    text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": database})
                if not exists:
                    await connection.exec_driver_sql(f'CREATE DATABASE "{database}"')
                await connection.exec_driver_sql(f'REVOKE ALL ON DATABASE "{database}" FROM PUBLIC')
                for group_name in groups_by_tool[schema]:
                    await connection.exec_driver_sql(f'GRANT CONNECT ON DATABASE "{database}" TO {group_name}')
    finally:
        await admin_engine.dispose()

    for schema, database in LIBRARY_DATABASES.items():
        groups = ", ".join(groups_by_tool[schema])
        internal = LIBRARY_INTERNAL_SCHEMA
        connection_string = f"dbname={appdb} user={LIBRARY_READERS[schema]}"

        engine = create_async_engine(_databaseUrl(database))
        try:
            async with engine.begin() as connection:
                run = connection.exec_driver_sql

                await run(f"CREATE SCHEMA IF NOT EXISTS {internal}")
                await run(f"CREATE EXTENSION IF NOT EXISTS dblink SCHEMA {internal}")
                await run(f"REVOKE ALL ON SCHEMA {internal} FROM PUBLIC")
                await run(f"REVOKE ALL ON ALL FUNCTIONS IN SCHEMA {internal} FROM PUBLIC")
                await run(f"GRANT USAGE ON SCHEMA {internal} TO {groups}")
                await run("REVOKE ALL ON SCHEMA public FROM PUBLIC")
                await run(f"GRANT USAGE ON SCHEMA public TO {groups}")

                # Start from an empty catalog: every relation in public is ours to rebuild.
                existing_views = (await run(
                    "SELECT format('%I.%I', schemaname, viewname) FROM pg_views WHERE schemaname = 'public'"
                )).fetchall()
                for (qualified_name,) in existing_views:
                    await run(f"DROP VIEW IF EXISTS {qualified_name} CASCADE")

                existing_functions = (await run(f"""
                    SELECT p.oid::regprocedure::text FROM pg_proc p
                    JOIN pg_namespace n ON n.oid = p.pronamespace
                    WHERE n.nspname = '{internal}' AND p.proname LIKE 'fetch\\_%'
                """)).fetchall()
                for (signature,) in existing_functions:
                    await run(f"DROP FUNCTION IF EXISTS {signature} CASCADE")

                for category_name, source_view, columns in definitions[schema]:
                    if not columns:
                        continue

                    function_name = f"{internal}.fetch_{source_view}"
                    column_definitions = ", ".join(f"{_quoteIdentifier(c)} {t}" for c, t in columns)
                    column_list = ", ".join(_quoteIdentifier(c) for c, _ in columns)
                    remote_query = f"SELECT {column_list} FROM {schema}.{source_view}"

                    await run(f"""
                        CREATE FUNCTION {function_name}()
                        RETURNS TABLE({column_definitions})
                        LANGUAGE sql STABLE SECURITY DEFINER
                        SET search_path = {internal}, pg_temp
                        AS $fetch$
                            SELECT * FROM {internal}.dblink({_quoteLiteral(connection_string)},
                                                            {_quoteLiteral(remote_query)})
                                AS source({column_definitions})
                        $fetch$
                    """)
                    await run(f"REVOKE ALL ON FUNCTION {function_name}() FROM PUBLIC")
                    await run(f"GRANT EXECUTE ON FUNCTION {function_name}() TO {groups}")

                    view_name = f"public.{_quoteIdentifier(category_name)}"
                    await run(f"CREATE VIEW {view_name} AS SELECT * FROM {function_name}()")
                    await run(f"GRANT SELECT ON {view_name} TO {groups}")
        finally:
            await engine.dispose()


async def dbEnsureUserRoleSystem(db_connection):
    """Installs the SQL layer that keeps private.users and real Postgres login roles in
    step, so one account = one login/password for the app, for SVN and for ODBC.

    Why creation goes through a function instead of a plain INSERT trigger: the app and
    SVN authenticate against a bcrypt hash stored in private.users.password, while a
    Postgres role stores a SCRAM verifier. Neither can be derived from the other, so both
    can only be set at the single moment the plaintext password exists. A trigger on
    INSERT only ever sees the already-hashed value and therefore cannot create a role
    with a matching password.

    Everything that does NOT need the plaintext (dropping a role, moving someone between
    groups) is automatic, via triggers."""

    await db_connection.execute(text("""
        ALTER TABLE private.users
        ADD COLUMN IF NOT EXISTS tool VARCHAR(16) NOT NULL DEFAULT 'altium'
    """))

    await db_connection.execute(text("""
        ALTER TABLE private.users DROP CONSTRAINT IF EXISTS users_tool_check
    """))
    await db_connection.execute(text("""
        ALTER TABLE private.users
        ADD CONSTRAINT users_tool_check CHECK (tool IN ('altium', 'kicad'))
    """))

    # Earlier versions pinned each account's search_path to its tool schema in appdb. That
    # setting applies in every database, so in altium_lib/kicad_lib it would hide the
    # public schema holding the category views. Tools now use their own database instead.
    await db_connection.execute(text("""
        DO $$
        DECLARE
            v_login text;
        BEGIN
            FOR v_login IN
                SELECT u.login FROM private.users u JOIN pg_roles r ON r.rolname = u.login
            LOOP
                EXECUTE format('ALTER ROLE %I RESET search_path', v_login);
            END LOOP;
        END
        $$;
    """))

    # rank is viewer/editor/admin; only viewer is a plain "user", the other two are editors.
    await db_connection.execute(text("""
        CREATE OR REPLACE FUNCTION private.user_group_name(p_tool text, p_rank text)
        RETURNS text
        LANGUAGE sql IMMUTABLE AS $$
            SELECT p_tool || CASE WHEN p_rank = 'viewer' THEN '_users' ELSE '_editors' END;
        $$;
    """))

    # Apache's mod_authn_dbd (which authenticates SVN) accepts a bcrypt hash only with the
    # $2y$ prefix and rejects pgcrypto's native $2a$, even though the two are the same
    # algorithm and differ only in that marker. Verified empirically: the identical
    # password authenticates as $2y$ and fails as $2a$.
    #
    # So hashes are STORED as $2y$ for Apache, and pgcrypto -- which only understands
    # $2a$ -- gets the prefix normalised back before it verifies anything.
    await db_connection.execute(text("""
        CREATE OR REPLACE FUNCTION private.user_password_hash(p_password text)
        RETURNS text
        LANGUAGE sql
        SET search_path = private, public, pg_temp AS $$
            SELECT replace(crypt(p_password, gen_salt('bf')), '$2a$', '$2y$');
        $$;
    """))

    await db_connection.execute(text("""
        CREATE OR REPLACE FUNCTION private.user_check_password(p_login text, p_password text)
        RETURNS boolean
        LANGUAGE sql
        SET search_path = private, public, pg_temp AS $$
            SELECT crypt(p_password, replace(password, '$2y$', '$2a$'))
                 = replace(password, '$2y$', '$2a$')
            FROM private.users WHERE login = p_login;
        $$;
    """))

    # A login becomes a Postgres identifier, so it is whitelisted rather than escaped.
    await db_connection.execute(text(r"""
        CREATE OR REPLACE FUNCTION private.user_assert_valid_login(p_login text)
        RETURNS void
        LANGUAGE plpgsql AS $$
        BEGIN
            IF p_login !~ '^[a-z][a-z0-9_]{2,62}$' THEN
                RAISE EXCEPTION 'Invalid login %: use 3-63 chars, lowercase letters/digits/underscore, starting with a letter', p_login;
            END IF;
        END
        $$;
    """))

    await db_connection.execute(text("""
        CREATE OR REPLACE FUNCTION private.user_create(
            p_login text,
            p_password text,
            p_email text,
            p_rank public.user_rank DEFAULT 'viewer',
            p_tool text DEFAULT 'altium')
        RETURNS void
        LANGUAGE plpgsql
        SET search_path = private, public, pg_temp AS $$
        DECLARE
            v_group text;
        BEGIN
            PERFORM private.user_assert_valid_login(p_login);

            IF p_tool NOT IN ('altium', 'kicad') THEN
                RAISE EXCEPTION 'Invalid tool %: expected altium or kicad', p_tool;
            END IF;

            IF EXISTS (SELECT FROM pg_roles WHERE rolname = p_login) THEN
                RAISE EXCEPTION 'A database role named % already exists', p_login;
            END IF;

            INSERT INTO private.users (login, password, email, rank, tool)
            VALUES (p_login, private.user_password_hash(p_password), p_email, p_rank, p_tool);

            v_group := private.user_group_name(p_tool, p_rank::text);

            EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', p_login, p_password);
            EXECUTE format('GRANT %I TO %I', v_group, p_login);
        END
        $$;
    """))

    await db_connection.execute(text("""
        CREATE OR REPLACE FUNCTION private.user_set_password(p_login text, p_password text)
        RETURNS void
        LANGUAGE plpgsql
        SET search_path = private, public, pg_temp AS $$
        BEGIN
            PERFORM private.user_assert_valid_login(p_login);

            UPDATE private.users
            SET password = private.user_password_hash(p_password)
            WHERE login = p_login;

            IF NOT FOUND THEN
                RAISE EXCEPTION 'No application user named %', p_login;
            END IF;

            IF EXISTS (SELECT FROM pg_roles WHERE rolname = p_login) THEN
                EXECUTE format('ALTER ROLE %I WITH LOGIN PASSWORD %L', p_login, p_password);
            ELSE
                EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', p_login, p_password);
                EXECUTE format('GRANT %I TO %I', private.user_group_name(
                    (SELECT tool FROM private.users WHERE login = p_login),
                    (SELECT rank::text FROM private.users WHERE login = p_login)), p_login);
            END IF;
        END
        $$;
    """))

    # Removing an account needs no password, so it is fully automatic.
    await db_connection.execute(text("""
        CREATE OR REPLACE FUNCTION private.user_drop_role()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = private, public, pg_temp AS $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = OLD.login) THEN
                EXECUTE format('DROP OWNED BY %I', OLD.login);
                EXECUTE format('DROP ROLE %I', OLD.login);
            END IF;
            RETURN OLD;
        END
        $$;
    """))

    # Changing someone's rank or tool only moves group membership, so that is automatic too.
    await db_connection.execute(text("""
        CREATE OR REPLACE FUNCTION private.user_sync_groups()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = private, public, pg_temp AS $$
        DECLARE
            v_group text;
            v_old_group text;
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = NEW.login) THEN
                RETURN NEW;
            END IF;

            v_old_group := private.user_group_name(OLD.tool, OLD.rank::text);
            v_group := private.user_group_name(NEW.tool, NEW.rank::text);

            IF v_old_group IS DISTINCT FROM v_group THEN
                EXECUTE format('REVOKE %I FROM %I', v_old_group, NEW.login);
                EXECUTE format('GRANT %I TO %I', v_group, NEW.login);
            END IF;

            RETURN NEW;
        END
        $$;
    """))

    await db_connection.execute(text("DROP TRIGGER IF EXISTS users_drop_role ON private.users"))
    await db_connection.execute(text("""
        CREATE TRIGGER users_drop_role
        AFTER DELETE ON private.users
        FOR EACH ROW EXECUTE FUNCTION private.user_drop_role();
    """))

    await db_connection.execute(text("DROP TRIGGER IF EXISTS users_sync_groups ON private.users"))
    await db_connection.execute(text("""
        CREATE TRIGGER users_sync_groups
        AFTER UPDATE OF rank, tool ON private.users
        FOR EACH ROW EXECUTE FUNCTION private.user_sync_groups();
    """))


def generateAltiumDbLib(table_to_view_map, supplier_columns_map):
    """Builds an Altium .DbLib (INI-style) file as text, with a blank password template
    connection string, mapping every category to Altium's special component parameter
    names (PartNumber, HelpUrl, [Library Ref], etc).

    The ODBC data source must point at the altium_lib database, where every category is
    a view named exactly like the category and nothing else exists. Tables are referenced
    without a schema, so Altium lists them as "fpga" rather than "public.fpga"."""

    lines = []
    lines.append("[OutputDatabaseLinkFile]")
    lines.append("Version=1.1")
    lines.append("[DatabaseLinks]")
    lines.append(
        # User ID/Password stay blank: each person signs in with their own account,
        # which is also their application and SVN login.
        "ConnectionString=Provider=MSDASQL.1;Persist Security Info=True;"
        "User ID=;Password=;Data Source=onyks_bloodstone;Mode=Read"
    )
    lines.append("AddMode=3")
    lines.append("RemoveMode=1")
    lines.append("UpdateMode=2")
    lines.append("ViewMode=0")
    lines.append('LeftQuote="')
    lines.append('RightQuote="')
    lines.append("QuoteTableNames=1")
    lines.append("UseTableSchemaName=0")
    lines.append("DefaultColumnType=VARCHAR(255)")
    lines.append("LibraryDatabaseType=")
    lines.append("LibraryDatabasePath=")
    lines.append("DatabasePathRelative=0")
    lines.append("TopPanelCollapsed=0")
    lines.append("LibrarySearchPath=")
    lines.append("OrcadMultiValueDelimiter=,")
    lines.append("SearchSubDirectories=0")
    lines.append("SchemaName=public")

    table_names = list(table_to_view_map.keys())
    lines.append(f"LastFocusedTable={table_names[0]}" if table_names else "LastFocusedTable=")

    for index, table_name in enumerate(table_names, start=1):
        lines.append(f"[Table{index}]")
        lines.append("SchemaName=public")
        lines.append(f"TableName={table_name}")
        lines.append("Enabled=True")
        lines.append("UserWhere=0")
        lines.append("UserWhereText=")

    base_fields = [
        ("part_name", 0, "PartNumber"),
        ("HelpURL", 1, "HelpUrl"),
        ("description", 1, "[Description]"),
        ("value", 1, "Value"),
        ("library_ref", 1, "[Library Ref]"),
        ("library_path", 1, "[Library Path]"),
        ("footprint_reference_1", 1, "[Footprint Ref]"),
        ("footprint_path_1", 1, "[Footprint Path]"),
        ("footprint_reference_2", 1, "[Footprint Ref 2]"),
        ("footprint_path_2", 1, "[Footprint Path 2]"),
        ("footprint_reference_3", 1, "[Footprint Ref 3]"),
        ("footprint_path_3", 1, "[Footprint Path 3]"),
    ]
    for supplier_name, column_name in supplier_columns_map.items():
        base_fields.append((column_name, 1, f"[{supplier_name}]"))

    field_map_number = 1
    for table_name in table_names:
        for column_name, field_type, parameter_name in base_fields:
            lines.append(f"[FieldMap{field_map_number}]")
            lines.append(
                f"Options=FieldName={table_name}.{column_name}"
                f"|TableNameOnly={table_name}"
                f"|FieldNameOnly={column_name}"
                f"|FieldType={field_type}"
                f"|ParameterName={parameter_name}"
                "|VisibleOnAdd=False|AddMode=0|RemoveMode=0|UpdateMode=0"
            )
            field_map_number += 1

    return "\n".join(lines) + "\n"


def generateKicadDbl(table_to_view_map, supplier_columns_map, host, port, database):
    """Builds a KiCad .kicad_dbl (JSON) file, with a blank password template ODBC
    connection string. Uses the "Symbols"/"Footprints" computed view columns
    (LibraryNickname:Name format) and a "Datasheet" column, which KiCad recognizes by
    name as the clickable datasheet link.

    `database` must be kicad_lib, where every category is a view in the public schema
    named exactly like the category. That matters because KiCad wraps the whole table
    name in a single pair of quotes ("SELECT ... FROM \"name\""), so a schema-qualified
    name could not work anyway."""

    base_fields = [
        {"column": "part_name", "name": "Part Name", "visible_on_add": True, "visible_in_chooser": True, "show_name": False},
        {"column": "manufacturer", "name": "Manufacturer", "visible_on_add": False, "visible_in_chooser": True, "show_name": True},
        {"column": "value", "name": "Value", "visible_on_add": True, "visible_in_chooser": True, "show_name": False},
        {"column": "availability", "name": "Availability", "visible_on_add": False, "visible_in_chooser": False, "show_name": True},
        {"column": "Datasheet", "name": "Datasheet", "visible_on_add": False, "visible_in_chooser": False, "show_name": False},
    ]
    for supplier_name, column_name in supplier_columns_map.items():
        base_fields.append({
            "column": column_name, "name": supplier_name,
            "visible_on_add": False, "visible_in_chooser": False, "show_name": True
        })

    libraries = []
    for category_name, view_name in table_to_view_map.items():
        libraries.append({
            "name": category_name,
            "table": category_name,
            "key": "uuid",
            "symbols": "Symbols",
            "footprints": "Footprints",
            "properties": {"description": "description"},
            "fields": [dict(field) for field in base_fields]
        })

    return {
        "meta": {"version": 1, "filename": "onyks_bloodstone.kicad_dbl"},
        "name": "Onyks Bloodstone",
        "description": "Onyks Bloodstone PCB component database",
        "source": {
            "type": "odbc",
            "dsn": "",
            # Filled in per person: same credentials as the app and SVN.
            "username": "",
            "password": "",
            "timeout_seconds": 2,
            "connection_string": f"Driver={{PostgreSQL Unicode}};Server={host};Port={port};Database={database};"
        },
        "cache": {"max_age": 60, "max_size": 256},
        "globally_unique_keys": True,
        "libraries": libraries
    }
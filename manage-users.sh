#!/bin/bash
# Account management for Onyks Bloodstone.
#
# One account = one login and password in three places:
#   - PostgreSQL login role  (ODBC access from Altium / KiCad)
#   - SVN                    (Apache authenticates against private.users)
#   - the web application    (NOT YET -- the web app currently has no login at all)
#
# Passwords are read from the terminal, never passed as arguments, so they do not
# end up in shell history or in the output of `ps`.

set -euo pipefail

cd "$(dirname "$0")"

ENV_FILE="${CONFIG_FILE:-.env}"
COMPOSE=(docker compose --env-file "$ENV_FILE")

# shellcheck disable=SC1090
set -a && . "./$ENV_FILE" && set +a

# Escapes a value for use inside a single-quoted SQL literal.
sqlQuote() { printf "%s" "${1//\'/\'\'}"; }

# Runs SQL from stdin, so nothing sensitive is visible in the process list.
runSql() { "${COMPOSE[@]}" exec -T database psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" "$@"; }

readPassword() {
    local first second
    # This function's stdout is captured by the caller, so every prompt and newline
    # must go to stderr -- otherwise they end up glued onto the password itself.
    read -rsp "Password: " first; echo >&2
    read -rsp "Repeat:   " second; echo >&2
    if [ "$first" != "$second" ]; then
        echo "Passwords do not match." >&2
        exit 1
    fi
    if [ ${#first} -lt 6 ]; then
        echo "Use at least 6 characters." >&2
        exit 1
    fi
    printf "%s" "$first"
}

usage() {
    cat <<'EOF'
Usage: ./manage-users.sh <command> [arguments]

  list                                 show all accounts
  add <login> <email> <rank> <tool>    create an account (asks for a password)
  passwd <login>                       change a password (asks for the new one)
  rank <login> <rank>                  change rank: viewer | editor | admin
  tool <login> <tool>                  change CAD tool: altium | kicad
  delete <login>                       remove the account and its database role

  rank   limits the WEB APPLICATION only (viewer cannot create categories).
         Every rank gets read-write SVN access, which is required to add components,
         and read-only database access over ODBC.
  tool   decides which component tables the account can read over ODBC
  login  3-63 chars, lowercase letters/digits/underscore, starting with a letter
EOF
}

command="${1:-}"

case "$command" in

    list)
        runSql -c "SELECT u.login, u.email, u.rank, u.tool,
                          CASE WHEN r.rolname IS NULL THEN 'MISSING' ELSE 'ok' END AS db_role,
                          coalesce(g.rolname, '-') AS db_group
                   FROM private.users u
                   LEFT JOIN pg_roles r ON r.rolname = u.login
                   LEFT JOIN pg_auth_members m ON m.member = r.oid
                   LEFT JOIN pg_roles g ON g.oid = m.roleid
                   ORDER BY u.login;"
        ;;

    add)
        [ $# -eq 5 ] || { usage; exit 1; }
        password="$(readPassword)"
        runSql <<SQL
SELECT private.user_create(
    '$(sqlQuote "$2")', '$(sqlQuote "$password")',
    '$(sqlQuote "$3")', '$(sqlQuote "$4")', '$(sqlQuote "$5")');
SQL
        echo "Account '$2' created. The same login and password now work for SVN and for ODBC."
        ;;

    passwd)
        [ $# -eq 2 ] || { usage; exit 1; }
        password="$(readPassword)"
        runSql <<SQL
SELECT private.user_set_password('$(sqlQuote "$2")', '$(sqlQuote "$password")');
SQL
        echo "Password for '$2' changed in every place at once."
        ;;

    rank)
        [ $# -eq 3 ] || { usage; exit 1; }
        runSql <<SQL
UPDATE private.users SET rank = '$(sqlQuote "$3")' WHERE login = '$(sqlQuote "$2")';
SQL
        echo "Rank for '$2' set to '$3'. SVN permissions follow within 10 seconds."
        ;;

    tool)
        [ $# -eq 3 ] || { usage; exit 1; }
        runSql <<SQL
UPDATE private.users SET tool = '$(sqlQuote "$3")' WHERE login = '$(sqlQuote "$2")';
SQL
        echo "Tool for '$2' set to '$3'."
        ;;

    delete)
        [ $# -eq 2 ] || { usage; exit 1; }
        read -rp "Really delete '$2' and its database role? [y/N] " confirm
        [ "$confirm" = "y" ] || { echo "Cancelled."; exit 0; }
        runSql <<SQL
DELETE FROM private.users WHERE login = '$(sqlQuote "$2")';
SQL
        echo "Account '$2' removed."
        ;;

    *)
        usage
        [ -z "$command" ] && exit 1
        exit 0
        ;;
esac

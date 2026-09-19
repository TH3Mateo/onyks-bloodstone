#!/bin/bash
set -e

echo "--- START ENTRYPOINT ---"

# 1. Wait for PostgreSQL and the specific table to be ready
echo "Czekam na pełną gotowość bazy danych i tabel..."
export PGPASSWORD=$POSTGRES_PASSWORD

until psql -h database -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1 FROM private.users LIMIT 1;" > /dev/null 2>&1; do
  echo "Baza danych lub tabela private.users jeszcze nie istnieje... czekam 2s..."
  sleep 2
done

echo "Baza danych jest w pełni gotowa, tabela private.users znaleziona!"

# 2. Create SVN repository if it doesn't exist
if [ ! -f "/var/svn/$SVN_REPO_NAME/format" ]; then
    mkdir -p "/var/svn/$SVN_REPO_NAME"
    svnadmin create "/var/svn/$SVN_REPO_NAME"
fi

chown -R www-data:www-data /var/svn

# 3. Generate Apache config from template
envsubst '\$POSTGRES_USER \$POSTGRES_PASSWORD \$POSTGRES_DB \$SVN_REPO_NAME' \
    < /usr/local/apache2/conf/httpd.conf.template \
    > /usr/local/apache2/conf/httpd.conf

# 4. Loop for syncing authz file from PostgreSQL
sync_authz_file() {
    echo "Uruchamiam proces synchronizacji uprawnień w tle..."
    
    # Infinite loop for syncing authz file every 10 seconds
    while true; do
        # Create a temporary file with the header
        echo "[/]" > /tmp/svn-authz.tmp
        
        export PGPASSWORD=$POSTGRES_PASSWORD
        
        # Download login and rank from PostgreSQL and append to the temp authz file
        # If the query fails (e.g. database is down), we skip this iteration and try again in 10 seconds
        if psql "host=database dbname=$POSTGRES_DB user=$POSTGRES_USER" -Atc \
           "SELECT login, rank FROM private.users;" >> /tmp/svn-authz.tmp 2>/dev/null; then
           
           # Process the downloaded data to convert ranks to permissions
           # Here we read the temp file line by line, convert ranks to permissions, and write to another temp file
           # We use a case statement to map ranks to permissions (admin and editor get rw, user gets r)
           
           # Clean up the tmp file to only have login and rank
           psql "host=database dbname=$POSTGRES_DB user=$POSTGRES_USER" -Atc \
           "SELECT login, rank FROM private.users;" | while IFS='|' read login rank; do
                # Every account gets read-write on SVN: adding a component means
                # committing its .SchLib/.PcbLib files, so write access is the baseline
                # for using the system at all. Rank does NOT restrict SVN -- it only
                # limits what the web application allows (e.g. creating categories).
                #
                # Must match the public.user_rank enum: viewer / editor / admin. The
                # previous branches were 'server' and 'user', which are not enum values,
                # so viewers matched nothing, got no authz line and were denied entirely.
                case $rank in
                    viewer|editor|admin) echo "$login = rw" ;;
                esac
           done > /tmp/svn-perms.tmp

           # Concat the header and permissions into the final authz file
           echo "[/]" > /tmp/svn-authz.final
           cat /tmp/svn-perms.tmp >> /tmp/svn-authz.final

           # Replace the main authz file if there are changes
           if ! cmp -s /tmp/svn-authz.final /etc/svn-authz; then
               cp /tmp/svn-authz.final /etc/svn-authz
               chown www-data:www-data /etc/svn-authz
               chmod 640 /etc/svn-authz
               echo "$(date) - Zaktualizowano uprawnienia SVN z bazy."
           fi
        fi
        
        # Wait for 10 seconds before next sync
        sleep 10
    done
}

# Run the sync_authz_file function in the background
sync_authz_file &

# =================================================================

echo "Konfiguracja gotowa. Uruchamiam Apache."

# 5. Start Apache in foreground
exec "$@"
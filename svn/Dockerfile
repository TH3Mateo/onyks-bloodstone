FROM httpd:2.4

RUN apt-get update && \
    apt-get install -y \
        subversion \
        libapache2-mod-svn \
        libaprutil1-dbd-pgsql \
        gettext-base \
        postgresql-client \
        python3 \
    && rm -rf /var/lib/apt/lists/* && \
    cp /usr/lib/apache2/modules/mod_dav_svn.so /usr/local/apache2/modules/ && \
    cp /usr/lib/apache2/modules/mod_authz_svn.so /usr/local/apache2/modules/

COPY httpd.conf.template /usr/local/apache2/conf/httpd.conf.template
COPY svn-authz.template /etc/svn-authz.template
COPY hooks/post-commit /usr/local/share/svn-hooks/post-commit
COPY hooks/pre-commit /usr/local/share/svn-hooks/pre-commit
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["httpd-foreground"]
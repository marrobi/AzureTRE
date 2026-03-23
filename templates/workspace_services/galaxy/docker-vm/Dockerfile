# Build gx-it-proxy with native deps in a Node 18 image (Galaxy image has broken apt repos)
FROM node:18 AS gxit-builder
RUN npm install -g gx-it-proxy

FROM quay.io/bgruening/galaxy:24.2

# Copy pre-built gx-it-proxy (with native sqlite3 module) from builder stage
COPY --from=gxit-builder /usr/local/lib/node_modules/gx-it-proxy /galaxy_venv/lib/node_modules/gx-it-proxy
RUN ln -sf ../lib/node_modules/gx-it-proxy/lib/main.js /galaxy_venv/bin/gx-it-proxy && \
    chmod +x /galaxy_venv/bin/gx-it-proxy

# Fix: psycopg2 is installed for system Python 3.10 but Galaxy venv uses Python 3.12
RUN /galaxy_venv/bin/pip install --no-cache-dir psycopg2-binary

# Patch gravity to invoke gx-it-proxy directly instead of via npx (no internet at runtime)
RUN sed -i 's|{virtualenv_bin}npx gx-it-proxy@{settings\[version\]}|{virtualenv_bin}gx-it-proxy|' \
        /galaxy_venv/lib/python3.12/site-packages/gravity/state.py

# Disable CVMFS: not available behind the TRE firewall.
# The startup script (/usr/bin/startup line ~479) appends CVMFS paths to
# GALAXY_CONFIG_TOOL_DATA_TABLE_CONFIG_PATH when running in privileged mode.
# Patch it out so Galaxy only uses our empty config file.
RUN sed -i 's|export GALAXY_CONFIG_TOOL_DATA_TABLE_CONFIG_PATH="$GALAXY_CONFIG_TOOL_DATA_TABLE_CONFIG_PATH,/cvmfs/data.galaxyproject.org|# DISABLED for TRE: export GALAXY_CONFIG_TOOL_DATA_TABLE_CONFIG_PATH="$GALAXY_CONFIG_TOOL_DATA_TABLE_CONFIG_PATH,/cvmfs/data.galaxyproject.org|' /usr/bin/startup

RUN echo '<?xml version="1.0"?><tables></tables>' > /galaxy/config/tool_data_table_conf.xml && \
    echo '<?xml version="1.0"?><tables></tables>' > /etc/galaxy/tool_data_table_conf.xml

ENV GALAXY_CONFIG_TOOL_DATA_TABLE_CONFIG_PATH=/etc/galaxy/tool_data_table_conf.xml
ENV GALAXY_CONFIG_SHED_TOOL_DATA_TABLE_CONFIG=/etc/galaxy/tool_data_table_conf.xml

# Route interactive tool jobs through Docker dispatch so tools requiring Docker
# containers (Jupyter, RStudio, etc.) are sent to the Docker-enabled Slurm destination.
ENV GALAXY_DESTINATIONS_DEFAULT=docker_dispatch
ENV GALAXY_DESTINATIONS_DOCKER_DEFAULT=slurm_cluster_docker

# Fix welcome page: nginx serves /etc/galaxy/web/ at that path, not /static/
ENV GALAXY_CONFIG_WELCOME_URL=/etc/galaxy/web/welcome.html

# Fix nginx large_client_header_buffers for long query strings (414 URI Too Long)
# Fix X-Forwarded-Proto: pass through from upstream proxy instead of $scheme
# (Galaxy is behind Caddy + App Service which terminate TLS)
# Auto-redirect unauthenticated users to Azure OIDC login (skip the login form).
# Galaxy's /authnz/azure/login API returns JSON with redirect_uri, so we serve
# a tiny HTML page at /azure-login that calls it via fetch and follows the redirect.
RUN sed -i '/http {/a \\tlarge_client_header_buffers 4 32k;' /etc/nginx/nginx.conf && \
    sed -i 's/proxy_set_header X-Forwarded-Proto $scheme;/proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;/g' /etc/nginx/galaxy_common.conf && \
    printf '<!DOCTYPE html><html><body>Redirecting to sign in...<script>fetch("/authnz/azure/login").then(function(r){return r.json()}).then(function(d){window.location=d.redirect_uri}).catch(function(){window.location="/root/login"});</script></body></html>\n' > /etc/galaxy/web/azure_login.html && \
    sed -i '/location \/ {/i \\t\tlocation = /azure-login { alias /etc/galaxy/web/azure_login.html; default_type text/html; }' /etc/nginx/galaxy_common.conf && \
    sed -i '/location \/ {/a \\t\tif ($request_uri ~ "^/root/login") { return 302 /azure-login; }' /etc/nginx/galaxy_common.conf

# Configure OIDC authentication with Microsoft Entra ID.
# Galaxy reads these XML configs at startup. The oidc_backends_config.xml
# uses placeholder tokens that are replaced by the entrypoint script using
# env vars passed from Terraform (via cloud-init).
ENV GALAXY_CONFIG_ENABLE_OIDC=True
ENV GALAXY_CONFIG_OIDC_CONFIG_FILE=/etc/galaxy/oidc_config.xml
ENV GALAXY_CONFIG_OIDC_BACKENDS_CONFIG_FILE=/etc/galaxy/oidc_backends_config.xml

# Force OIDC-only login: require login, disable local account creation,
# and prefer the OIDC login button over the username/password form.
ENV GALAXY_CONFIG_REQUIRE_LOGIN=True
ENV GALAXY_CONFIG_ALLOW_USER_CREATION=False
ENV GALAXY_CONFIG_PREFER_CUSTOS_LOGIN=True

RUN printf '<?xml version="1.0"?>\n<OIDC>\n    <provider name="azure">\n        <url>https://login.microsoftonline.com/common/v2.0</url>\n    </provider>\n</OIDC>\n' > /etc/galaxy/oidc_config.xml

RUN printf '<?xml version="1.0"?>\n<OIDC>\n    <provider name="azure">\n        <client_id>__OIDC_CLIENT_ID__</client_id>\n        <client_secret>__OIDC_CLIENT_SECRET__</client_secret>\n        <redirect_uri>https://__GALAXY_HOSTNAME__/authnz/azure/callback</redirect_uri>\n        <tenant_id>__OIDC_TENANT_ID__</tenant_id>\n    </provider>\n</OIDC>\n' > /etc/galaxy/oidc_backends_config.xml

# Entrypoint script to substitute OIDC placeholders from env vars at runtime
RUN printf '#!/bin/bash\nif [ -n "$GALAXY_OIDC_CLIENT_ID" ]; then\n    sed -i "s|__OIDC_CLIENT_ID__|$GALAXY_OIDC_CLIENT_ID|g" /etc/galaxy/oidc_backends_config.xml\n    sed -i "s|__OIDC_CLIENT_SECRET__|$GALAXY_OIDC_CLIENT_SECRET|g" /etc/galaxy/oidc_backends_config.xml\n    sed -i "s|__OIDC_TENANT_ID__|$GALAXY_OIDC_TENANT_ID|g" /etc/galaxy/oidc_backends_config.xml\n    sed -i "s|__GALAXY_HOSTNAME__|$GALAXY_HOSTNAME|g" /etc/galaxy/oidc_backends_config.xml\n    if [ -n "$GALAXY_OIDC_AUTHORITY_URL" ]; then\n        sed -i "s|https://login.microsoftonline.com|$GALAXY_OIDC_AUTHORITY_URL|g" /etc/galaxy/oidc_config.xml\n    fi\nfi\nexec /usr/bin/startup "$@"\n' > /usr/local/bin/galaxy-entrypoint.sh && \
    chmod +x /usr/local/bin/galaxy-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/galaxy-entrypoint.sh"]

/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */
package org.apache.guacamole.auth.azuretre;

import org.apache.guacamole.GuacamoleException;
import org.json.JSONObject;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;

/**
 * Service that fetches workspace authentication configuration from the TRE Core API.
 * This is used by the shared Guacamole service to dynamically determine the correct
 * OAuth2 configuration for each workspace.
 *
 * Uses the user's Core API token to fetch workspace details, then validates the user's
 * workspace-scoped token against the workspace-specific OAuth2 configuration.
 */
public final class WorkspaceAuthConfigService {

    /** Maximum HTTP status code that indicates success. */
    private static final int HTTP_SUCCESS_MAX = 299;

    /** API call timeout in seconds. */
    private static final int API_TIMEOUT_SECONDS = 10;

    /** Cache expiry time in minutes. */
    private static final int CACHE_EXPIRY_MINUTES = 5;

    /** Cache expiry time in milliseconds, derived from CACHE_EXPIRY_MINUTES. */
    private static final long CACHE_EXPIRY_MS =
        TimeUnit.MINUTES.toMillis(CACHE_EXPIRY_MINUTES);

    /** Logger instance. */
    private static final Logger LOGGER = LoggerFactory.getLogger(
        WorkspaceAuthConfigService.class);

    /** Cache for workspace auth configurations. */
    private static final ConcurrentHashMap<String, CachedAuthConfig> AUTH_CONFIG_CACHE =
        new ConcurrentHashMap<>();

    /**
     * Represents a cached workspace auth configuration with expiry time.
     */
    private static final class CachedAuthConfig {
        private final WorkspaceAuthConfig config;
        private final long expiryTime;

        CachedAuthConfig(final WorkspaceAuthConfig cfg) {
            this.config = cfg;
            this.expiryTime = System.currentTimeMillis() + CACHE_EXPIRY_MS;
        }

        boolean isExpired() {
            return System.currentTimeMillis() > expiryTime;
        }

        WorkspaceAuthConfig getConfig() {
            return config;
        }
    }

    /**
     * Represents the authentication configuration for a workspace.
     */
    public static final class WorkspaceAuthConfig {
        private final String clientId;
        private final String scopeId;
        private final String issuer;
        private final String jwksEndpoint;

        /**
         * Creates a new WorkspaceAuthConfig.
         *
         * @param cId     OAuth2 client ID.
         * @param sId     Workspace scope ID.
         * @param iss     OAuth2 issuer URL.
         * @param jwks    JWKS endpoint URL.
         */
        public WorkspaceAuthConfig(
            final String cId,
            final String sId,
            final String iss,
            final String jwks) {
            this.clientId = cId;
            this.scopeId = sId;
            this.issuer = iss;
            this.jwksEndpoint = jwks;
        }

        public String getClientId() {
            return clientId;
        }

        public String getScopeId() {
            return scopeId;
        }

        public String getIssuer() {
            return issuer;
        }

        public String getJwksEndpoint() {
            return jwksEndpoint;
        }
    }

    private WorkspaceAuthConfigService() {
        // Utility class
    }

    /**
     * Extracts the workspace ID from a Guacamole request URI.
     * Expected URI format: /guacamole/{workspace_id}/...
     *
     * @param requestUri the request URI.
     * @return the workspace ID, or null if not found.
     */
    public static String extractWorkspaceIdFromUri(final String requestUri) {
        if (requestUri == null || requestUri.isEmpty()) {
            return null;
        }

        // Expected format: /guacamole/{workspace_id}/... or /{workspace_id}/...
        final String[] parts = requestUri.split("/");
        for (int i = 0; i < parts.length; i++) {
            // Look for a UUID-like workspace ID
            if (parts[i].matches(
                "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                    + "[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")) {
                return parts[i];
            }
        }

        // Also check for workspace ID passed in query parameter or header
        return null;
    }

    /**
     * Fetches the workspace authentication configuration from the TRE Core API.
     * Uses the user's Core API token to fetch workspace details, then derives
     * auth config from the workspace properties.
     *
     * @param workspaceId   the workspace ID.
     * @param coreApiToken  the user's Core API-scoped access token.
     * @return the workspace auth configuration.
     * @throws GuacamoleException if the configuration cannot be retrieved.
     */
    public static WorkspaceAuthConfig getWorkspaceAuthConfig(
        final String workspaceId,
        final String coreApiToken) throws GuacamoleException {

        // Check cache first
        final CachedAuthConfig cached = AUTH_CONFIG_CACHE.get(workspaceId);
        if (cached != null && !cached.isExpired()) {
            LOGGER.debug("Using cached auth config for workspace {}",
                workspaceId);
            return cached.getConfig();
        }

        LOGGER.info("Fetching auth config for workspace {}", workspaceId);

        final String apiUrl = System.getenv("API_URL");
        if (apiUrl == null || apiUrl.isEmpty()) {
            throw new GuacamoleException("API_URL environment variable not set");
        }

        final String aadAuthorityUrl = System.getenv("AAD_AUTHORITY_URL");
        if (aadAuthorityUrl == null || aadAuthorityUrl.isEmpty()) {
            throw new GuacamoleException(
                "AAD_AUTHORITY_URL environment variable not set");
        }

        // Use the existing workspace endpoint with user's Core API token
        final String url = String.format(
            "%s/api/workspaces/%s",
            apiUrl,
            workspaceId);

        final HttpClient client = HttpClient.newHttpClient();
        final HttpRequest request = HttpRequest.newBuilder(URI.create(url))
            .header("Accept", "application/json")
            .header("Authorization", "Bearer " + coreApiToken)
            .timeout(Duration.ofSeconds(API_TIMEOUT_SECONDS))
            .build();

        final HttpResponse<String> response;
        try {
            response = client.send(
                request,
                HttpResponse.BodyHandlers.ofString());
        } catch (final IOException | InterruptedException ex) {
            LOGGER.error("Failed to fetch workspace", ex);
            throw new GuacamoleException(
                "Failed to fetch workspace: " + ex.getMessage());
        }

        final int statusCode = response.statusCode();
        if (statusCode > HTTP_SUCCESS_MAX) {
            LOGGER.error(
                "Failed to fetch workspace. Status: {}",
                statusCode);
            throw new GuacamoleException(
                "Failed to fetch workspace. Status: " + statusCode);
        }

        final String resBody = response.body();
        if (resBody == null || resBody.isBlank()) {
            throw new GuacamoleException(
                "Empty response from workspace API");
        }

        try {
            final JSONObject result = new JSONObject(resBody);
            final JSONObject workspace = result.getJSONObject("workspace");
            final JSONObject properties = workspace.getJSONObject("properties");

            // Extract auth properties from workspace
            final String clientId = properties.optString("client_id", "");
            final String scopeId = properties.optString("scope_id", "");

            // Get tenant ID - use workspace-specific if available, otherwise
            // fall back to AAD_TENANT_ID env var
            String tenantId = properties.optString("auth_tenant_id", "");
            if (tenantId.isEmpty()) {
                tenantId = System.getenv("AAD_TENANT_ID");
                if (tenantId == null || tenantId.isEmpty()) {
                    throw new GuacamoleException(
                        "No auth_tenant_id in workspace and AAD_TENANT_ID not set");
                }
            }

            // Derive issuer and JWKS endpoint from tenant ID
            final String issuer = String.format(
                "%s/%s/v2.0",
                aadAuthorityUrl,
                tenantId);
            final String jwksEndpoint = String.format(
                "%s/%s/discovery/v2.0/keys",
                aadAuthorityUrl,
                tenantId);

            final WorkspaceAuthConfig config = new WorkspaceAuthConfig(
                clientId,
                scopeId,
                issuer,
                jwksEndpoint);

            // Cache the configuration
            AUTH_CONFIG_CACHE.put(workspaceId, new CachedAuthConfig(config));

            return config;
        } catch (final GuacamoleException ex) {
            throw ex;
        } catch (final Exception ex) {
            LOGGER.error("Failed to parse workspace response", ex);
            throw new GuacamoleException(
                "Failed to parse workspace response");
        }
    }

    /**
     * Clears the auth config cache for a specific workspace.
     *
     * @param workspaceId the workspace ID to clear from cache.
     */
    public static void clearCache(final String workspaceId) {
        AUTH_CONFIG_CACHE.remove(workspaceId);
    }

    /**
     * Clears the entire auth config cache.
     */
    public static void clearAllCache() {
        AUTH_CONFIG_CACHE.clear();
    }
}

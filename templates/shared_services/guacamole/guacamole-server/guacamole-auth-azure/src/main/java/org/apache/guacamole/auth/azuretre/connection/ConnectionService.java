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
package org.apache.guacamole.auth.azuretre.connection;

import org.apache.guacamole.GuacamoleException;
import org.apache.guacamole.auth.azuretre.AzureTREAuthenticationProvider;
import org.apache.guacamole.auth.azuretre.user.AzureTREAuthenticatedUser;
import org.apache.guacamole.net.auth.Connection;
import org.apache.guacamole.protocol.GuacamoleConfiguration;
import org.json.JSONArray;
import org.json.JSONObject;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/**
 * Utility methods that hydrate Guacamole connections for TRE users.
 */
public final class ConnectionService {

    /** Maximum HTTP status code that still indicates success. */
    private static final int HTTP_SUCCESS_MAX = 299;

    /** API call timeout in seconds. */
    private static final int API_TIMEOUT_SECONDS = 5;

    /**
     * Default template name of the Guacamole workspace service. Used to
     * discover the workspace services whose user-resources (VMs) should be
     * surfaced. Can be overridden via the
     * {@code GUACAMOLE_SERVICE_TEMPLATE_NAME} environment variable.
     */
    private static final String DEFAULT_GUACAMOLE_SERVICE_TEMPLATE_NAME =
        "tre-service-guacamole";

    /**
     * Retrieves the JSON body for a GET request against the TRE API.
     */
    @FunctionalInterface
    interface ApiJsonFetcher {
        String fetch(String url, AzureTREAuthenticatedUser user)
            throws GuacamoleException;
    }

    /** Logger for this class. */
    private static final Logger LOGGER = LoggerFactory.getLogger(
        ConnectionService.class);

    private ConnectionService() {
        // Utility class
    }

    /**
     * Builds a map of Guacamole connections available to the authenticated
     * TRE user.
     *
     * @param user the authenticated TRE user.
     * @return map keyed by connection identifier.
     * @throws GuacamoleException if retrieving connections fails.
     */
    public static Map<String, Connection> getConnections(
        final AzureTREAuthenticatedUser user) throws GuacamoleException {
        final Map<String, Connection> connections = new TreeMap<>();
        final Map<String, GuacamoleConfiguration> configs =
            getConfigurations(user);

        for (final Map.Entry<String, GuacamoleConfiguration> config
            : configs.entrySet()) {
            final Connection connection = new TokenInjectingConnection(
                config.getValue().getParameter("display_name"),
                config.getKey(),
                config.getValue(),
                true);
            connection.setParentIdentifier(
                AzureTREAuthenticationProvider.ROOT_CONNECTION_GROUP);
            connections.putIfAbsent(config.getKey(), connection);
        }

        return connections;
    }

    private static Map<String, GuacamoleConfiguration> getConfigurations(
        final AzureTREAuthenticatedUser user) throws GuacamoleException {
        final Map<String, GuacamoleConfiguration> configs = new TreeMap<>();

        if (user == null) {
            return configs;
        }

        try {
            final JSONArray vmsJsonArray = getVMsFromProjectAPI(user);

            for (int i = 0; i < vmsJsonArray.length(); i++) {
                final GuacamoleConfiguration config =
                    new GuacamoleConfiguration();
                final JSONObject vmJsonObject = vmsJsonArray.getJSONObject(i);
                final JSONObject templateParameters =
                    (JSONObject) vmJsonObject.get("properties");

                if (templateParameters.has("hostname")
                    && templateParameters.has("ip")) {
                    final String azureResourceId =
                        templateParameters.getString("hostname");
                    final String ip = templateParameters.getString("ip");
                    final String displayName =
                        templateParameters.getString("display_name");

                    setConfig(config, azureResourceId, ip, displayName);
                    LOGGER.info(
                        "Adding VM id:{} ip:{} name:{}",
                        azureResourceId,
                        ip,
                        displayName);
                    configs.putIfAbsent(azureResourceId, config);
                } else {
                    LOGGER.info("Missing ip or hostname, skipping VM");
                }
            }
        } catch (final Exception ex) {
            LOGGER.error("Exception getting VMs", ex);
            throw new GuacamoleException(
                "Exception getting VMs: " + ex.getMessage());
        }

        return configs;
    }

    private static void setConfig(
        final GuacamoleConfiguration config,
        final String azureResourceId,
        final String ip,
        final String displayName) {
        config.setProtocol("rdp");
        config.setParameter("hostname", ip);
        config.setParameter("display_name", displayName);
        config.setParameter("resize-method", "display-update");
        config.setParameter("azure-resource-id", azureResourceId);
        config.setParameter("port", "3389");
        config.setParameter("ignore-cert", "true");

        setEnvParameter(config, "disable-copy", "GUAC_DISABLE_COPY");
        setEnvParameter(config, "disable-paste", "GUAC_DISABLE_PASTE");
        setEnvParameter(config, "enable-drive", "GUAC_ENABLE_DRIVE");
        setEnvParameter(config, "drive-name", "GUAC_DRIVE_NAME");
        setEnvParameter(config, "drive-path", "GUAC_DRIVE_PATH");
        setEnvParameter(
            config,
            "disable-download",
            "GUAC_DISABLE_DOWNLOAD");
        setEnvParameter(
            config,
            "disable-upload",
            "GUAC_DISABLE_UPLOAD");

        final String serverLayout = System.getenv("GUAC_SERVER_LAYOUT");
        if (serverLayout != null && !serverLayout.isEmpty()) {
            config.setParameter("server-layout", serverLayout);
        }
    }

    private static void setEnvParameter(
        final GuacamoleConfiguration config,
        final String parameterName,
        final String envVarName) {
        final String value = System.getenv(envVarName);
        if (value != null && !value.isEmpty()) {
            config.setParameter(parameterName, value);
        }
    }

    private static JSONArray getVMsFromProjectAPI(
        final AzureTREAuthenticatedUser user) throws GuacamoleException {
        return collectUserResources(user, ConnectionService::fetchJson);
    }

    /**
     * Aggregates the user-resources (VMs) visible to the user across every
     * Guacamole workspace service in the resolved workspace.
     *
     * <p>In shared service mode the workspace is determined per-request from
     * the authenticated user (dynamic), so that VM retrieval is always scoped
     * to the workspace the user's token was validated against. A single
     * workspace may host more than one Guacamole workspace service, so all of
     * them are discovered and their user-resources merged.</p>
     *
     * @param user the authenticated TRE user.
     * @param fetcher performs the authenticated GET requests (injected to
     *     allow unit testing without a live API).
     * @return the aggregated array of user-resource objects.
     * @throws GuacamoleException if the workspace cannot be resolved or the
     *     workspace-services listing cannot be retrieved.
     */
    static JSONArray collectUserResources(
        final AzureTREAuthenticatedUser user,
        final ApiJsonFetcher fetcher) throws GuacamoleException {
        final String apiUrl = requireEnv("API_URL", "API URL");
        final String workspaceId = resolveWorkspaceId(user);

        final List<String> serviceIds =
            resolveGuacamoleServiceIds(apiUrl, workspaceId, user, fetcher);

        final JSONArray aggregated = new JSONArray();
        for (final String serviceId : serviceIds) {
            final String url = String.format(
                "%s/api/workspaces/%s/workspace-services/%s/user-resources",
                apiUrl,
                workspaceId,
                serviceId);
            try {
                final String body = fetcher.fetch(url, user);
                if (body != null && !body.isBlank()) {
                    final JSONArray userResources =
                        new JSONObject(body).getJSONArray("userResources");
                    for (int i = 0; i < userResources.length(); i++) {
                        aggregated.put(userResources.get(i));
                    }
                }
            } catch (final Exception ex) {
                // Skip a single failing service rather than blanking out all
                // connections for the user.
                LOGGER.error(
                    "Failed getting user-resources for service {}: {}",
                    serviceId,
                    ex.getMessage());
            }
        }

        return aggregated;
    }

    /**
     * Resolves the IDs of the Guacamole workspace services to query.
     *
     * <p>If a static {@code SERVICE_ID} is configured (legacy single-workspace
     * mode) it is used directly. Otherwise the workspace-services listing is
     * retrieved and filtered to the enabled Guacamole services.</p>
     */
    private static List<String> resolveGuacamoleServiceIds(
        final String apiUrl,
        final String workspaceId,
        final AzureTREAuthenticatedUser user,
        final ApiJsonFetcher fetcher) throws GuacamoleException {
        final String staticServiceId = System.getenv("SERVICE_ID");
        if (staticServiceId != null && !staticServiceId.isEmpty()) {
            final List<String> ids = new ArrayList<>();
            ids.add(staticServiceId);
            return ids;
        }

        final String url = String.format(
            "%s/api/workspaces/%s/workspace-services",
            apiUrl,
            workspaceId);
        final String body = fetcher.fetch(url, user);
        return extractGuacamoleServiceIds(body);
    }

    /**
     * Extracts the IDs of enabled Guacamole workspace services from a
     * workspace-services listing response body.
     *
     * @param body the JSON body returned by the workspace-services endpoint.
     * @return the list of matching workspace service IDs (never {@code null}).
     */
    static List<String> extractGuacamoleServiceIds(final String body) {
        final List<String> ids = new ArrayList<>();
        if (body == null || body.isBlank()) {
            return ids;
        }

        final JSONArray services =
            new JSONObject(body).optJSONArray("workspaceServices");
        if (services == null) {
            return ids;
        }

        final String templateName = guacamoleTemplateName();
        for (int i = 0; i < services.length(); i++) {
            final JSONObject service = services.getJSONObject(i);
            if (!templateName.equals(service.optString("templateName"))) {
                continue;
            }
            if (!service.optBoolean("isEnabled", true)) {
                continue;
            }
            final String id = service.optString("id", "");
            if (!id.isEmpty()) {
                ids.add(id);
            }
        }

        return ids;
    }

    private static String guacamoleTemplateName() {
        final String override =
            System.getenv("GUACAMOLE_SERVICE_TEMPLATE_NAME");
        if (override != null && !override.isEmpty()) {
            return override;
        }
        return DEFAULT_GUACAMOLE_SERVICE_TEMPLATE_NAME;
    }

    private static String resolveWorkspaceId(
        final AzureTREAuthenticatedUser user) throws GuacamoleException {
        String workspaceId = user.getWorkspaceId();
        if (workspaceId == null || workspaceId.isEmpty()) {
            // Fall back to the WORKSPACE_ID environment variable for static
            // (single-workspace) mode.
            workspaceId = System.getenv("WORKSPACE_ID");
        }
        if (workspaceId == null || workspaceId.isEmpty()) {
            throw new GuacamoleException(
                "Unable to determine workspace ID for user-resources lookup");
        }
        return workspaceId;
    }

    private static String requireEnv(final String name, final String label)
        throws GuacamoleException {
        final String value = System.getenv(name);
        if (value == null || value.isEmpty()) {
            throw new GuacamoleException(
                "Unable to determine " + label + " for user-resources lookup");
        }
        return value;
    }

    /**
     * Performs an authenticated GET request against the TRE API and returns
     * the response body.
     *
     * @param url the request URL.
     * @param user the authenticated TRE user whose token is used.
     * @return the response body (may be blank).
     * @throws GuacamoleException if the request fails or returns an error
     *     status code.
     */
    private static String fetchJson(
        final String url,
        final AzureTREAuthenticatedUser user) throws GuacamoleException {
        final HttpClient client = HttpClient.newHttpClient();
        final HttpRequest request = HttpRequest.newBuilder(URI.create(url))
            .header("Accept", "application/json")
            .header("Authorization", "Bearer " + user.getAccessToken())
            .timeout(Duration.ofSeconds(API_TIMEOUT_SECONDS))
            .build();

        final HttpResponse<String> response;
        try {
            response = client.send(
                request,
                HttpResponse.BodyHandlers.ofString());
        } catch (final IOException | InterruptedException ex) {
            LOGGER.error("Connection failed", ex);
            throw new GuacamoleException(
                "Connection failed: " + ex.getMessage());
        }

        final int statusCode = response.statusCode();
        final String resBody = response.body();
        if (statusCode > HTTP_SUCCESS_MAX) {
            final String errorMsg =
                "Failed getting response. statusCode: " + statusCode;
            LOGGER.error(errorMsg);
            if (resBody != null && !resBody.isBlank()) {
                LOGGER.error("response: {}", resBody);
            }
            throw new GuacamoleException(errorMsg);
        }

        LOGGER.debug("Got API response");
        return resBody;
    }
}

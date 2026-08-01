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
import java.util.LinkedHashMap;
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
     * Key under which each aggregated user-resource carries the guac policy
     * settings (copy/paste, drive, download/upload, keyboard layout) taken
     * from its parent Guacamole workspace service's specification. Prefixed
     * with an underscore so it cannot collide with a real resource property.
     */
    private static final String GUAC_SETTINGS_KEY = "_guacSettings";

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
                final JSONObject vmJsonObject = vmsJsonArray.getJSONObject(i);
                final GuacamoleConfiguration config =
                    buildConfiguration(vmJsonObject);

                if (config != null) {
                    configs.putIfAbsent(
                        config.getParameter("azure-resource-id"), config);
                }
            }
        } catch (final Exception ex) {
            LOGGER.error("Exception getting VMs", ex);
            throw new GuacamoleException(
                "Exception getting VMs: " + ex.getMessage());
        }

        return configs;
    }

    /**
     * Builds a Guacamole configuration for a single user-resource (VM) JSON
     * object, applying the policy settings from the VM's parent workspace
     * service specification (tagged under {@link #GUAC_SETTINGS_KEY}).
     *
     * @param vmJsonObject the user-resource JSON object.
     * @return the configuration, or {@code null} if the VM is missing the
     *     hostname/ip required to build a connection.
     */
    static GuacamoleConfiguration buildConfiguration(
        final JSONObject vmJsonObject) {
        final JSONObject templateParameters =
            (JSONObject) vmJsonObject.get("properties");
        final JSONObject workspaceServiceSettings =
            vmJsonObject.optJSONObject(GUAC_SETTINGS_KEY);

        if (!templateParameters.has("hostname")
            || !templateParameters.has("ip")) {
            LOGGER.info("Missing ip or hostname, skipping VM");
            return null;
        }

        final String azureResourceId =
            templateParameters.getString("hostname");
        final String ip = templateParameters.getString("ip");
        final String displayName =
            templateParameters.getString("display_name");

        final GuacamoleConfiguration config = new GuacamoleConfiguration();
        setConfig(
            config,
            azureResourceId,
            ip,
            displayName,
            workspaceServiceSettings);
        LOGGER.info(
            "Adding VM id:{} ip:{} name:{}",
            azureResourceId,
            ip,
            displayName);
        return config;
    }

    private static void setConfig(
        final GuacamoleConfiguration config,
        final String azureResourceId,
        final String ip,
        final String displayName,
        final JSONObject workspaceServiceSettings) {
        config.setProtocol("rdp");
        config.setParameter("hostname", ip);
        config.setParameter("display_name", displayName);
        config.setParameter("resize-method", "display-update");
        config.setParameter("azure-resource-id", azureResourceId);
        config.setParameter("port", "3389");
        config.setParameter("ignore-cert", "true");

        // Guacamole policy settings (copy/paste, drive, download/upload and
        // keyboard layout) are taken solely from the parent Guacamole
        // workspace service's specification so that each workspace's own
        // policy is honoured. When a workspace service does not specify a
        // value the Guacamole built-in default for that parameter applies.
        applyGuacParameter(config, "disable-copy",
            "guac_disable_copy", workspaceServiceSettings);
        applyGuacParameter(config, "disable-paste",
            "guac_disable_paste", workspaceServiceSettings);
        applyGuacParameter(config, "enable-drive",
            "guac_enable_drive", workspaceServiceSettings);
        applyGuacParameter(config, "drive-name",
            "guac_drive_name", workspaceServiceSettings);
        applyGuacParameter(config, "drive-path",
            "guac_drive_path", workspaceServiceSettings);
        applyGuacParameter(config, "disable-download",
            "guac_disable_download", workspaceServiceSettings);
        applyGuacParameter(config, "disable-upload",
            "guac_disable_upload", workspaceServiceSettings);
        applyGuacParameter(config, "server-layout",
            "guac_server_layout", workspaceServiceSettings);
    }

    /**
     * Applies a single Guacamole connection parameter from the parent
     * workspace service's specification (its {@code properties}). When the
     * workspace service does not set the property the parameter is left
     * unset and Guacamole's built-in default applies.
     *
     * @param config the connection configuration to mutate.
     * @param parameterName the Guacamole connection parameter name.
     * @param propertyName the workspace service property name.
     * @param workspaceServiceSettings the workspace service properties (may be
     *     {@code null} when unavailable, e.g. legacy single-workspace mode).
     */
    private static void applyGuacParameter(
        final GuacamoleConfiguration config,
        final String parameterName,
        final String propertyName,
        final JSONObject workspaceServiceSettings) {
        if (workspaceServiceSettings != null
            && workspaceServiceSettings.has(propertyName)
            && !workspaceServiceSettings.isNull(propertyName)) {
            final String value = String.valueOf(
                workspaceServiceSettings.get(propertyName));
            if (!value.isEmpty()) {
                config.setParameter(parameterName, value);
            }
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

        final Map<String, JSONObject> services =
            resolveGuacamoleServices(apiUrl, workspaceId, user, fetcher);

        final JSONArray aggregated = new JSONArray();
        for (final Map.Entry<String, JSONObject> service
            : services.entrySet()) {
            final String serviceId = service.getKey();
            final JSONObject serviceProperties = service.getValue();
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
                        final Object resource = userResources.get(i);
                        // Tag each VM with its parent workspace service's
                        // policy settings so the connection can honour that
                        // workspace's specification (copy/paste, drive, etc.).
                        if (resource instanceof JSONObject
                            && serviceProperties != null) {
                            ((JSONObject) resource).put(
                                GUAC_SETTINGS_KEY, serviceProperties);
                        }
                        aggregated.put(resource);
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
     * Resolves the Guacamole workspace services to query, mapped to the
     * {@code properties} (specification) of each service.
     *
     * <p>If a static {@code SERVICE_ID} is configured (legacy single-workspace
     * mode) it is used directly with no properties (the shared service's
     * deployment-time defaults then apply). Otherwise the workspace-services
     * listing is retrieved and filtered to the enabled Guacamole services,
     * preserving each service's properties.</p>
     *
     * @return an ordered map of workspace service ID to its properties (the
     *     properties value may be {@code null} when unavailable).
     */
    private static Map<String, JSONObject> resolveGuacamoleServices(
        final String apiUrl,
        final String workspaceId,
        final AzureTREAuthenticatedUser user,
        final ApiJsonFetcher fetcher) throws GuacamoleException {
        final Map<String, JSONObject> services = new LinkedHashMap<>();

        final String staticServiceId = System.getenv("SERVICE_ID");
        if (staticServiceId != null && !staticServiceId.isEmpty()) {
            services.put(staticServiceId, null);
            return services;
        }

        final String url = String.format(
            "%s/api/workspaces/%s/workspace-services",
            apiUrl,
            workspaceId);
        final String body = fetcher.fetch(url, user);
        for (final JSONObject service : extractGuacamoleServices(body)) {
            final String id = service.optString("id", "");
            if (!id.isEmpty()) {
                services.put(id, service.optJSONObject("properties"));
            }
        }
        return services;
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
        for (final JSONObject service : extractGuacamoleServices(body)) {
            final String id = service.optString("id", "");
            if (!id.isEmpty()) {
                ids.add(id);
            }
        }
        return ids;
    }

    /**
     * Extracts the enabled Guacamole workspace service objects (including
     * their {@code properties}) from a workspace-services listing response
     * body.
     *
     * @param body the JSON body returned by the workspace-services endpoint.
     * @return the list of matching workspace service objects (never
     *     {@code null}).
     */
    static List<JSONObject> extractGuacamoleServices(final String body) {
        final List<JSONObject> matches = new ArrayList<>();
        if (body == null || body.isBlank()) {
            return matches;
        }

        final JSONArray services =
            new JSONObject(body).optJSONArray("workspaceServices");
        if (services == null) {
            return matches;
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
            matches.add(service);
        }

        return matches;
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

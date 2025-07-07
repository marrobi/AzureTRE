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
import org.apache.guacamole.auth.azuretre.TreApiAuthenticationService;
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
import java.util.Map;
import java.util.TreeMap;

public class ConnectionService {
    /**
     * Logger for this class.
     */
    private static final Logger LOGGER = LoggerFactory.getLogger(ConnectionService.class);

    public static Map<String, Connection> getConnections(final AzureTREAuthenticatedUser user)
          throws GuacamoleException {
        final Map<String, Connection> connections = new TreeMap<>();
        final Map<String, GuacamoleConfiguration> configs = getConfigurations(user);

        for (final Map.Entry<String, GuacamoleConfiguration> config : configs.entrySet()) {
            final Connection connection =
                  new TokenInjectingConnection(
                      config.getValue().getParameter("display_name"),
                      config.getKey(),
                      config.getValue(),
                      true);
            connection.setParentIdentifier(AzureTREAuthenticationProvider.ROOT_CONNECTION_GROUP);
            connections.putIfAbsent(config.getKey(), connection);
        }

        return connections;
    }

    private static Map<String, GuacamoleConfiguration> getConfigurations(final AzureTREAuthenticatedUser user)
          throws GuacamoleException {
        final Map<String, GuacamoleConfiguration> configs = new TreeMap<>();
        if (user != null) {
            try {
                final JSONArray vmsJsonArray = getVMsFromProjectAPI(user);
                for (int i = 0; i < vmsJsonArray.length(); i++) {
                    final GuacamoleConfiguration config = new GuacamoleConfiguration();
                    final JSONObject vmJsonObject = vmsJsonArray.getJSONObject(i);
                    final JSONObject templateParameters = (JSONObject) vmJsonObject.get("properties");
                    if (templateParameters.has("hostname") && templateParameters.has("ip")) {
                        final String azureResourceId = templateParameters.getString("hostname");
                        final String ip = templateParameters.getString("ip");
                        final String displayName = templateParameters.getString("display_name");
                        setConfig(config, azureResourceId, ip, displayName);
                        LOGGER.info("Adding a VM, ID: {} IP: {}, Name:{}", azureResourceId, ip, displayName);
                        configs.putIfAbsent(templateParameters.getString("hostname"), config);
                    } else {
                        LOGGER.info("Missing ip or hostname, skipping...");
                    }
                }
            } catch (final Exception ex) {
                LOGGER.error("Exception getting VMs", ex);
                throw new GuacamoleException("Exception getting VMs: " + ex.getMessage());
            }
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
        config.setParameter("disable-copy", System.getenv("GUAC_DISABLE_COPY"));
        config.setParameter("disable-paste", System.getenv("GUAC_DISABLE_PASTE"));
        config.setParameter("enable-drive", System.getenv("GUAC_ENABLE_DRIVE"));
        config.setParameter("drive-name", System.getenv("GUAC_DRIVE_NAME"));
        config.setParameter("drive-path", System.getenv("GUAC_DRIVE_PATH"));
        config.setParameter("disable-download", System.getenv("GUAC_DISABLE_DOWNLOAD"));
        config.setParameter("disable-upload", System.getenv("GUAC_DISABLE_UPLOAD"));

        String serverLayout = System.getenv("GUAC_SERVER_LAYOUT");
        if (serverLayout != null) {
            if (!serverLayout.isEmpty()) {
                config.setParameter("server-layout", serverLayout);
            }
        }
    }

    private static JSONArray getVMsFromProjectAPI(final AzureTREAuthenticatedUser user) throws GuacamoleException {
        final JSONArray virtualMachines;

        // Step 1: Extract workspace ID from the request URL
        String workspaceId = extractWorkspaceId(user);
        LOGGER.info("Using workspace ID: {}", workspaceId);

        // Step 2: Get workspace client ID from session (stored during authentication)
        String workspaceClientId = null;
        if (user.getCredentials().getRequest().getSession(false) != null) {
            workspaceClientId = (String) user.getCredentials().getRequest().getSession(false)
                .getAttribute("workspace_client_id_" + workspaceId);
        }

        if (workspaceClientId == null || workspaceClientId.isEmpty()) {
            throw new GuacamoleException("Workspace client ID not found in session. Authentication may have expired.");
        }

        LOGGER.debug("Using workspace client ID: {}", workspaceClientId);

        // Step 3: Check if we have a workspace token from the user's session
        String workspaceToken = getWorkspaceTokenFromSession(user, workspaceClientId);

        if (workspaceToken == null) {
            // Need to redirect user for workspace authentication
            String authUrl = TreApiAuthenticationService.getWorkspaceAuthenticationUrl(workspaceClientId, workspaceId);
            LOGGER.info("User needs to authenticate with workspace. Redirect URL: {}", authUrl);
            throw new GuacamoleException("WORKSPACE_AUTH_REQUIRED:" + authUrl);
        }

        // Step 4: Use workspace token to get VMs from workspace API
        final String url = String.format("%s/api/workspaces/%s/workspace-services/%s/user-resources",
            System.getenv("API_URL"), workspaceId, System.getenv("SERVICE_ID"));

        final var client = HttpClient.newHttpClient();
        final var request = HttpRequest.newBuilder(URI.create(url))
            .header("Accept", "application/json")
            .header("Authorization", "Bearer " + workspaceToken)
            .timeout(Duration.ofSeconds(5))
            .build();

        final HttpResponse<String> response;
        try {
            response = client.send(request, HttpResponse.BodyHandlers.ofString());
        } catch (final IOException | InterruptedException ex) {
            LOGGER.error("Connection failed", ex);
            throw new GuacamoleException("Connection failed: " + ex.getMessage());
        }

        var statusCode = response.statusCode();
        var resBody = response.body();

        if (statusCode >= 300) {
            var errorMsg = "Failed getting VMs with status code. statusCode: " + statusCode;
            LOGGER.error(errorMsg);
            if (!resBody.isBlank()) {
                LOGGER.error("response: " + resBody);
            }
            throw new GuacamoleException(errorMsg);
        }

        LOGGER.debug("Got VMs list");

        if (!resBody.isBlank()) {
            final JSONObject result = new JSONObject(resBody);
            virtualMachines = result.getJSONArray("userResources");
        } else {
            LOGGER.debug("Got an empty response");
            virtualMachines = new JSONArray();
        }

        return virtualMachines;
    }

    /**
     * Extracts the workspace ID from the user context or request.
     */
    private static String extractWorkspaceId(final AzureTREAuthenticatedUser user) {
        // Try to get workspace ID from the request context
        if (user.getCredentials() != null && user.getCredentials().getRequest() != null) {
            String requestPath = user.getCredentials().getRequest().getRequestURI();
            String workspaceId = TreApiAuthenticationService.extractWorkspaceIdFromPath(requestPath);
            if (workspaceId != null) {
                return workspaceId;
            }
        }

        // Fall back to environment variable
        String defaultWorkspaceId = System.getenv("WORKSPACE_ID");
        LOGGER.debug("Using default workspace ID from environment: {}", defaultWorkspaceId);
        return defaultWorkspaceId;
    }

    /**
     * Verifies that the user has access to the specified workspace using the TRE API and user's SSO token.
     */
    private static void verifyWorkspaceAccess(String userSsoToken, String workspaceId, AzureTREAuthenticatedUser user)
            throws GuacamoleException {
        try {
            // Call TRE API to get user's accessible workspaces using their SSO token
            final String url = String.format("%s/api/workspaces", System.getenv("API_URL"));

            final var client = HttpClient.newHttpClient();
            final var request = HttpRequest.newBuilder(URI.create(url))
                .header("Accept", "application/json")
                .header("Authorization", "Bearer " + userSsoToken)
                .timeout(Duration.ofSeconds(5))
                .build();

            final HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());

            if (response.statusCode() >= 300) {
                LOGGER.warn("Failed to verify workspace access. Status: {}, Response: {}",
                    response.statusCode(), response.body());
                // Continue anyway - workspace-specific token validation will catch unauthorized access
                return;
            }

            // Parse response to check if user has access to the workspace
            JSONObject result = new JSONObject(response.body());
            JSONArray workspaces = result.getJSONArray("workspaces");

            boolean hasAccess = false;
            for (int i = 0; i < workspaces.length(); i++) {
                JSONObject workspace = workspaces.getJSONObject(i);
                if (workspaceId.equals(workspace.getString("id"))) {
                    hasAccess = true;
                    break;
                }
            }

            if (!hasAccess) {
                LOGGER.warn("User {} does not have access to workspace {}", user.getIdentifier(), workspaceId);
                throw new GuacamoleException("Access denied: User does not have access to workspace " + workspaceId);
            }

            LOGGER.debug("Verified user {} has access to workspace {}", user.getIdentifier(), workspaceId);

        } catch (IOException | InterruptedException ex) {
            LOGGER.warn("Failed to verify workspace access: {}", ex.getMessage());
            // Continue anyway - workspace-specific token validation will catch unauthorized access
        }
    }

    /**
     * Retrieves workspace token from user's session if available.
     *
     * @param user The authenticated user
     * @param workspaceClientId The workspace client ID
     * @return The workspace token if available, null otherwise
     */
    private static String getWorkspaceTokenFromSession(AzureTREAuthenticatedUser user, String workspaceClientId) {
        // Check if user's session contains a workspace token for this workspace
        // This could be stored in session attributes or user credentials
        if (user.getCredentials() != null && user.getCredentials().getRequest() != null) {
            String sessionToken = null;
            if (user.getCredentials().getRequest().getSession(false) != null) {
                sessionToken = (String) user.getCredentials().getRequest().getSession(false)
                    .getAttribute("workspace_token_" + workspaceClientId);
            }
            if (sessionToken != null) {
                LOGGER.debug("Found workspace token in session for client ID: {}", workspaceClientId);
                return sessionToken;
            }
        }

        LOGGER.debug("No workspace token found in session for client ID: {}", workspaceClientId);
        return null;
    }

    /**
     * Handles the workspace authentication callback and exchanges code for token.
     *
     * @param authorizationCode The authorization code from the callback
     * @param workspaceClientId The workspace client ID
     * @param workspaceId The workspace ID
     * @param user The authenticated user
     * @return The workspace access token
     * @throws GuacamoleException If token exchange fails
     */
    public static String handleWorkspaceAuthCallback(String authorizationCode, String workspaceClientId,
            String workspaceId, AzureTREAuthenticatedUser user) throws GuacamoleException {

        // Exchange authorization code for access token
        String workspaceToken = TreApiAuthenticationService.exchangeCodeForWorkspaceToken(
            authorizationCode, workspaceClientId, workspaceId);

        // Store token in user's session for future use
        if (user.getCredentials() != null && user.getCredentials().getRequest() != null) {
            user.getCredentials().getRequest().getSession(true)
                .setAttribute("workspace_token_" + workspaceClientId, workspaceToken);
            LOGGER.debug("Stored workspace token in session for client ID: {}", workspaceClientId);
        }

        return workspaceToken;
    }

}

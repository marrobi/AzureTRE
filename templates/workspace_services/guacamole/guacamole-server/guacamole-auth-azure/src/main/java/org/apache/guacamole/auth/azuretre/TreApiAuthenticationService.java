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

/**
 * Service for handling two-step authentication with Azure TRE API:
 * 1. First authenticate against TRE API to get available workspaces
 * 2. Then authenticate against specific workspace API to get VMs
 */
public class TreApiAuthenticationService {

    private static final Logger LOGGER = LoggerFactory.getLogger(TreApiAuthenticationService.class);

    /**
     * Uses the user's SSO access token to call the TRE API.
     * This is step 1 - authenticate against TRE API to get available workspaces using user's token.
     *
     * @param userToken The user's SSO access token from OpenID Connect extension
     * @return The user's access token (just returns the same token for clarity in flow)
     * @throws GuacamoleException If the token is invalid
     */
    public static String getTreApiToken(String userToken) throws GuacamoleException {
        if (userToken == null || userToken.isEmpty()) {
            LOGGER.error("User SSO token is null or empty");
            throw new GuacamoleException("User not authenticated with SSO");
        }

        LOGGER.debug("Using user SSO token for TRE API access");
        return userToken;
    }

    /**
     * Gets workspace details from TRE API using the user's SSO token and verifies user access.
     * This is step 2 - verify user has access to workspace and get workspace config.
     *
     * @param userToken The user's SSO access token
     * @param workspaceId The workspace ID to get details for
     * @return The workspace details as JSON object
     * @throws GuacamoleException If the workspace cannot be accessed
     */
    public static JSONObject getWorkspaceDetails(String userToken, String workspaceId) throws GuacamoleException {
        try {
            String treApiUrl = System.getenv("TRE_API_URL");
            if (treApiUrl == null) {
                LOGGER.error("TRE_API_URL environment variable not found");
                throw new GuacamoleException("TRE API URL not configured");
            }

            String workspaceUrl = treApiUrl + "/api/workspaces/" + workspaceId;

            HttpClient client = HttpClient.newHttpClient();
            HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(workspaceUrl))
                .header("Authorization", "Bearer " + userToken)
                .timeout(Duration.ofSeconds(10))
                .GET()
                .build();

            HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());

            if (response.statusCode() == 403) {
                LOGGER.warn("User does not have access to workspace: {}", workspaceId);
                throw new GuacamoleException("Access denied to workspace: " + workspaceId);
            } else if (response.statusCode() != 200) {
                LOGGER.error("Failed to get workspace details for {}. Status: {}, Response: {}",
                    workspaceId, response.statusCode(), response.body());
                throw new GuacamoleException("Failed to get workspace details");
            }

            JSONObject workspaceDetails = new JSONObject(response.body());
            LOGGER.debug("Successfully retrieved workspace details for: {}", workspaceId);
            return workspaceDetails;

        } catch (IOException | InterruptedException ex) {
            LOGGER.error("Error getting workspace details for workspace: " + workspaceId, ex);
            throw new GuacamoleException("Error getting workspace details: " + ex.getMessage());
        }
    }

    /**
     * Initiates browser-based authentication flow for workspace API access.
     * This is step 3 - redirect user to authenticate against workspace-specific Azure AD application.
     *
     * @param workspaceClientId The workspace client ID from workspace details
     * @param workspaceId The workspace ID (for logging purposes)
     * @return The redirect URL for workspace authentication
     * @throws GuacamoleException If the authentication URL cannot be constructed
     */
    public static String getWorkspaceAuthenticationUrl(String workspaceClientId, String workspaceId) throws GuacamoleException {
        try {
            if (workspaceClientId == null || workspaceClientId.isEmpty()) {
                LOGGER.error("Workspace client ID is null or empty for workspace: {}", workspaceId);
                throw new GuacamoleException("Workspace client ID not found in workspace details");
            }

            // Get the tenant ID and redirect URI from environment
            String tenantId = System.getenv("AZURE_TENANT_ID");
            String redirectUri = System.getenv("WORKSPACE_REDIRECT_URI");

            if (tenantId == null || redirectUri == null) {
                LOGGER.error("Required environment variables not found: AZURE_TENANT_ID or WORKSPACE_REDIRECT_URI");
                throw new GuacamoleException("Workspace authentication configuration incomplete");
            }

            // Construct Azure AD authorization URL for workspace-specific application
            String scope = "api://" + workspaceClientId + "/user_impersonation";
            String authUrl = String.format(
                "https://login.microsoftonline.com/%s/oauth2/v2.0/authorize?" +
                "client_id=%s&response_type=code&redirect_uri=%s&scope=%s&state=%s",
                tenantId, workspaceClientId, redirectUri, scope, workspaceId
            );

            LOGGER.debug("Generated workspace authentication URL for workspace: {} with client ID: {}",
                workspaceId, workspaceClientId);
            return authUrl;

        } catch (Exception ex) {
            LOGGER.error("Error generating workspace authentication URL for workspace: " + workspaceId, ex);
            throw new GuacamoleException("Error generating workspace authentication URL: " + ex.getMessage());
        }
    }

    /**
     * Exchanges authorization code for workspace API access token.
     * This completes the workspace authentication flow after user returns from browser.
     *
     * @param authorizationCode The authorization code from the callback
     * @param workspaceClientId The workspace client ID
     * @param workspaceId The workspace ID (for logging purposes)
     * @return The access token for workspace API
     * @throws GuacamoleException If the token exchange fails
     */
    public static String exchangeCodeForWorkspaceToken(String authorizationCode, String workspaceClientId, String workspaceId) throws GuacamoleException {
        try {
            String tenantId = System.getenv("AZURE_TENANT_ID");
            String clientSecret = System.getenv("WORKSPACE_CLIENT_SECRET");
            String redirectUri = System.getenv("WORKSPACE_REDIRECT_URI");

            if (tenantId == null || clientSecret == null || redirectUri == null) {
                LOGGER.error("Required environment variables not found for token exchange");
                throw new GuacamoleException("Workspace token exchange configuration incomplete");
            }

            String tokenUrl = String.format("https://login.microsoftonline.com/%s/oauth2/v2.0/token", tenantId);
            String scope = "api://" + workspaceClientId + "/user_impersonation";

            // Prepare form data for token exchange
            String formData = String.format(
                "grant_type=authorization_code&client_id=%s&client_secret=%s&code=%s&redirect_uri=%s&scope=%s",
                workspaceClientId, clientSecret, authorizationCode, redirectUri, scope
            );

            HttpClient client = HttpClient.newHttpClient();
            HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(tokenUrl))
                .header("Content-Type", "application/x-www-form-urlencoded")
                .timeout(Duration.ofSeconds(10))
                .POST(HttpRequest.BodyPublishers.ofString(formData))
                .build();

            HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());

            if (response.statusCode() != 200) {
                LOGGER.error("Failed to exchange code for workspace token. Status: {}, Response: {}",
                    response.statusCode(), response.body());
                throw new GuacamoleException("Failed to exchange authorization code for workspace token");
            }

            JSONObject tokenResponse = new JSONObject(response.body());
            String accessToken = tokenResponse.getString("access_token");
            LOGGER.debug("Successfully obtained workspace API token for workspace: {} with client ID: {}",
                workspaceId, workspaceClientId);
            return accessToken;

        } catch (IOException | InterruptedException ex) {
            LOGGER.error("Error exchanging code for workspace token for workspace: " + workspaceId, ex);
            throw new GuacamoleException("Error exchanging code for workspace token: " + ex.getMessage());
        }
    }

    /**
     * Extracts the workspace ID from the current request URL path.
     * Supports multiple URL patterns:
     * 1. /guacamole/workspace/{workspaceId}/...
     * 2. /guacamole/#/client/workspace/{workspaceId}/...
     * 3. Query parameter: ?workspace_id=...
     *
     * @param requestPath The request path
     * @return The workspace ID if found, or default workspace ID from environment
     */
    public static String extractWorkspaceIdFromPath(String requestPath) {
        if (requestPath != null) {
            LOGGER.debug("Extracting workspace ID from path: {}", requestPath);

            // Pattern 1: /guacamole/workspace/{workspaceId}/
            if (requestPath.contains("/guacamole/workspace/")) {
                try {
                    String[] pathParts = requestPath.split("/guacamole/workspace/");
                    if (pathParts.length > 1) {
                        String workspaceIdPart = pathParts[1];
                        // Extract just the workspace ID (before any additional path segments or query params)
                        String[] workspaceParts = workspaceIdPart.split("[/?]");
                        if (workspaceParts.length > 0 && !workspaceParts[0].isEmpty()) {
                            LOGGER.debug("Extracted workspace ID from /guacamole/workspace/ path: {}", workspaceParts[0]);
                            return workspaceParts[0];
                        }
                    }
                } catch (Exception e) {
                    LOGGER.warn("Failed to extract workspace ID from /guacamole/workspace/ path: {}", requestPath, e);
                }
            }

            // Pattern 2: Traditional Guacamole client URL pattern
            if (requestPath.contains("/workspace/")) {
                try {
                    String[] pathParts = requestPath.split("/workspace/");
                    if (pathParts.length > 1) {
                        String workspaceIdPart = pathParts[1];
                        // Extract just the workspace ID (before any additional path segments)
                        String[] workspaceParts = workspaceIdPart.split("/");
                        if (workspaceParts.length > 0 && !workspaceParts[0].isEmpty()) {
                            LOGGER.debug("Extracted workspace ID from traditional path: {}", workspaceParts[0]);
                            return workspaceParts[0];
                        }
                    }
                } catch (Exception e) {
                    LOGGER.warn("Failed to extract workspace ID from traditional path: {}", requestPath, e);
                }
            }
        }

        // Fall back to environment variable
        String defaultWorkspaceId = System.getenv("WORKSPACE_ID");
        LOGGER.debug("Using default workspace ID from environment: {}", defaultWorkspaceId);
        return defaultWorkspaceId;
    }
}

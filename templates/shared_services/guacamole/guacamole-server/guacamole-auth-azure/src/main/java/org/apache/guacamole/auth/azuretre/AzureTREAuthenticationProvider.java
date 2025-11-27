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

import com.auth0.jwk.UrlJwkProvider;
import com.google.common.base.Strings;
import org.apache.guacamole.GuacamoleException;
import org.apache.guacamole.auth.azuretre.connection.ConnectionService;
import org.apache.guacamole.auth.azuretre.user.AzureTREAuthenticatedUser;
import org.apache.guacamole.auth.azuretre.user.TreUserContext;
import org.apache.guacamole.net.auth.AbstractAuthenticationProvider;
import org.apache.guacamole.net.auth.AuthenticatedUser;
import org.apache.guacamole.net.auth.Connection;
import org.apache.guacamole.net.auth.Credentials;
import org.apache.guacamole.net.auth.UserContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.net.MalformedURLException;
import java.net.URL;
import java.util.Map;

/**
 * Authentication provider that integrates Guacamole with Azure TRE.
 * This provider supports both:
 * - Static mode: Uses AUDIENCE, ISSUER, and OAUTH2_PROXY_JWKS_ENDPOINT from env vars
 * - Dynamic mode: Extracts workspace ID from request and fetches auth config from API
 */
public final class AzureTREAuthenticationProvider
    extends AbstractAuthenticationProvider {

    /** Root connection group identifier. */
    public static final String ROOT_CONNECTION_GROUP = "ROOT";

    /** Header name for workspace ID in shared service mode. */
    private static final String WORKSPACE_ID_HEADER = "X-Workspace-Id";

    /** Logger for provider actions. */
    private static final Logger LOGGER = LoggerFactory.getLogger(
        AzureTREAuthenticationProvider.class);

    /** Service responsible for token validation. */
    private final AuthenticationProviderService authenticationProviderService;

    /**
     * Creates a provider with a default authentication service.
     */
    public AzureTREAuthenticationProvider() {
        this.authenticationProviderService =
            new AuthenticationProviderService();
    }

    /**
     * Creates a provider with the given authentication service.
     *
     * @param providerService optional service override.
     */
    public AzureTREAuthenticationProvider(
        final AuthenticationProviderService providerService) {
        if (providerService == null) {
            this.authenticationProviderService =
                new AuthenticationProviderService();
        } else {
            this.authenticationProviderService = providerService;
        }
    }

    @Override
    public String getIdentifier() {
        return "azuretre";
    }

    @Override
    public AuthenticatedUser updateAuthenticatedUser(
        final AuthenticatedUser authenticatedUser,
        final Credentials credentials) throws GuacamoleException {
        return authenticateUser(credentials);
    }

    @Override
    public AzureTREAuthenticatedUser authenticateUser(
        final Credentials credentials) {
        final var requestDetails = credentials.getRequestDetails();
        final String accessToken = requestDetails.getHeader(
            "X-Forwarded-Access-Token");
        final String prefUsername = requestDetails.getHeader(
            "X-Forwarded-Preferred-Username");

        if (Strings.isNullOrEmpty(accessToken)) {
            LOGGER.error("Access token was not provided");
            return null;
        }
        if (Strings.isNullOrEmpty(prefUsername)) {
            LOGGER.error("Preferred username missing from headers");
            return null;
        }

        // Try to get workspace ID from header or URI
        String workspaceId = requestDetails.getHeader(WORKSPACE_ID_HEADER);
        if (Strings.isNullOrEmpty(workspaceId)) {
            // Try to extract from X-Original-URI header (set by reverse proxy)
            final String originalUri = requestDetails.getHeader("X-Original-URI");
            if (!Strings.isNullOrEmpty(originalUri)) {
                workspaceId = WorkspaceAuthConfigService.extractWorkspaceIdFromUri(
                    originalUri);
            }
        }

        return new AzureTREAuthenticatedUser(
            credentials,
            accessToken,
            prefUsername,
            workspaceId,
            this);
    }

    @Override
    public UserContext getUserContext(
        final AuthenticatedUser authenticatedUser)
        throws GuacamoleException {
        if (!(authenticatedUser instanceof AzureTREAuthenticatedUser)) {
            return null;
        }

        final AzureTREAuthenticatedUser user =
            (AzureTREAuthenticatedUser) authenticatedUser;
        final String accessToken = user.getAccessToken();
        final String workspaceId = user.getWorkspaceId();

        try {
            LOGGER.info("Validating token");

            // Check if we're in shared service mode (dynamic workspace auth)
            if (!Strings.isNullOrEmpty(workspaceId) && isSharedServiceMode()) {
                LOGGER.info("Using dynamic workspace auth for workspace {}",
                    workspaceId);
                validateTokenWithDynamicConfig(accessToken, workspaceId);
            } else {
                // Static mode - use environment variables
                final UrlJwkProvider jwkProvider = new UrlJwkProvider(
                    buildJwksEndpointUrl());
                authenticationProviderService.validateToken(
                    accessToken,
                    jwkProvider);
            }
        } catch (final Exception ex) {
            LOGGER.error("Failed to validate token: {}", ex.getMessage());
            LOGGER.debug("Token validation failure", ex);
            return null;
        }

        final Map<String, Connection> connections =
            ConnectionService.getConnections(user);
        final TreUserContext treUserContext = new TreUserContext(
            this,
            connections);
        treUserContext.init(user);
        return treUserContext;
    }

    /**
     * Validates the token using dynamic workspace auth configuration.
     *
     * @param accessToken   the access token to validate.
     * @param workspaceId   the workspace ID for auth config lookup.
     * @throws GuacamoleException if validation fails.
     */
    private void validateTokenWithDynamicConfig(
        final String accessToken,
        final String workspaceId) throws GuacamoleException {

        // Get workspace auth config from the API
        final WorkspaceAuthConfigService.WorkspaceAuthConfig authConfig =
            WorkspaceAuthConfigService.getWorkspaceAuthConfig(
                workspaceId,
                accessToken);

        // Validate the token using workspace-specific configuration
        try {
            final UrlJwkProvider jwkProvider = new UrlJwkProvider(
                new URL(authConfig.getJwksEndpoint()));

            authenticationProviderService.validateTokenWithConfig(
                accessToken,
                jwkProvider,
                authConfig.getClientId(),
                authConfig.getIssuer());
        } catch (final MalformedURLException ex) {
            LOGGER.error("Invalid JWKS endpoint URL: {}",
                authConfig.getJwksEndpoint());
            throw new GuacamoleException("Invalid JWKS endpoint URL");
        }
    }

    /**
     * Determines if the provider is running in shared service mode.
     * In shared service mode, AUDIENCE and ISSUER are not set and
     * authentication is done dynamically per workspace.
     *
     * @return true if running in shared service mode.
     */
    private boolean isSharedServiceMode() {
        final String sharedModeEnv = System.getenv("GUACAMOLE_SHARED_SERVICE_MODE");
        if (!Strings.isNullOrEmpty(sharedModeEnv)) {
            return Boolean.parseBoolean(sharedModeEnv);
        }
        // If AUDIENCE/ISSUER are not set, assume shared service mode
        final String audience = System.getenv("AUDIENCE");
        final String issuer = System.getenv("ISSUER");
        return Strings.isNullOrEmpty(audience) || Strings.isNullOrEmpty(issuer);
    }

    @Override
    public UserContext updateUserContext(
        final UserContext context,
        final AuthenticatedUser authenticatedUser,
        final Credentials credentials) throws GuacamoleException {
        return getUserContext(authenticatedUser);
    }

    private URL buildJwksEndpointUrl() throws MalformedURLException {
        return new URL(System.getenv("OAUTH2_PROXY_JWKS_ENDPOINT"));
    }
}

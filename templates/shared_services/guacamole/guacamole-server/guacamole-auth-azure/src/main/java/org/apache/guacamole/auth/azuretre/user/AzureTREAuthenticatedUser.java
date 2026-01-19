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

package org.apache.guacamole.auth.azuretre.user;

import org.apache.guacamole.net.auth.AbstractAuthenticatedUser;
import org.apache.guacamole.net.auth.AuthenticationProvider;
import org.apache.guacamole.net.auth.Credentials;

/**
 * Authenticated user implementation that retains TRE-specific context.
 * In shared service mode, this holds both the Core API token (for fetching
 * workspace details) and the workspace token (for VM access).
 */
public final class AzureTREAuthenticatedUser extends AbstractAuthenticatedUser {

    /** Provider that authenticated the user. */
    private final AuthenticationProvider authProvider;

    /** Credentials originally supplied by the user. */
    private final Credentials credentials;

    /** Workspace ID for shared service mode. */
    private final String workspaceId;

    /** Workspace-scoped access token for VM access. */
    private final String accessToken;

    /** Core API-scoped access token for fetching workspace details. */
    private final String coreApiToken;

    /**
     * Creates a new authenticated user.
     *
     * @param originalCredentials original credentials from the client.
     * @param bearerToken         workspace-scoped access token.
     * @param coreToken           Core API-scoped access token (can be null for static mode).
     * @param username            preferred username for the user.
     * @param wsId                workspace ID for shared service mode (can be null).
     * @param provider            provider that authenticated the user.
     */
    public AzureTREAuthenticatedUser(
        final Credentials originalCredentials,
        final String bearerToken,
        final String coreToken,
        final String username,
        final String wsId,
        final AuthenticationProvider provider) {
        this.credentials = originalCredentials;
        this.accessToken = bearerToken;
        this.coreApiToken = coreToken;
        this.workspaceId = wsId;
        this.authProvider = provider;
        setIdentifier(username.toLowerCase());
    }

    @Override
    public AuthenticationProvider getAuthenticationProvider() {
        return authProvider;
    }

    @Override
    public Credentials getCredentials() {
        return credentials;
    }

    /**
     * Returns the workspace-scoped bearer token for VM access.
     *
     * @return the workspace access token string.
     */
    public String getAccessToken() {
        return accessToken;
    }

    /**
     * Returns the Core API-scoped access token.
     * Used to fetch workspace details in shared service mode.
     *
     * @return the Core API token, or {@code null} if not in shared service mode.
     */
    public String getCoreApiToken() {
        return coreApiToken;
    }

    /**
     * Returns the workspace ID associated with this request.
     * This is used in shared service mode to determine which workspace
     * authentication configuration to use.
     *
     * @return workspace ID value, or {@code null} if not in shared service mode.
     */
    public String getWorkspaceId() {
        return workspaceId;
    }

    /**
     * Returns the Azure AD object identifier associated with the user.
     * Kept for backwards compatibility but returns null in shared service mode.
     *
     * @return object identifier value, or {@code null} if unavailable.
     * @deprecated Use getWorkspaceId() for shared service mode.
     */
    @Deprecated
    public String getObjectId() {
        return null;
    }
}

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

import com.auth0.jwk.Jwk;
import com.auth0.jwk.UrlJwkProvider;
import com.auth0.jwt.JWT;
import com.auth0.jwt.JWTVerifier;
import com.auth0.jwt.algorithms.Algorithm;
import com.auth0.jwt.interfaces.Claim;
import com.auth0.jwt.interfaces.DecodedJWT;
import com.google.common.base.Strings;
import org.apache.guacamole.net.auth.credentials.CredentialsInfo;
import org.apache.guacamole.net.auth.credentials.GuacamoleInvalidCredentialsException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.apache.guacamole.GuacamoleException;

import java.net.URI;
import java.net.URISyntaxException;
import java.security.interfaces.RSAPublicKey;
import java.util.List;

public class AuthenticationProviderService {

  private static final Logger LOGGER = LoggerFactory.getLogger(AzureTREAuthenticationProvider.class);

  public void validateToken(final String token, final UrlJwkProvider jwkProvider)
      throws GuacamoleInvalidCredentialsException {

    try {
      if (System.getenv("AUDIENCE").length() == 0) {
        throw new Exception("AUDIENCE is not provided");
      }
      if (System.getenv("ISSUER").length() == 0) {
        throw new Exception("ISSUER is not provided");
      }

      final Jwk jwk = jwkProvider.get(JWT.decode(token).getKeyId());
      final Algorithm algorithm = Algorithm.RSA256((RSAPublicKey) jwk.getPublicKey(), null);
      final JWTVerifier verifier = JWT.require(algorithm)
          .withAudience(System.getenv("AUDIENCE"))
          .withClaimPresence("roles")
          .withIssuer(System.getenv("ISSUER"))
          .build();

      final DecodedJWT jwt = verifier.verify(token);
      // Since we verify we have the correct Audience we validate the token if at
      // least one role is present, no
      // matter which one.
      final Claim roles = jwt.getClaim("roles");
      if (roles == null || roles.isNull() || roles.asArray(Object.class).length == 0) {
        throw new GuacamoleInvalidCredentialsException(
            "Token must contain a 'roles' claim", CredentialsInfo.USERNAME_PASSWORD);
      }

      // Additional role validation - check for specific roles
      List<String> rolesList = roles.asList(String.class);
      if (rolesList.stream().noneMatch(role -> role.equalsIgnoreCase("WorkspaceOwner")
          || role.equalsIgnoreCase("WorkspaceResearcher")
          || role.equalsIgnoreCase("AirlockManager"))) {
        throw new GuacamoleInvalidCredentialsException(
            "User must have a workspace owner or workspace researcher or Airlock Manager role",
            CredentialsInfo.USERNAME_PASSWORD);
      }

    } catch (Exception e) {
      throw new GuacamoleInvalidCredentialsException(
          "Token validation failed: " + e.getMessage(), CredentialsInfo.USERNAME_PASSWORD);
    }
  }

  /**
   * Generates workspace-specific login URI using the provided workspace client
   * ID.
   * This method builds an authorization URL that uses the workspace's Azure AD
   * app registration
   * instead of the general TRE client ID.
   */
  public URI getWorkspaceLoginURI(String workspaceClientId, String workspaceId) throws GuacamoleException {
    // Get configuration from environment variables with fallback support
    String authorizationEndpoint = System.getenv("GUAC_OPENID_AUTHORIZATION_ENDPOINT");
    if (Strings.isNullOrEmpty(authorizationEndpoint)) {
      authorizationEndpoint = System.getenv("OPENID_AUTHORIZATION_ENDPOINT");
    }

    // Check authorization endpoint first to maintain test compatibility
    if (Strings.isNullOrEmpty(authorizationEndpoint)) {
      throw new GuacamoleException("OPENID_AUTHORIZATION_ENDPOINT is not configured");
    }
    if (Strings.isNullOrEmpty(workspaceClientId)) {
      throw new GuacamoleException("Workspace client ID is required");
    }

    // Use TreConfiguration for consistent redirect URI handling
    String redirectUri = TreConfiguration.getRedirectUri();

    // Generate a simple nonce (in production, this should be more secure)
    String nonce = "nonce-" + System.currentTimeMillis();

    try {
      // Build the workspace-specific authorization URL
      StringBuilder urlBuilder = new StringBuilder(authorizationEndpoint);
      urlBuilder.append("?scope=").append("openid%20profile%20email");
      urlBuilder.append("&client_id=").append(workspaceClientId); // Use workspace client ID
      urlBuilder.append("&redirect_uri=").append(redirectUri);
      urlBuilder.append("&response_type=").append("code");
      urlBuilder.append("&nonce=").append(nonce);

      // Add workspace_client_id as state to preserve it through OAuth flow
      if (!Strings.isNullOrEmpty(workspaceId)) {
        urlBuilder.append("&state=").append(workspaceId);
      }

      LOGGER.debug("Generated workspace login URI for client: {} and workspace: {}", workspaceClientId, workspaceId);
      return new URI(urlBuilder.toString());
    } catch (URISyntaxException e) {
      throw new GuacamoleException("Failed to build workspace authorization URI", e);
    }
  }
}

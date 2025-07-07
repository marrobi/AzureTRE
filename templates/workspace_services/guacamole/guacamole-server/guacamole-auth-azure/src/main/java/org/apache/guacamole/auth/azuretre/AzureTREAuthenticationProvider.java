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
import com.auth0.jwt.JWT;
import com.auth0.jwt.interfaces.DecodedJWT;
import com.google.common.base.Strings;
import org.apache.guacamole.GuacamoleException;
import org.apache.guacamole.auth.azuretre.connection.ConnectionService;
import org.apache.guacamole.auth.azuretre.user.AzureTREAuthenticatedUser;
import org.apache.guacamole.auth.azuretre.user.TreUserContext;
import org.apache.guacamole.net.auth.AbstractAuthenticationProvider;
import org.apache.guacamole.net.auth.AuthenticatedUser;
import org.apache.guacamole.net.auth.Credentials;
import org.apache.guacamole.net.auth.UserContext;
import org.apache.guacamole.net.auth.credentials.CredentialsInfo;
import org.apache.guacamole.net.auth.credentials.GuacamoleInvalidCredentialsException;
import org.apache.guacamole.form.Field;
import org.apache.guacamole.form.RedirectField;
import org.apache.guacamole.language.TranslatableMessage;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.net.URI;
import java.net.URL;
import java.util.Arrays;

public class AzureTREAuthenticationProvider extends AbstractAuthenticationProvider {

  public static final String ROOT_CONNECTION_GROUP = "ROOT";

  private static final Logger LOGGER = LoggerFactory.getLogger(AzureTREAuthenticationProvider.class);

  private final AuthenticationProviderService authenticationProviderService;

  public AzureTREAuthenticationProvider() {
    this.authenticationProviderService = new AuthenticationProviderService();
  }

  public AzureTREAuthenticationProvider(
      AuthenticationProviderService authenticationProviderService) {
    if (authenticationProviderService == null) {
      this.authenticationProviderService = new AuthenticationProviderService();
    } else {
      this.authenticationProviderService = authenticationProviderService;
    }
  }

  @Override
  public String getIdentifier() {
    return "azuretre";
  }

  @Override
  public AuthenticatedUser updateAuthenticatedUser(AuthenticatedUser authenticatedUser, Credentials credentials)
      throws GuacamoleException {
    LOGGER.info("updateAuthenticatedUser");
    AuthenticatedUser updated = authenticateUser(credentials);

    LOGGER.info("updateAuthenticatedUser - done");
    return updated;
  }

  @Override
  public AzureTREAuthenticatedUser authenticateUser(final Credentials credentials) throws GuacamoleException {
    LOGGER.info("Authenticating user - Azure TRE URL-based workspace authentication");

    // Check for workspace_client_id URL parameter first
    String workspaceClientId = credentials.getRequest() != null
        ? credentials.getRequest().getParameter("workspace_client_id")
        : null;

    // If not found in URL parameter, check session state (e.g., OAuth callback)
    if (Strings.isNullOrEmpty(workspaceClientId) && credentials.getRequest() != null) {
      if (credentials.getRequest().getSession(false) != null) {
        workspaceClientId = (String) credentials.getRequest().getSession(false).getAttribute("workspace_client_id");
        if (!Strings.isNullOrEmpty(workspaceClientId)) {
          LOGGER.debug("Found workspace_client_id in session: {}", workspaceClientId);
        }
      }
    }

    if (Strings.isNullOrEmpty(workspaceClientId)) {
      LOGGER.error("No workspace_client_id parameter found in URL or session");
      throw new GuacamoleInvalidCredentialsException(
          "Access denied. This Guacamole instance requires a workspace_client_id parameter. " +
              "Please access through the TRE UI.",
          CredentialsInfo.EMPTY);
    }

    LOGGER.debug("Found workspace_client_id: {}", workspaceClientId);

    // Extract workspace ID from the request URL or parameter
    String workspaceId = null;
    String requestPath = null;
    if (credentials.getRequest() != null) {
      requestPath = credentials.getRequest().getRequestURI();
      workspaceId = TreApiAuthenticationService.extractWorkspaceIdFromPath(requestPath);

      // If not found in path, try URL parameter
      if (Strings.isNullOrEmpty(workspaceId)) {
        workspaceId = credentials.getRequest().getParameter("workspace_id");
        LOGGER.debug("Found workspace_id parameter: {}", workspaceId);
      }

      // If still not found, check session state (e.g., OAuth callback)
      if (Strings.isNullOrEmpty(workspaceId) && credentials.getRequest().getSession(false) != null) {
        workspaceId = (String) credentials.getRequest().getSession(false).getAttribute("workspace_id");
        if (!Strings.isNullOrEmpty(workspaceId)) {
          LOGGER.debug("Found workspace_id in session: {}", workspaceId);
        }
      }
    }

    if (Strings.isNullOrEmpty(workspaceId)) {
      LOGGER.error("Could not extract workspace ID from request path: {} or parameters", requestPath);
      throw new GuacamoleException(
          "Invalid workspace access: workspace ID is required in URL path or as workspace_id parameter");
    }

    LOGGER.debug("Using workspace ID: {} (from path: {})", workspaceId, requestPath);

    // Check if this is a callback from workspace authentication
    String authCode = credentials.getRequest().getParameter("code");
    String state = credentials.getRequest().getParameter("state");

    if (authCode != null && state != null) {
      // This is a workspace authentication callback
      return handleWorkspaceAuthCallback(credentials, authCode, state, workspaceClientId);
    }

    // Check for existing TRE API token from OpenID Connect implicit flow
    String treApiToken = credentials.getRequest().getParameter("id_token");

    if (Strings.isNullOrEmpty(treApiToken)) {
      treApiToken = credentials.getRequest().getParameter("access_token");
    }

    if (Strings.isNullOrEmpty(treApiToken)) {
      // No token found, initiate workspace-specific authentication
      LOGGER.debug("No TRE API token found, initiating workspace authentication for client: {}", workspaceClientId);

      try {
        URI loginUri = authenticationProviderService.getWorkspaceLoginURI(workspaceClientId, workspaceId);
        LOGGER.info("Workspace authentication required. Login URI: {}", loginUri.toString());

        // Store workspace context in session for callback
        if (credentials.getRequest() != null && credentials.getRequest().getSession(true) != null) {
          credentials.getRequest().getSession(true).setAttribute("workspace_client_id", workspaceClientId);
          credentials.getRequest().getSession(true).setAttribute("workspace_id", workspaceId);
          credentials.getRequest().getSession(true).setAttribute("login_uri", loginUri.toString());
        }

        // For compatibility with tests, include redirect URL in exception message
        // Also provide RedirectField for proper Guacamole integration
        throw new GuacamoleInvalidCredentialsException(
            "Workspace authentication required. Redirect to: " + loginUri.toString(),
            new CredentialsInfo(Arrays.asList(new Field[] {
                new RedirectField("workspace_auth", loginUri,
                    new TranslatableMessage("LOGIN.INFO_IDP_REDIRECT_PENDING",
                        "Redirecting to workspace authentication..."))
            })));

      } catch (GuacamoleInvalidCredentialsException e) {
        // Re-throw the credentials exception
        throw e;
      } catch (Exception e) {
        LOGGER.error("Failed to initiate workspace authentication for client: {}", workspaceClientId, e);

        // Try to build an error redirect to TRE UI
        try {
          String errorRedirectUrl = TreConfiguration.buildErrorRedirectUrl(workspaceId,
              "Authentication configuration error. Please contact your administrator.");
          throw new GuacamoleInvalidCredentialsException(
              "Authentication failed. Please return to TRE UI: " + errorRedirectUrl,
              CredentialsInfo.EMPTY);
        } catch (Exception redirectEx) {
          // Fallback to simple error message
          throw new GuacamoleInvalidCredentialsException(
              "Authentication failed. Please access through the TRE UI with workspace_client_id parameter.",
              CredentialsInfo.EMPTY);
        }
      }
    }

    // Validate the TRE API token
    try {
      String jwksUri = System.getenv("JWKS_URI");
      if (Strings.isNullOrEmpty(jwksUri)) {
        throw new GuacamoleException("JWKS_URI not configured");
      }

      UrlJwkProvider jwkProvider = new UrlJwkProvider(new URL(jwksUri));
      authenticationProviderService.validateToken(treApiToken, jwkProvider);

      // Extract user information from token
      DecodedJWT jwt = JWT.decode(treApiToken);
      String username = jwt.getClaim("preferred_username").asString();
      String objectId = jwt.getClaim("oid").asString();

      if (Strings.isNullOrEmpty(username)) {
        username = jwt.getClaim("upn").asString();
      }
      if (Strings.isNullOrEmpty(username)) {
        username = jwt.getSubject();
      }

      LOGGER.debug("Successfully authenticated user: {} with workspace client ID: {}", username, workspaceClientId);

      // Create authenticated user with TRE API token and workspace context
      AzureTREAuthenticatedUser authenticatedUser = new AzureTREAuthenticatedUser(credentials, treApiToken, username,
          objectId, this);

      // Store workspace client ID in session for future use
      if (credentials.getRequest().getSession(true) != null) {
        credentials.getRequest().getSession(true).setAttribute("workspace_client_id_" + workspaceId, workspaceClientId);
        credentials.getRequest().getSession(true).setAttribute("tre_api_token", treApiToken);
      }

      return authenticatedUser;

    } catch (Exception ex) {
      LOGGER.error("Token validation failed for workspace client: {}", workspaceClientId, ex);
      throw new GuacamoleInvalidCredentialsException("Invalid token", CredentialsInfo.EMPTY);
    }
  }

  /**
   * Handles workspace authentication callback after user returns from workspace
   * OAuth flow.
   * This method processes the authorization code and exchanges it for access
   * tokens.
   */
  private AzureTREAuthenticatedUser handleWorkspaceAuthCallback(Credentials credentials,
      String authCode, String state, String workspaceClientId) throws GuacamoleException {

    String workspaceId = state; // State parameter contains workspace ID

    // Additional fallback: if workspaceClientId is still empty, try session
    if (Strings.isNullOrEmpty(workspaceClientId) && credentials.getRequest().getSession(false) != null) {
      workspaceClientId = (String) credentials.getRequest().getSession(false).getAttribute("workspace_client_id");
      LOGGER.debug("Retrieved workspace_client_id from session for callback: {}", workspaceClientId);
    }

    if (Strings.isNullOrEmpty(workspaceClientId)) {
      throw new GuacamoleException(
          "Missing workspace_client_id for authentication callback. Session may have expired.");
    }

    LOGGER.debug("Handling workspace authentication callback for workspace: {} with client ID: {}", workspaceId,
        workspaceClientId);

    try {
      LOGGER.debug("Exchanging authorization code for workspace token: client={}, workspace={}", workspaceClientId,
          workspaceId);

      // Exchange code for workspace token with enhanced error handling
      String workspaceToken = TreApiAuthenticationService.exchangeCodeForWorkspaceToken(
          authCode, workspaceClientId, workspaceId);

      if (Strings.isNullOrEmpty(workspaceToken)) {
        throw new GuacamoleException("Failed to retrieve workspace token: empty token received");
      }

      LOGGER.debug("Successfully obtained workspace token for client: {}", workspaceClientId);

      // Store workspace token in session with proper key management
      if (credentials.getRequest().getSession(true) != null) {
        credentials.getRequest().getSession(true)
            .setAttribute("workspace_token_" + workspaceClientId, workspaceToken);
        credentials.getRequest().getSession(true)
            .setAttribute("workspace_auth_completed_" + workspaceId, true);
        LOGGER.debug("Stored workspace token in session for future use");
      }

      // Get user info from workspace token
      DecodedJWT jwt = JWT.decode(workspaceToken);
      String username = extractUsername(jwt);
      String objectId = jwt.getClaim("oid").asString();

      if (Strings.isNullOrEmpty(username)) {
        throw new GuacamoleException("Unable to extract username from TRE API token");
      }

      LOGGER.info("Successfully completed workspace authentication for user: {} with client ID: {}", username,
          workspaceClientId);

      // Create authenticated user with enhanced context
      AzureTREAuthenticatedUser authenticatedUser = new AzureTREAuthenticatedUser(credentials, workspaceToken, username,
          objectId, this);

      // Store additional context for future operations
      if (credentials.getRequest().getSession(true) != null) {
        credentials.getRequest().getSession(true).setAttribute("last_workspace_client_id", workspaceClientId);
        credentials.getRequest().getSession(true).setAttribute("last_workspace_id", workspaceId);
      }

      return authenticatedUser;

    } catch (GuacamoleException e) {
      // Re-throw GuacamoleExceptions as-is
      throw e;
    } catch (Exception ex) {
      LOGGER.error("Workspace authentication callback failed for client: {} with code: {}", workspaceClientId, authCode,
          ex);
      throw new GuacamoleException("Workspace authentication failed: " + ex.getMessage());
    }
  }

  /**
   * Extract username from JWT token with multiple fallback strategies.
   */
  private String extractUsername(DecodedJWT jwt) {
    String username = jwt.getClaim("preferred_username").asString();

    if (Strings.isNullOrEmpty(username)) {
      username = jwt.getClaim("upn").asString();
    }
    if (Strings.isNullOrEmpty(username)) {
      username = jwt.getClaim("email").asString();
    }
    if (Strings.isNullOrEmpty(username)) {
      username = jwt.getSubject();
    }

    return username;
  }

  @Override
  public UserContext getUserContext(final AuthenticatedUser authenticatedUser) throws GuacamoleException {
    LOGGER.debug("Getting user context for Azure TRE unified authentication.");

    if (authenticatedUser == null) {
      LOGGER.warn("No authenticated user provided");
      return null;
    }

    if (!(authenticatedUser instanceof AzureTREAuthenticatedUser)) {
      LOGGER.warn("User not authenticated via Azure TRE extension");
      return null;
    }

    AzureTREAuthenticatedUser treUser = (AzureTREAuthenticatedUser) authenticatedUser;
    String username = treUser.getIdentifier();

    LOGGER.info("Processing Azure TRE user context for user: {}", username);

    // Store TRE API token in session for workspace authentication flow
    if (treUser.getCredentials() != null && treUser.getCredentials().getRequest() != null) {
      treUser.getCredentials().getRequest().getSession(true)
          .setAttribute("tre_api_token", treUser.getAccessToken());
    }

    try {
      LOGGER.debug("Getting VM configurations from Azure TRE API with unified authentication flow.");
      var connections = ConnectionService.getConnections(treUser);

      LOGGER.debug("Creating Azure TRE user context.");
      final TreUserContext treUserContext = new TreUserContext(this, connections);
      treUserContext.init(treUser);

      LOGGER.debug("Azure TRE user context created successfully for user: {}", username);
      return treUserContext;

    } catch (GuacamoleException ex) {
      // Check if this is a workspace authentication required exception
      if (ex.getMessage() != null && ex.getMessage().startsWith("WORKSPACE_AUTH_REQUIRED:")) {
        String authUrl = ex.getMessage().substring("WORKSPACE_AUTH_REQUIRED:".length());
        LOGGER.info("Workspace authentication required for user: {}, redirecting to: {}", username, authUrl);

        // Extract workspace info and store in session for callback
        String workspaceId = extractWorkspaceIdFromAuthUrl(authUrl);
        String workspaceClientId = extractWorkspaceClientIdFromAuthUrl(authUrl);

        if (treUser.getCredentials() != null && treUser.getCredentials().getRequest() != null) {
          treUser.getCredentials().getRequest().getSession(true)
              .setAttribute("workspace_client_id_" + workspaceId, workspaceClientId);
        }

        // Use standard RedirectField approach
        try {
          URI redirectUri = new URI(authUrl);
          throw new GuacamoleInvalidCredentialsException(
              "Workspace authentication required.",
              new CredentialsInfo(Arrays.asList(new Field[] {
                  new RedirectField("workspace_auth", redirectUri,
                      new TranslatableMessage("LOGIN.INFO_IDP_REDIRECT_PENDING",
                          "Redirecting to workspace authentication..."))
              })));
        } catch (Exception uriEx) {
          throw new GuacamoleException("Failed to create workspace auth redirect: " + uriEx.getMessage());
        }
      }

      // Re-throw other exceptions
      throw ex;
    }
  }

  /**
   * Extracts workspace ID from the authentication URL state parameter.
   */
  private String extractWorkspaceIdFromAuthUrl(String authUrl) {
    // The workspace ID should be in the state parameter
    try {
      URI uri = new URI(authUrl);
      String query = uri.getQuery();
      if (query != null) {
        String[] params = query.split("&");
        for (String param : params) {
          if (param.startsWith("state=")) {
            return param.substring(6); // Remove "state="
          }
        }
      }
    } catch (Exception ex) {
      LOGGER.warn("Failed to extract workspace ID from auth URL: {}", authUrl, ex);
    }
    return "default";
  }

  /**
   * Extracts workspace client ID from the authentication URL client_id parameter.
   */
  private String extractWorkspaceClientIdFromAuthUrl(String authUrl) {
    try {
      URI uri = new URI(authUrl);
      String query = uri.getQuery();
      if (query != null) {
        String[] params = query.split("&");
        for (String param : params) {
          if (param.startsWith("client_id=")) {
            return param.substring(10); // Remove "client_id="
          }
        }
      }
    } catch (Exception ex) {
      LOGGER.warn("Failed to extract client ID from auth URL: {}", authUrl, ex);
    }
    return null;
  }

  @Override
  public UserContext updateUserContext(UserContext context, AuthenticatedUser authenticatedUser,
      Credentials credentials)
      throws GuacamoleException {
    LOGGER.debug("Updating usercontext");
    var userContext = getUserContext(authenticatedUser);

    return userContext;
  }
}

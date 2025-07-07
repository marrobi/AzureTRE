package org.apache.guacamole.auth.azuretre;

import com.google.common.base.Strings;
import org.apache.guacamole.GuacamoleException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.net.URI;
import java.net.URISyntaxException;

/**
 * Configuration management for Azure TRE settings with enhanced redirect URL handling.
 */
public class TreConfiguration {

    private static final Logger LOGGER = LoggerFactory.getLogger(TreConfiguration.class);

    // Environment variable names
    public static final String TRE_URL_ENV = "TRE_URL";
    public static final String API_URL_ENV = "API_URL";
    public static final String OPENID_REDIRECT_URI_ENV = "OPENID_REDIRECT_URI";
    public static final String GUAC_OPENID_REDIRECT_URI_ENV = "GUAC_OPENID_REDIRECT_URI";

    private static String treBaseUrl = null;
    private static String redirectUri = null;

    /**
     * Get the base TRE URL from environment configuration.
     *
     * @return The base TRE URL
     * @throws GuacamoleException if TRE URL is not configured
     */
    public static String getTreBaseUrl() throws GuacamoleException {
        if (treBaseUrl == null) {
            // Try TRE_URL first, then fall back to API_URL
            treBaseUrl = System.getenv(TRE_URL_ENV);
            if (Strings.isNullOrEmpty(treBaseUrl)) {
                treBaseUrl = System.getenv(API_URL_ENV);
            }

            if (Strings.isNullOrEmpty(treBaseUrl)) {
                throw new GuacamoleException("TRE base URL not configured. Please set TRE_URL or API_URL environment variable.");
            }

            // Ensure URL doesn't end with slash for consistent handling
            if (treBaseUrl.endsWith("/")) {
                treBaseUrl = treBaseUrl.substring(0, treBaseUrl.length() - 1);
            }

            LOGGER.debug("Using TRE base URL: {}", treBaseUrl);
        }
        return treBaseUrl;
    }

    /**
     * Get the redirect URI for Guacamole authentication.
     *
     * @return The redirect URI
     * @throws GuacamoleException if redirect URI cannot be determined
     */
    public static String getRedirectUri() throws GuacamoleException {
        if (redirectUri == null) {
            // Try GUAC_OPENID_REDIRECT_URI first, then OPENID_REDIRECT_URI
            redirectUri = System.getenv(GUAC_OPENID_REDIRECT_URI_ENV);
            if (Strings.isNullOrEmpty(redirectUri)) {
                redirectUri = System.getenv(OPENID_REDIRECT_URI_ENV);
            }

            // If not explicitly set, construct from TRE_URL
            if (Strings.isNullOrEmpty(redirectUri)) {
                String baseUrl = getTreBaseUrl();
                redirectUri = baseUrl + "/guacamole/";
                LOGGER.debug("Constructed redirect URI from TRE_URL: {}", redirectUri);
            }

            // Validate the redirect URI
            try {
                new URI(redirectUri);
            } catch (URISyntaxException e) {
                throw new GuacamoleException("Invalid redirect URI: " + redirectUri, e);
            }

            LOGGER.debug("Using redirect URI: {}", redirectUri);
        }
        return redirectUri;
    }

    /**
     * Build a workspace-specific redirect URL for the TRE UI.
     *
     * @param workspaceId The workspace ID
     * @param workspaceClientId The workspace client ID
     * @return The TRE UI redirect URL
     * @throws GuacamoleException if URL cannot be constructed
     */
    public static String buildTreWorkspaceRedirectUrl(String workspaceId, String workspaceClientId) throws GuacamoleException {
        String baseUrl = getTreBaseUrl();

        // Construct the TRE UI workspace URL
        // Format: {TRE_URL}/workspaces/{workspaceId}/guacamole?workspace_client_id={clientId}
        StringBuilder urlBuilder = new StringBuilder(baseUrl);
        urlBuilder.append("/workspaces/").append(workspaceId);
        urlBuilder.append("/guacamole?workspace_client_id=").append(workspaceClientId);

        String redirectUrl = urlBuilder.toString();
        LOGGER.debug("Built TRE workspace redirect URL: {}", redirectUrl);

        return redirectUrl;
    }

    /**
     * Build an error redirect URL for authentication failures.
     *
     * @param workspaceId The workspace ID (optional)
     * @param errorMessage The error message to include
     * @return The error redirect URL
     * @throws GuacamoleException if URL cannot be constructed
     */
    public static String buildErrorRedirectUrl(String workspaceId, String errorMessage) throws GuacamoleException {
        String baseUrl = getTreBaseUrl();

        try {
            StringBuilder urlBuilder = new StringBuilder(baseUrl);
            if (!Strings.isNullOrEmpty(workspaceId)) {
                urlBuilder.append("/workspaces/").append(workspaceId);
            }
            urlBuilder.append("/auth-error?message=").append(java.net.URLEncoder.encode(errorMessage, "UTF-8"));

            String errorUrl = urlBuilder.toString();
            LOGGER.debug("Built error redirect URL: {}", errorUrl);

            return errorUrl;
        } catch (java.io.UnsupportedEncodingException e) {
            // UTF-8 should always be supported, but fallback if not
            String fallbackUrl = baseUrl + "/auth-error?message=authentication_failed";
            LOGGER.warn("Failed to encode error message, using fallback URL: {}", fallbackUrl);
            return fallbackUrl;
        }
    }

    /**
     * Reset cached configuration values (useful for testing).
     */
    public static void resetCache() {
        treBaseUrl = null;
        redirectUri = null;
    }
}

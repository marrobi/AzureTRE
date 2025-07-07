package org.apache.guacamole.auth.azuretre;

import com.auth0.jwk.UrlJwkProvider;
import org.apache.guacamole.GuacamoleException;
import org.apache.guacamole.auth.azuretre.connection.ConnectionService;
import org.apache.guacamole.auth.azuretre.user.AzureTREAuthenticatedUser;
import org.apache.guacamole.auth.azuretre.user.TreUserContext;
import org.apache.guacamole.net.auth.AuthenticatedUser;
import org.apache.guacamole.net.auth.Connection;
import org.apache.guacamole.net.auth.Credentials;
import org.apache.guacamole.net.auth.credentials.CredentialsInfo;
import org.apache.guacamole.net.auth.credentials.GuacamoleInvalidCredentialsException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junitpioneer.jupiter.SetEnvironmentVariable;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.MockedStatic;
import org.mockito.Mockito;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;

import javax.servlet.http.HttpServletRequest;

import java.net.URI;
import java.util.HashMap;

import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.fail;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)

public class AzureTREAuthenticationProviderTest {
    public static final String OAUTH_2_PROXY_JWKS_ENDPOINT = "OAUTH2_PROXY_JWKS_ENDPOINT";
    public static final String JWKS_MOCK_ENDPOINT_URL = "https://mockedjwks.com";
    public static final String MOCKED_TOKEN = "dummy_token";
    public static final String MOCKED_USERNAME = "mocked@mail.com";
    @Mock
    AuthenticationProviderService authenticationProviderService;
    @Mock
    HttpServletRequest requestMock;
    @InjectMocks
    Credentials credentialsMock;
    AzureTREAuthenticationProvider azureTREAuthenticationProvider;
    @Mock
    AzureTREAuthenticatedUser authenticatedUser;


    @BeforeEach
    void setup() {
        azureTREAuthenticationProvider = new AzureTREAuthenticationProvider(authenticationProviderService);
    }    @Test
    public void authenticateUserFailsWhenNoWorkspaceClientId() throws GuacamoleException {
        // Test that authentication fails when workspace_client_id parameter is missing
        when(credentialsMock.getRequest().getParameter("workspace_client_id")).thenReturn(null);

        GuacamoleInvalidCredentialsException exception = assertThrows(
            GuacamoleInvalidCredentialsException.class,
            () -> azureTREAuthenticationProvider.authenticateUser(credentialsMock)
        );

        assertTrue(exception.getMessage().contains("workspace_client_id parameter"));
    }

    @Test
    public void authenticateUserFailsWhenEmptyWorkspaceClientId() throws GuacamoleException {
        // Test that authentication fails when workspace_client_id parameter is empty
        when(credentialsMock.getRequest().getParameter("workspace_client_id")).thenReturn("");

        GuacamoleInvalidCredentialsException exception = assertThrows(
            GuacamoleInvalidCredentialsException.class,
            () -> azureTREAuthenticationProvider.authenticateUser(credentialsMock)
        );

        assertTrue(exception.getMessage().contains("workspace_client_id parameter"));
    }

    @Test
    @SetEnvironmentVariable(key = "OPENID_AUTHORIZATION_ENDPOINT", value = "https://login.microsoftonline.com/tenant-id/oauth2/v2.0/authorize")
    @SetEnvironmentVariable(key = "OPENID_REDIRECT_URI", value = "http://localhost:8080/guacamole/")
    public void authenticateUserUsesUrlParameterNotEnvironmentClientId() throws GuacamoleException {
        // Given: workspace_client_id in URL parameter and different OPENID_CLIENT_ID in environment
        String urlWorkspaceClientId = "url-client-id-123";
        String envClientId = "env-client-id-456";
        String workspaceId = "workspace-123";

        // Set environment variable (this should NOT be used)
        System.setProperty("OPENID_CLIENT_ID", envClientId);

        // Mock the getWorkspaceLoginURI to return a test URI
        URI expectedUri = URI.create("https://login.microsoftonline.com/tenant-id/oauth2/v2.0/authorize?client_id=" + urlWorkspaceClientId);
        when(authenticationProviderService.getWorkspaceLoginURI(urlWorkspaceClientId, workspaceId)).thenReturn(expectedUri);

        // Mock request parameters
        when(credentialsMock.getRequest().getParameter("workspace_client_id")).thenReturn(urlWorkspaceClientId);
        when(credentialsMock.getRequest().getParameter("workspace_id")).thenReturn(workspaceId);
        when(credentialsMock.getRequest().getRequestURI()).thenReturn("/guacamole/");
        // Mock that no OAuth tokens are present (to trigger authentication)
        when(credentialsMock.getRequest().getParameter("code")).thenReturn(null);
        when(credentialsMock.getRequest().getParameter("state")).thenReturn(null);
        when(credentialsMock.getRequest().getParameter("id_token")).thenReturn(null);
        when(credentialsMock.getRequest().getParameter("access_token")).thenReturn(null);

        // Should trigger workspace authentication flow since no tokens provided
        GuacamoleInvalidCredentialsException exception = assertThrows(
            GuacamoleInvalidCredentialsException.class,
            () -> azureTREAuthenticationProvider.authenticateUser(credentialsMock)
        );

        // Verify the redirect URL contains the workspace client ID from URL parameter
        String redirectUrl = exception.getMessage();
        assertTrue(redirectUrl.contains("client_id=" + urlWorkspaceClientId),
            "Redirect URL should contain URL parameter client ID");
    }

    @Test
    public void authenticateUserRequiresWorkspaceIdParameter() throws GuacamoleException {
        // Given: workspace_client_id but no workspace_id in URL or path
        when(credentialsMock.getRequest().getParameter("workspace_client_id")).thenReturn("test-client-id");
        when(credentialsMock.getRequest().getParameter("workspace_id")).thenReturn(null);
        when(credentialsMock.getRequest().getRequestURI()).thenReturn("/guacamole/");

        GuacamoleException exception = assertThrows(
            GuacamoleException.class,
            () -> azureTREAuthenticationProvider.authenticateUser(credentialsMock)
        );

        assertTrue(exception.getMessage().contains("workspace ID is required"));
    }

    @Test
    @SetEnvironmentVariable(key = "OPENID_AUTHORIZATION_ENDPOINT", value = "https://login.microsoftonline.com/tenant-id/oauth2/v2.0/authorize")
    @SetEnvironmentVariable(key = "OPENID_REDIRECT_URI", value = "http://localhost:8080/guacamole/")
    public void authenticateUserExtractsWorkspaceIdFromPath() throws GuacamoleException {
        // Given: workspace_client_id in URL and workspace ID in path
        String workspaceClientId = "test-client-id";
        String workspaceId = "workspace-from-path";

        // Mock the getWorkspaceLoginURI to return a test URI
        URI expectedUri = URI.create("https://login.microsoftonline.com/tenant-id/oauth2/v2.0/authorize?client_id=" + workspaceClientId + "&state=" + workspaceId);
        when(authenticationProviderService.getWorkspaceLoginURI(workspaceClientId, workspaceId)).thenReturn(expectedUri);

        when(credentialsMock.getRequest().getParameter("workspace_client_id")).thenReturn(workspaceClientId);
        when(credentialsMock.getRequest().getParameter("workspace_id")).thenReturn(null);
        when(credentialsMock.getRequest().getRequestURI()).thenReturn("/guacamole/workspace/" + workspaceId + "/");
        // Mock that no OAuth tokens are present (to trigger authentication)
        when(credentialsMock.getRequest().getParameter("code")).thenReturn(null);
        when(credentialsMock.getRequest().getParameter("state")).thenReturn(null);
        when(credentialsMock.getRequest().getParameter("id_token")).thenReturn(null);
        when(credentialsMock.getRequest().getParameter("access_token")).thenReturn(null);

        GuacamoleInvalidCredentialsException exception = assertThrows(
            GuacamoleInvalidCredentialsException.class,
            () -> azureTREAuthenticationProvider.authenticateUser(credentialsMock)
        );

        // Should trigger workspace authentication with extracted workspace ID
        String redirectUrl = exception.getMessage();
        assertTrue(redirectUrl.contains("client_id=" + workspaceClientId),
            "Should use workspace client ID from URL parameter");
        assertTrue(redirectUrl.contains("state=" + workspaceId),
            "Should use workspace ID extracted from path");
    }

    @Test
    @SetEnvironmentVariable(key = OAUTH_2_PROXY_JWKS_ENDPOINT, value = JWKS_MOCK_ENDPOINT_URL)
    public void getUserContextSucceed() throws GuacamoleException {
        try (MockedStatic<ConnectionService> connectionServiceMockedStatic =
                 Mockito.mockStatic(ConnectionService.class)) {
            connectionServiceMockedStatic.when(() -> ConnectionService.getConnections(authenticatedUser))
                .thenReturn(new HashMap<String, Connection>());

            TreUserContext treUserContext =
                (TreUserContext) azureTREAuthenticationProvider.getUserContext(authenticatedUser);
            assertNotNull(treUserContext);
        }
    }

    @Test
    public void getUserContextFailsWhenNotInstanceOfAuthUser() throws GuacamoleException {
        AuthenticatedUser notTreUser = mock(AuthenticatedUser.class);
        assertNull(azureTREAuthenticationProvider.getUserContext(notTreUser));
    }

    @Test
    @SetEnvironmentVariable(key = OAUTH_2_PROXY_JWKS_ENDPOINT, value = JWKS_MOCK_ENDPOINT_URL)
    public void getUserContextFailsWhenConnectionServiceFails() throws GuacamoleException {
        try (MockedStatic<ConnectionService> connectionServiceMockedStatic =
                 Mockito.mockStatic(ConnectionService.class)) {
            connectionServiceMockedStatic.when(() -> ConnectionService.getConnections(authenticatedUser))
                .thenThrow(new GuacamoleException("Connection service failed"));

            // Should propagate the exception from ConnectionService.getConnections
            assertThrows(GuacamoleException.class,
                () -> azureTREAuthenticationProvider.getUserContext(authenticatedUser));
        }
    }
}

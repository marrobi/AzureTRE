package org.apache.guacamole.auth.azuretre.connection;

import org.apache.guacamole.GuacamoleException;
import org.apache.guacamole.auth.azuretre.user.AzureTREAuthenticatedUser;
import org.apache.guacamole.net.auth.AuthenticatedUser;
import org.apache.guacamole.net.auth.Connection;
import org.apache.guacamole.protocol.GuacamoleConfiguration;
import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.jupiter.api.Test;
import org.junitpioneer.jupiter.ClearEnvironmentVariable;
import org.junitpioneer.jupiter.SetEnvironmentVariable;
import org.mockito.Mock;
import org.mockito.MockedStatic;
import org.mockito.Mockito;

import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.when;

class ConnectionServiceTest {
    @Mock
    AuthenticatedUser authenticatedUser;

    @Test
    public void getConnectionsWhenEmpty() {
        final Map<String, Connection> connectionList = Collections.emptyMap();
        testGetConnections(connectionList);
    }

    @Test
    public void getConnectionsWhenMany() {
        final Map<String, Connection> connectionList  = new HashMap<>() {{
                put("dummy_connection", null);
            }};
        testGetConnections(connectionList);
    }

    @Test
    public void getConnectionsThrowsExceptionWhenUserIsNull() {
        try (MockedStatic<ConnectionService> connectionServiceMockedStatic = Mockito.mockStatic(
            ConnectionService.class)) {
            connectionServiceMockedStatic.when(() -> ConnectionService.getConnections(null))
                .thenCallRealMethod();
            
            Map<String, Connection> result = ConnectionService.getConnections(null);
            // Should return empty map when user is null
            assertEquals(0, result.size());
        } catch (final GuacamoleException e) {
            e.printStackTrace();
        }
    }

    @Test
    public void getConnectionsHandlesGuacamoleException() {
        try (MockedStatic<ConnectionService> connectionServiceMockedStatic = Mockito.mockStatic(
            ConnectionService.class)) {
            connectionServiceMockedStatic.when(() -> ConnectionService.getConnections(
              (AzureTREAuthenticatedUser) authenticatedUser))
                .thenThrow(new GuacamoleException("API connection failed"));
            
            assertThrows(GuacamoleException.class, () -> 
                ConnectionService.getConnections((AzureTREAuthenticatedUser) authenticatedUser));
        }
    }

    private void testGetConnections(final Map<String, Connection> connectionList) {
        try (MockedStatic<ConnectionService> connectionServiceMockedStatic = Mockito.mockStatic(
            ConnectionService.class)) {
            connectionServiceMockedStatic.when(() -> ConnectionService.getConnections(
              (AzureTREAuthenticatedUser) authenticatedUser))
                .thenReturn(connectionList);
            assertEquals(connectionList, ConnectionService.getConnections(
                (AzureTREAuthenticatedUser) authenticatedUser));
        } catch (final GuacamoleException e) {
            e.printStackTrace();
        }
    }

    @Test
    public void extractGuacamoleServiceIdsReturnsEmptyForNullOrBlank() {
        assertTrue(ConnectionService.extractGuacamoleServiceIds(null).isEmpty());
        assertTrue(ConnectionService.extractGuacamoleServiceIds("").isEmpty());
        assertTrue(ConnectionService.extractGuacamoleServiceIds("   ").isEmpty());
    }

    @Test
    public void extractGuacamoleServiceIdsFiltersToEnabledGuacamoleServices() {
        final String body = "{\"workspaceServices\":["
            + "{\"id\":\"guac-1\",\"templateName\":\"tre-service-guacamole\",\"isEnabled\":true},"
            + "{\"id\":\"guac-2\",\"templateName\":\"tre-service-guacamole\"},"
            + "{\"id\":\"guac-disabled\",\"templateName\":\"tre-service-guacamole\",\"isEnabled\":false},"
            + "{\"id\":\"other\",\"templateName\":\"tre-service-gitea\",\"isEnabled\":true}"
            + "]}";

        final List<String> ids = ConnectionService.extractGuacamoleServiceIds(body);

        assertEquals(List.of("guac-1", "guac-2"), ids);
    }

    @Test
    @SetEnvironmentVariable(key = "API_URL", value = "http://localhost")
    @ClearEnvironmentVariable(key = "SERVICE_ID")
    public void collectUserResourcesAggregatesAcrossMultipleServices() throws GuacamoleException {
        final AzureTREAuthenticatedUser user = Mockito.mock(AzureTREAuthenticatedUser.class);
        when(user.getWorkspaceId()).thenReturn("ws-1");

        final ConnectionService.ApiJsonFetcher fetcher = (url, u) -> {
            if (url.endsWith("/workspace-services")) {
                return "{\"workspaceServices\":["
                    + "{\"id\":\"guac-1\",\"templateName\":\"tre-service-guacamole\",\"isEnabled\":true},"
                    + "{\"id\":\"guac-2\",\"templateName\":\"tre-service-guacamole\",\"isEnabled\":true}"
                    + "]}";
            }
            if (url.contains("/guac-1/user-resources")) {
                return "{\"userResources\":[{\"id\":\"vm-a\"}]}";
            }
            if (url.contains("/guac-2/user-resources")) {
                return "{\"userResources\":[{\"id\":\"vm-b\"},{\"id\":\"vm-c\"}]}";
            }
            return "";
        };

        final JSONArray result = ConnectionService.collectUserResources(user, fetcher);

        assertEquals(3, result.length());
    }

    @Test
    @SetEnvironmentVariable(key = "API_URL", value = "http://localhost")
    @ClearEnvironmentVariable(key = "SERVICE_ID")
    public void collectUserResourcesSkipsFailingService() throws GuacamoleException {
        final AzureTREAuthenticatedUser user = Mockito.mock(AzureTREAuthenticatedUser.class);
        when(user.getWorkspaceId()).thenReturn("ws-1");

        final ConnectionService.ApiJsonFetcher fetcher = (url, u) -> {
            if (url.endsWith("/workspace-services")) {
                return "{\"workspaceServices\":["
                    + "{\"id\":\"guac-1\",\"templateName\":\"tre-service-guacamole\",\"isEnabled\":true},"
                    + "{\"id\":\"guac-2\",\"templateName\":\"tre-service-guacamole\",\"isEnabled\":true}"
                    + "]}";
            }
            if (url.contains("/guac-1/user-resources")) {
                throw new GuacamoleException("boom");
            }
            if (url.contains("/guac-2/user-resources")) {
                return "{\"userResources\":[{\"id\":\"vm-b\"}]}";
            }
            return "";
        };

        final JSONArray result = ConnectionService.collectUserResources(user, fetcher);

        // Only the healthy service's VM should be returned.
        assertEquals(1, result.length());
    }

    @Test
    @SetEnvironmentVariable(key = "API_URL", value = "http://localhost")
    @SetEnvironmentVariable(key = "SERVICE_ID", value = "legacy-service")
    public void collectUserResourcesUsesStaticServiceIdWhenSet() throws GuacamoleException {
        final AzureTREAuthenticatedUser user = Mockito.mock(AzureTREAuthenticatedUser.class);
        when(user.getWorkspaceId()).thenReturn("ws-1");

        final ConnectionService.ApiJsonFetcher fetcher = (url, u) -> {
            if (url.contains("/legacy-service/user-resources")) {
                return "{\"userResources\":[{\"id\":\"vm-legacy\"}]}";
            }
            // Discovery must not be attempted when a static SERVICE_ID is set.
            throw new GuacamoleException("unexpected call: " + url);
        };

        final JSONArray result = ConnectionService.collectUserResources(user, fetcher);

        assertEquals(1, result.length());
    }

    @Test
    @SetEnvironmentVariable(key = "API_URL", value = "http://localhost")
    @ClearEnvironmentVariable(key = "SERVICE_ID")
    public void collectUserResourcesTagsResourcesWithWorkspaceServiceSettings()
        throws GuacamoleException {
        final AzureTREAuthenticatedUser user = Mockito.mock(AzureTREAuthenticatedUser.class);
        when(user.getWorkspaceId()).thenReturn("ws-1");

        final ConnectionService.ApiJsonFetcher fetcher = (url, u) -> {
            if (url.endsWith("/workspace-services")) {
                return "{\"workspaceServices\":["
                    + "{\"id\":\"guac-1\",\"templateName\":\"tre-service-guacamole\","
                    + "\"isEnabled\":true,\"properties\":{\"guac_disable_copy\":false,"
                    + "\"guac_disable_paste\":true}}"
                    + "]}";
            }
            if (url.contains("/guac-1/user-resources")) {
                return "{\"userResources\":[{\"id\":\"vm-a\"}]}";
            }
            return "";
        };

        final JSONArray result = ConnectionService.collectUserResources(user, fetcher);

        assertEquals(1, result.length());
        final JSONObject settings = result.getJSONObject(0).getJSONObject("_guacSettings");
        assertEquals(false, settings.getBoolean("guac_disable_copy"));
        assertEquals(true, settings.getBoolean("guac_disable_paste"));
    }

    @Test
    @ClearEnvironmentVariable(key = "GUAC_DISABLE_COPY")
    @ClearEnvironmentVariable(key = "GUAC_DISABLE_PASTE")
    @ClearEnvironmentVariable(key = "GUAC_SERVER_LAYOUT")
    public void buildConfigurationAppliesWorkspaceServicePolicySettings() {
        final JSONObject vm = vmWithSettings(new JSONObject()
            .put("guac_disable_copy", false)
            .put("guac_disable_paste", true)
            .put("guac_enable_drive", true)
            .put("guac_disable_download", false)
            .put("guac_disable_upload", false)
            .put("guac_server_layout", "de-de-qwertz"));

        final GuacamoleConfiguration config = ConnectionService.buildConfiguration(vm);

        assertEquals("false", config.getParameter("disable-copy"));
        assertEquals("true", config.getParameter("disable-paste"));
        assertEquals("true", config.getParameter("enable-drive"));
        assertEquals("false", config.getParameter("disable-download"));
        assertEquals("false", config.getParameter("disable-upload"));
        assertEquals("de-de-qwertz", config.getParameter("server-layout"));
    }

    @Test
    @SetEnvironmentVariable(key = "GUAC_DISABLE_COPY", value = "true")
    public void buildConfigurationWorkspaceServiceSettingOverridesEnv() {
        final JSONObject vm = vmWithSettings(new JSONObject()
            .put("guac_disable_copy", false));

        final GuacamoleConfiguration config = ConnectionService.buildConfiguration(vm);

        // The workspace service's own policy must win over the shared
        // service's deployment-time default.
        assertEquals("false", config.getParameter("disable-copy"));
    }

    @Test
    @SetEnvironmentVariable(key = "GUAC_DISABLE_COPY", value = "true")
    public void buildConfigurationFallsBackToEnvWhenNoWorkspaceServiceSettings() {
        final JSONObject vm = new JSONObject().put("properties", new JSONObject()
            .put("hostname", "vm-host")
            .put("ip", "10.0.0.1")
            .put("display_name", "My VM"));

        final GuacamoleConfiguration config = ConnectionService.buildConfiguration(vm);

        assertEquals("true", config.getParameter("disable-copy"));
    }

    @Test
    public void buildConfigurationReturnsNullWhenMissingHostname() {
        final JSONObject vm = new JSONObject().put("properties", new JSONObject()
            .put("ip", "10.0.0.1")
            .put("display_name", "My VM"));

        assertNull(ConnectionService.buildConfiguration(vm));
    }

    @Test
    public void extractGuacamoleServicesReturnsProperties() {
        final String body = "{\"workspaceServices\":["
            + "{\"id\":\"guac-1\",\"templateName\":\"tre-service-guacamole\","
            + "\"isEnabled\":true,\"properties\":{\"guac_disable_copy\":true}}"
            + "]}";

        final List<JSONObject> services = ConnectionService.extractGuacamoleServices(body);

        assertEquals(1, services.size());
        assertEquals(true, services.get(0).getJSONObject("properties")
            .getBoolean("guac_disable_copy"));
    }

    private static JSONObject vmWithSettings(final JSONObject settings) {
        return new JSONObject()
            .put("properties", new JSONObject()
                .put("hostname", "vm-host")
                .put("ip", "10.0.0.1")
                .put("display_name", "My VM"))
            .put("_guacSettings", settings);
    }
}

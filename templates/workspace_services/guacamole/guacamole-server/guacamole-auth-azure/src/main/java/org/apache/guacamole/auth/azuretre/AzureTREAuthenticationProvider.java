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

import com.google.inject.Guice;
import com.google.inject.Injector;
import org.apache.guacamole.GuacamoleException;
import org.apache.guacamole.auth.azuretre.user.AzureTREAuthenticatedUser;
import org.apache.guacamole.net.auth.AbstractAuthenticationProvider;
import org.apache.guacamole.net.auth.UserContext;
import org.apache.guacamole.net.auth.simple.SimpleAuthenticationProvider;
import org.apache.guacamole.net.auth.AuthenticatedUser;
import org.apache.guacamole.net.auth.Credentials;
import org.apache.guacamole.net.auth.simple.SimpleUserContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Enumeration;
import java.util.HashMap;
import java.util.Map;
import org.apache.guacamole.protocol.GuacamoleConfiguration;
import javax.servlet.http.HttpServletRequest;

public class AzureTREAuthenticationProvider extends AbstractAuthenticationProvider {

    public static final String ROOT_CONNECTION_GROUP = "ROOT";

    /**
     * The standard HTTP parameter which will be included within the URL by all
     * OpenID services upon successful authentication and redirect.
     */
    public static final String PARAMETER_NAME = "id_token";

    private static final Logger LOGGER = LoggerFactory.getLogger(AzureTREAuthenticationProvider.class);

    private final Injector injector;

    public AzureTREAuthenticationProvider() throws GuacamoleException {
        // Set up Guice injector.
        injector = Guice.createInjector(new AzureTREAuthenticationProviderModule(this));
    }

    @Override
    public String getIdentifier() {
        return "azuretre";
    }

    /*
    @Override
    public AuthenticatedUser updateAuthenticatedUser(AuthenticatedUser authenticatedUser,
                                                     Credentials credentials)
        throws org.apache.guacamole.GuacamoleException {

        String token = authenticatedUser.getCredentials().getRequest().getParameter(PARAMETER_NAME);
        return authenticatedUser;
    }

    @Override
    public org.apache.guacamole.net.auth.UserContext updateUserContext(UserContext context, AuthenticatedUser authenticatedUser, Credentials credentials) throws GuacamoleException {

        String token = authenticatedUser.getCredentials().getRequest().getParameter("id_token");
        return context;
    }
*/
    @Override
    public  org.apache.guacamole.auth.azuretre.user.UserContext getUserContext(final AuthenticatedUser authenticatedUser) throws GuacamoleException {
        if (authenticatedUser != null) {
            LOGGER.info("Identifier: " + authenticatedUser.getIdentifier());
            String token = authenticatedUser.getCredentials().getRequest().getParameter(PARAMETER_NAME);
            LOGGER.info("id_token is : " + token);

            AzureTREAuthenticatedUser treUser = new AzureTREAuthenticatedUser();
            treUser.init(authenticatedUser.getCredentials(), token, authenticatedUser.getIdentifier(), null);
            final  org.apache.guacamole.auth.azuretre.user.UserContext userContext = injector.getInstance( org.apache.guacamole.auth.azuretre.user.UserContext.class);
            userContext.init(treUser);

            return userContext;
        }
        // Unauthorized
        return null;
    }
}

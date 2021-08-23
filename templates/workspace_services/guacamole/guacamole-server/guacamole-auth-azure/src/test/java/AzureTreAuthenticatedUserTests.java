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

import static org.mockito.Mockito.mock;

import org.apache.guacamole.GuacamoleException;
import org.apache.guacamole.auth.azuretre.user.AzureTREAuthenticatedUser;
import org.apache.guacamole.net.auth.Credentials;

import org.junit.Assert;
import org.junit.Test;

public class AzureTreAuthenticatedUserTests {

  String dummyAccessToken = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsImtpZCI6ImtnMkxZczJUMENUaklmajRydDZKSXluZW4zOCJ9.eyJhdWQiOiI2ZjY3ZjI3YS04NTk4LTQ4ZGMtYTM1OC00MDVkMzAyOThhMDMiLCJpc3MiOiJodHRwczovL2xvZ2luLm1pY3Jvc29mdG9ubGluZS5jb20vYWY0MTg0ZGItNjdhOC00ZDMxLWJjMDYtYmUwN2IwMGJlYWQwL3YyLjAiLCJpYXQiOjE2MDIxNzUxODQsIm5iZiI6MTYwMjE3NTE4NCwiZXhwIjoxNjAyMTc5MDg0LCJhaW8iOiJBVFFBeS84UkFBQUFRWVRQZW8yM3NpN0ZuQjZXbEtIZUs5MnhFZGN5T3NKWDhzSXBkRUpRd2dnR1g3M0ZFL0hPTCtDZU1STjdrQlJoIiwiYXpwIjoiNmY2N2YyN2EtODU5OC00OGRjLWEzNTgtNDA1ZDMwMjk4YTAzIiwiYXpwYWNyIjoiMSIsIm5hbWUiOiJNYXJjdXMgVGVzdCIsIm9pZCI6IjYzYTE3NzY0LThiZWEtNDk4Yi1hYzEyLWZjNTRlMzMwMDAxNyIsInByZWZlcnJlZF91c2VybmFtZSI6Im1hcmN1c3Rlc3RAZHJlZGV2Mm91dGxvb2sub25taWNyb3NvZnQuY29tIiwicmgiOiIwLkFBQUEyNFJCcjZobk1VMjhCcjRIc0F2cTBIcnlaMi1ZaGR4SW8xaEFYVEFwaWdOMEFITS4iLCJyb2xlcyI6WyJQcm9qZWN0LUFkbWluaXN0cmF0b3IiLCJQcm9qZWN0LVVzZXIiXSwic2NwIjoiZW1haWwgb3BlbmlkIHByb2ZpbGUgVXNlci5SZWFkIiwic3ViIjoiLUg2aFdjR0pRd2hJVE9ZakNJY1RkV2V3UkNfMUZHZXFHZnZpQV91Q0JVRSIsInRpZCI6ImFmNDE4NGRiLTY3YTgtNGQzMS1iYzA2LWJlMDdiMDBiZWFkMCIsInVwbiI6Im1hcmN1c3Rlc3RAZHJlZGV2Mm91dGxvb2sub25taWNyb3NvZnQuY29tIiwidXRpIjoiMk1wVHo3WExXVTJzQV9ENVRWaTZBQSIsInZlciI6IjIuMCIsIndpZHMiOlsiYjc5ZmJmNGQtM2VmOS00Njg5LTgxNDMtNzZiMTk0ZTg1NTA5Il19.qG8CZ7_AIxvt7YTy9UqhLUujv_fIdwTWrnKZlN9AE5tJvaHCNP_7URJWbE9J3tcH2Ot6pYORHqqhcRAYe6pGP1w4FZFLt-GRLBfZ80V6uuYTIA3BmZEimVBMQchPfwpZm6kJhT8Jc9qeMXoZbPVNoeMAf1mFthgQ_VfffGt_tnX-vf9CCsQcS7D175RNpbbpKXvQVoupIt_iwdxhwb6_cJSTolV8P4ohJWKcU3dP61wzWuHP50wgxbvDIVqk7ltTTNFG36TAwlzd9-C_sztIoaIKRss_WIhSAu01SY6bWAw75M33KqRZt0KmvQRpwd14yeuGK1ulUa8_-t3lynqWfw";

  @Test
  public void AuthenticatedUser_returns_claims() throws GuacamoleException {

    AzureTREAuthenticatedUser authenticatedUser = new AzureTREAuthenticatedUser();

    Credentials credentialsMock = mock(Credentials.class);

    authenticatedUser.init(credentialsMock, dummyAccessToken, "dummy_username", "dummy_objectid");

    Assert.assertEquals("dummy_objectid", authenticatedUser.getObjectId());
    Assert.assertEquals("dummy_username", authenticatedUser.getIdentifier());

  }
}
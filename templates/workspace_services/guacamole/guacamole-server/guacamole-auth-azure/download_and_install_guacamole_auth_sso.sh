#!/bin/bash

# Download the guacamole-auth-sso-1.6.0.tar.gz file
wget -O guacamole-auth-sso-1.6.0.tar.gz "https://apache.org/dyn/closer.lua/guacamole/1.6.0/binary/guacamole-auth-sso-1.6.0.tar.gz?action=download" --progress=dot:giga

# Extract the contents of the tar.gz file
mkdir -p guacamole-auth-sso-1.6.0
tar -xzf guacamole-auth-sso-1.6.0.tar.gz -C guacamole-auth-sso-1.6.0 --strip-components=1

unzip guacamole-auth-sso-1.6.0/openid/guacamole-auth-sso-openid-1.6.0.jar -d guacamole-auth-sso-1.6.0/openid/

# Install the JAR files using Maven
mvn install:install-file -Dfile=guacamole-auth-sso-1.6.0/openid/guacamole-auth-sso-openid-1.6.0.jar -DgroupId=org.apache.guacamole -DartifactId=guacamole-auth-sso-openid -Dversion=1.6.0 -Dpackaging=jar
mvn install:install-file -Dfile=guacamole-auth-sso-1.6.0/openid/guacamole-auth-sso-base-1.6.0.jar -DgroupId=org.apache.guacamole -DartifactId=guacamole-auth-sso -Dversion=1.6.0 -Dpackaging=jar

# Clean up
rm -rf guacamole-auth-sso-1.6.0 guacamole-auth-sso-1.6.0.tar.gz

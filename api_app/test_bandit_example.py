"""
This is a test file with intentional security vulnerabilities for testing the Bandit pre-commit hook.
These vulnerabilities should be caught and resolved during development.
"""

import subprocess
import random
import pickle
import os
from flask import request

# Vulnerability 1: Hardcoded password/secret
DATABASE_PASSWORD = "MySecurePassword123"
API_KEY = "sk_live_51234567890abcdef"

# Vulnerability 2: Use of random for security purposes
def generate_token():
    """Insecure token generation - should use secrets module"""
    return random.randint(100000, 999999)

# Vulnerability 3: Shell injection vulnerability
def execute_command(user_input):
    """Dangerous use of subprocess with shell=True"""
    result = subprocess.run(
        f"echo {user_input}",
        shell=True,
        capture_output=True
    )
    return result.stdout.decode()

# Vulnerability 4: SQL injection risk
def query_database(db_connection, user_id):
    """Unsafe SQL query construction"""
    cursor = db_connection.cursor()
    query = f"SELECT * FROM users WHERE id = {user_id}"
    cursor.execute(query)
    return cursor.fetchall()

# Vulnerability 5: Unsafe deserialization
def deserialize_data(data):
    """Dangerous use of pickle.loads with untrusted data"""
    return pickle.loads(data)

# Vulnerability 6: Exec function usage
def execute_user_code(code_string):
    """Dangerous use of exec() function"""
    exec(code_string)

# Vulnerability 7: Missing certificate validation (would show if requests is used)
def insecure_request(url):
    """Example of what would be insecure - hardcoded credentials in URL"""
    import requests
    response = requests.get(f"https://user:password@{url}")
    return response.text

if __name__ == "__main__":
    print("This file contains intentional security vulnerabilities for testing.")
    print("Do not use this code as a reference for production code!")
# Added comment

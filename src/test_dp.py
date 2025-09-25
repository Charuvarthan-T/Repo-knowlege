from neo4j import GraphDatabase

# --- CONFIGURATION ---
# The only thing you need to edit is the PASSWORD line.
URI = "neo4j://localhost:7687"
USER = "neo4j"
PASSWORD = "neo4j-test-123" # <-- THE ONLY LINE TO EDIT

# --- CONNECTION TEST ---
print("--- Neo4j Connection Test ---")
print(f"Attempting to connect to {URI} as user '{USER}'...")

try:
    # This command connects and verifies authentication in one step.
    with GraphDatabase.driver(URI, auth=(USER, PASSWORD)) as driver:
        driver.verify_connectivity()

    # If the line above doesn't fail, the password is correct.
    print("\n[SUCCESS] Authentication successful! The password is correct.")
    print("You can now copy this exact password into 'graph_builder.py'.")

except Exception as e:
    # If verify_connectivity() fails, it will raise an exception.
    print("\n[FAILURE] Authentication FAILED.")
    print("The password you entered in this test script is INCORRECT.")
    print(f"Error details: {e}")
import os
import requests
import json
import time

# --- Configuration ---
# Your NextDNS API Key and Profile ID from GitHub Secrets
API_KEY = os.environ.get("NEXTDNS_API_KEY")
PROFILE_ID = os.environ.get("NEXTDNS_PROFILE_ID")

# The number of domains to process in each batch.
# 500 is a safe and efficient number.
CHUNK_SIZE = 500

# The API endpoint for the denylist
NEXTDNS_API_URL = f"https://api.nextdns.io/profiles/{PROFILE_ID}/denylist"


def get_current_denylist(session):
    """Fetches the current denylist from NextDNS."""
    print("Fetching current NextDNS denylist...")
    try:
        response = session.get(NEXTDNS_API_URL)
        response.raise_for_status()
        # When you GET rules, the domain is the 'id' field
        data = response.json().get('data', [])
        print(f"Found {len(data)} domains currently in your denylist.")
        return {item['id'] for item in data}
    except requests.exceptions.RequestException as e:
        print(f"FATAL: Could not fetch current denylist. Error: {e}")
        # Exit if we can't get the current state, to avoid incorrect changes.
        exit(1)


def get_remote_blocklist_domains():
    """Fetches and parses unique domains from a list of blocklist URLs."""
    print("Fetching domains from remote blocklists...")
    domains = set()
    session = requests.Session()
    with open("blocklists.txt", "r") as f:
        blocklist_urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    for url in blocklist_urls:
        try:
            response = session.get(url, timeout=30)
            response.raise_for_status()
            for line in response.text.splitlines():
                line = line.strip().split("#")[0].strip()
                if line:
                    parts = line.split()
                    domain = parts[-1]
                    if domain != '0.0.0.0' and domain != '127.0.0.1':
                        domains.add(domain)
        except requests.exceptions.RequestException as e:
            print(f"Warning: Could not fetch {url}. Error: {e}")
    
    print(f"Found {len(domains)} unique domains across all source lists.")
    return domains


def execute_in_batches(session, domains, action):
    """Adds or removes domains in batches."""
    if not domains:
        return

    action_verb = "Adding" if action == 'add' else "Removing"
    http_method = session.post if action == 'add' else session.delete
    
    domain_list = list(domains)
    total_chunks = (len(domain_list) + CHUNK_SIZE - 1) // CHUNK_SIZE

    print(f"\nPreparing to {action} {len(domains)} domains in {total_chunks} chunk(s).")

    for i in range(0, len(domain_list), CHUNK_SIZE):
        chunk = domain_list[i:i + CHUNK_SIZE]
        current_chunk_num = (i // CHUNK_SIZE) + 1
        
        # The API expects an array of objects for bulk POST (add) and DELETE (remove)
        if action == 'add':
            payload = [{"id": domain, "active": True} for domain in chunk]
        else:
            payload = [{"id": domain} for domain in chunk]

        print(f"{action_verb} chunk {current_chunk_num} of {total_chunks} ({len(chunk)} domains)...")
        try:
            # We use a POST to add and a DELETE with a body to remove
            response = http_method(NEXTDNS_API_URL, json=payload, timeout=60)
            response.raise_for_status()
            print(f"  Chunk {current_chunk_num} successful.")
        except requests.exceptions.RequestException as e:
            print(f"  ERROR on chunk {current_chunk_num}: {e}")
            if e.response:
                print(f"  Response Body: {e.response.text}")
        
        # Be a good API citizen and wait a moment between requests
        time.sleep(1)


if __name__ == "__main__":
    if not API_KEY or not PROFILE_ID:
        raise ValueError("NEXTDNS_API_KEY and NEXTDNS_PROFILE_ID environment variables must be set.")

    # Use a single session for all API calls
    api_session = requests.Session()
    api_session.headers.update({"X-Api-Key": API_KEY})

    # 1. Get the desired state from source files
    desired_domains = get_remote_blocklist_domains()
    if not desired_domains:
        print("No domains were fetched. Aborting to avoid unintended changes.")
        exit(1)

    # 2. Get the current state from NextDNS
    current_domains = get_current_denylist(api_session)

    # 3. Calculate the difference
    domains_to_add = desired_domains - current_domains
    domains_to_remove = current_domains - desired_domains

    # 4. Execute the changes in batches
    if not domains_to_add and not domains_to_remove:
        print("\nYour NextDNS denylist is already up to date. No changes needed.")
    else:
        execute_in_batches(api_session, domains_to_add, action='add')
        execute_in_batches(api_session, domains_to_remove, action='remove')
        print("\nDenylist update process complete.")

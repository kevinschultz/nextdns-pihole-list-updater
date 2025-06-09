import os
import requests
import json
import time

# --- Debugging Configuration ---
# Set to a number to limit the total domains for this test. Set to None to run on all domains.
DEBUG_DOMAIN_LIMIT = 100
# The number of domains to process in each batch. User requested 25 for this test.
CHUNK_SIZE = 25
# --- End Debugging Configuration ---

# Your NextDNS API Key and Profile ID from GitHub Secrets
API_KEY = os.environ.get("NEXTDNS_API_KEY")
PROFILE_ID = os.environ.get("NEXTDNS_PROFILE_ID")

# The API endpoint for the denylist
NEXTDNS_API_URL = f"https://api.nextdns.io/profiles/{PROFILE_ID}/denylist"


def get_current_denylist(session):
    """Fetches the current denylist from NextDNS."""
    print("Fetching current NextDNS denylist...")
    try:
        response = session.get(NEXTDNS_API_URL)
        response.raise_for_status()
        data = response.json().get('data', [])
        print(f"Found {len(data)} domains currently in your denylist.")
        return {item['id'] for item in data}
    except requests.exceptions.RequestException as e:
        print(f"FATAL: Could not fetch current denylist. Error: {e}")
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

    print(f"\nPreparing to {action} {len(domains)} domains in {total_chunks} chunk(s) of {CHUNK_SIZE}.")

    for i in range(0, len(domain_list), CHUNK_SIZE):
        chunk = domain_list[i:i + CHUNK_SIZE]
        current_chunk_num = (i // CHUNK_SIZE) + 1
        
        if action == 'add':
            payload = [{"id": domain, "active": True} for domain in chunk]
        else:
            payload = [{"id": domain} for domain in chunk]

        print(f"{action_verb} chunk {current_chunk_num} of {total_chunks} ({len(chunk)} domains)...")
        try:
            response = http_method(NEXTDNS_API_URL, json=payload, timeout=60)
            response.raise_for_status()
            print(f"  Chunk {current_chunk_num} successful.")
        except requests.exceptions.RequestException as e:
            print(f"  ERROR on chunk {current_chunk_num}: {e}")
            if e.response:
                print(f"  Response Body: {e.response.text}")
        
        time.sleep(1)


if __name__ == "__main__":
    if not API_KEY or not PROFILE_ID:
        raise ValueError("NEXTDNS_API_KEY and NEXTDNS_PROFILE_ID environment variables must be set.")

    api_session = requests.Session()
    api_session.headers.update({"X-Api-Key": API_KEY})

    all_desired_domains = get_remote_blocklist_domains()

    # --- Debugging: Limit the number of domains to process ---
    if DEBUG_DOMAIN_LIMIT is not None:
        print(f"\n---!!! DEBUG MODE ENABLED: Limiting to a maximum of {DEBUG_DOMAIN_LIMIT} domains. !!!---")
        if len(all_desired_domains) > DEBUG_DOMAIN_LIMIT:
            # Sort for deterministic results, then slice to get a consistent subset
            desired_domains = set(sorted(list(all_desired_domains))[:DEBUG_DOMAIN_LIMIT])
            print(f"Original domain count: {len(all_desired_domains)}. Using the first {len(desired_domains)} for this test run.")
        else:
            desired_domains = all_desired_domains
    else:
        desired_domains = all_desired_domains
    # --- End Debugging Block ---

    if not desired_domains:
        print("No domains to process after applying debug limit. Aborting.")
        exit(1)

    current_domains = get_current_denylist(api_session)

    domains_to_add = desired_domains - current_domains
    domains_to_remove = current_domains - desired_domains

    if not domains_to_add and not domains_to_remove:
        print("\nYour NextDNS denylist is already up to date with the test list. No changes needed.")
    else:
        execute_in_batches(api_session, domains_to_add, action='add')
        execute_in_batches(api_session, domains_to_remove, action='remove')
        print("\nDiagnostic test run complete.")

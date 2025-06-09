import os
import requests
import json
import time

# Your NextDNS API Key and Profile ID from GitHub Secrets
API_KEY = os.environ.get("NEXTDNS_API_KEY")
PROFILE_ID = os.environ.get("NEXTDNS_PROFILE_ID")

# We'll process our lists in batches of this size.
CHUNK_SIZE = 1000

NEXTDNS_API_URL = f"https://api.nextdns.io/profiles/{PROFILE_ID}/denylist"

def get_current_denylist():
    """Fetches the current denylist from NextDNS."""
    headers = {"X-Api-Key": API_KEY}
    response = requests.get(NEXTDNS_API_URL, headers=headers)
    response.raise_for_status()
    # When you GET rules, the domain is the 'id' field
    return {item['id'] for item in response.json().get('data', [])}

def get_remote_blocklist_domains(blocklist_urls):
    """Fetches and parses domains from a list of blocklist URLs."""
    domains = set()
    session = requests.Session()
    for url in blocklist_urls:
        try:
            response = session.get(url, timeout=30)
            response.raise_for_status()
            for line in response.text.splitlines():
                line = line.strip().split("#")[0].strip()
                if line:
                    parts = line.split()
                    if len(parts) > 1:
                        domain = parts[-1]
                        if domain != '0.0.0.0' and domain != '127.0.0.1':
                             domains.add(domain)
                    else:
                        domains.add(parts[0])
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {url}: {e}")
    return domains

def update_denylist_in_batches(domains, action='add'):
    """Adds or removes domains in batches using the correct API key for each action."""
    headers = {
        "X-Api-Key": API_KEY,
        "Content-Type": "application/json"
    }
    session = requests.Session()
    session.headers.update(headers)

    domain_list = list(domains)
    total_chunks = (len(domain_list) + CHUNK_SIZE - 1) // CHUNK_SIZE
    
    http_method = session.post if action == 'add' else session.delete
    
    # --- THIS IS THE KEY CHANGE ---
    # Use 'domain' as the key when adding, and 'id' when removing.
    key_for_payload = 'domain' if action == 'add' else 'id'

    for i in range(0, len(domain_list), CHUNK_SIZE):
        chunk = domain_list[i:i + CHUNK_SIZE]
        # Generate payload with the correct key
        payload = {"rules": [{key_for_payload: domain} for domain in chunk]}
        
        current_chunk_num = (i // CHUNK_SIZE) + 1
        action_verb = "Adding" if action == 'add' else "Removing"
        print(f"{action_verb} chunk {current_chunk_num} of {total_chunks} ({len(chunk)} domains)...")

        try:
            response = http_method(NEXTDNS_API_URL, json=payload, timeout=60)
            # A successful response is 204 No Content
            response.raise_for_status()
            print(f"  Chunk {current_chunk_num} successful.")
        except requests.exceptions.RequestException as e:
            print(f"  ERROR on chunk {current_chunk_num}: {e}")
            # The API should provide a more detailed error in the response body
            if e.response:
                print(f"  Response Body: {e.response.text}")
        
        time.sleep(1)

if __name__ == "__main__":
    if not API_KEY or not PROFILE_ID:
        raise ValueError("NEXTDNS_API_KEY and NEXTDNS_PROFILE_ID environment variables must be set.")

    with open("blocklists.txt", "r") as f:
        blocklist_urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    print("Fetching remote blocklists...")
    remote_domains = get_remote_blocklist_domains(blocklist_urls)
    print(f"Found {len(remote_domains)} unique domains in remote lists.")

    print("Fetching current NextDNS denylist...")
    current_denylist = get_current_denylist()
    print(f"Found {len(current_denylist)} domains in your NextDNS denylist.")

    domains_to_add = remote_domains - current_denylist
    domains_to_remove = current_denylist - remote_domains

    if not domains_to_add and not domains_to_remove:
        print("Your NextDNS denylist is already up to date.")
    else:
        if domains_to_add:
            print(f"Preparing to add {len(domains_to_add)} new domains.")
            update_denylist_in_batches(domains_to_add, action='add')
        
        if domains_to_remove:
            print(f"Preparing to remove {len(domains_to_remove)} domains.")
            update_denylist_in_batches(domains_to_remove, action='remove')

import os
import requests
import json
import time

# --- Debugging Configuration ---
# Set to a number to limit the total domains for a test run.
# Set to None to run on all domains for the full sync.
DEBUG_DOMAIN_LIMIT = 20
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


def add_domains_one_by_one(session, domains_to_add):
    """Adds domains one by one, which is slow but supported by the API."""
    if not domains_to_add:
        return
        
    print(f"\nAdding {len(domains_to_add)} domains one by one...")
    for i, domain in enumerate(domains_to_add, 1):
        payload = {"id": domain, "active": True}
        try:
            response = session.post(NEXTDNS_API_URL, json=payload, timeout=15)
            if response.status_code == 409: # Conflict
                print(f"  {i}/{len(domains_to_add)}: Skipping '{domain}' (already exists).")
                continue
            response.raise_for_status()
            print(f"  {i}/{len(domains_to_add)}: Added '{domain}'")
        except requests.exceptions.RequestException as e:
            print(f"  ERROR adding '{domain}': {e}")
        # Add a very short sleep to be polite to the API on sequential requests
        time.sleep(0.1)


def remove_domains_one_by_one(session, domains_to_remove):
    """Removes domains one by one, which is slow but supported by the API."""
    if not domains_to_remove:
        return

    print(f"\nRemoving {len(domains_to_remove)} domains one by one...")
    for i, domain in enumerate(domains_to_remove, 1):
        delete_url = f"{NEXTDNS_API_URL}/{domain}"
        try:
            response = session.delete(delete_url, timeout=15)
            if response.status_code == 404: # Not Found
                print(f"  {i}/{len(domains_to_remove)}: Skipping '{domain}' (does not exist).")
                continue
            response.raise_for_status()
            print(f"  {i}/{len(domains_to_remove)}: Removed '{domain}'")
        except requests.exceptions.RequestException as e:
            print(f"  ERROR removing '{domain}': {e}")
        # Add a very short sleep to be polite to the API
        time.sleep(0.1)


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
        print("\nNo domains to process. Aborting.")
        exit(1)

    current_domains = get_current_denylist(api_session)

    domains_to_add = desired_domains - current_domains
    domains_to_remove = current_domains - desired_domains

    if not domains_to_add and not domains_to_remove:
        print("\nYour NextDNS denylist is already up to date with the test list. No changes needed.")
    else:
        add_domains_one_by_one(api_session, domains_to_add)
        remove_domains_one_by_one(api_session, domains_to_remove)
        print("\nTest run update process complete.")

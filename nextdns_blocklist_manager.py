import os
import requests
import json

# Your NextDNS API Key and Profile ID from GitHub Secrets
API_KEY = os.environ.get("NEXTDNS_API_KEY")
PROFILE_ID = os.environ.get("NEXTDNS_PROFILE_ID")

NEXTDNS_API_URL = f"https://api.nextdns.io/profiles/{PROFILE_ID}/denylist"

def get_current_denylist():
    """Fetches the current denylist from NextDNS."""
    headers = {"X-Api-Key": API_KEY}
    response = requests.get(NEXTDNS_API_URL, headers=headers)
    response.raise_for_status()
    # The 'id' of a denylist rule is the domain name itself
    return {item['id'] for item in response.json().get('data', [])}

def get_remote_blocklist_domains(blocklist_urls):
    """Fetches and parses domains from a list of blocklist URLs."""
    domains = set()
    session = requests.Session()
    for url in blocklist_urls:
        try:
            response = session.get(url)
            response.raise_for_status()
            for line in response.text.splitlines():
                # Basic parsing for hosts file format or a simple list of domains
                line = line.strip().split("#")[0].strip()
                if line:
                    # Handle hosts file format (e.g., "0.0.0.0 example.com")
                    parts = line.split()
                    if len(parts) > 1:
                        domain = parts[-1]
                        # Avoid adding IP addresses as domains
                        if domain != '0.0.0.0' and domain != '127.0.0.1':
                             domains.add(domain)
                    else:
                        domains.add(parts[0])

        except requests.exceptions.RequestException as e:
            print(f"Error fetching {url}: {e}")
    return domains

def update_denylist(domains_to_add, domains_to_remove):
    """Adds and removes domains from the NextDNS denylist in bulk."""
    headers = {
        "X-Api-Key": API_KEY,
        "Content-Type": "application/json"
    }

    # Use the requests 'json' parameter to handle serialization and headers
    session = requests.Session()
    session.headers.update(headers)

    if domains_to_add:
        # The API expects an object with a "rules" key
        add_payload = {"rules": [{"id": domain} for domain in domains_to_add]}
        response = session.post(NEXTDNS_API_URL, json=add_payload)
        if response.status_code == 204:
            print(f"Successfully added {len(domains_to_add)} domains.")
        else:
            print(f"Error adding domains: {response.status_code} - {response.text}")

    if domains_to_remove:
        # The DELETE request also expects a payload of rules to remove
        remove_payload = {"rules": [{"id": domain} for domain in domains_to_remove]}
        response = session.delete(NEXTDNS_API_URL, json=remove_payload)
        if response.status_code == 204:
            print(f"Successfully removed {len(domains_to_remove)} domains.")
        else:
            print(f"Error removing domains: {response.status_code} - {response.text}")


if __name__ == "__main__":
    # Ensure environment variables are set
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
        update_denylist(domains_to_add, domains_to_remove)

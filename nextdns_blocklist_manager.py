import os
import requests
import json

# Your NextDNS API Key and Profile ID
# It is recommended to store these as secrets in your GitHub repository
API_KEY = os.environ.get("NEXTDNS_API_KEY")
PROFILE_ID = os.environ.get("NEXTDNS_PROFILE_ID")

NEXTDNS_API_URL = f"https://api.nextdns.io/profiles/{PROFILE_ID}/denylist"

def get_current_denylist():
    """Fetches the current denylist from NextDNS."""
    headers = {"X-Api-Key": API_KEY}
    response = requests.get(NEXTDNS_API_URL, headers=headers)
    response.raise_for_status()
    return {item['domain'] for item in response.json()['data']}

def get_remote_blocklist_domains(blocklist_urls):
    """Fetches and parses domains from a list of blocklist URLs."""
    domains = set()
    for url in blocklist_urls:
        try:
            response = requests.get(url)
            response.raise_for_status()
            for line in response.text.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    domains.add(line.split()[0])
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {url}: {e}")
    return domains

def update_denylist(domains_to_add, domains_to_remove):
    """Adds and removes domains from the NextDNS denylist."""
    headers = {
        "X-Api-Key": API_KEY,
        "Content-Type": "application/json"
    }

    if domains_to_add:
        add_payload = [{"domain": domain} for domain in domains_to_add]
        response = requests.post(NEXTDNS_API_URL, headers=headers, data=json.dumps(add_payload))
        if response.status_code == 204:
            print(f"Successfully added {len(domains_to_add)} domains.")
        else:
            print(f"Error adding domains: {response.status_code} - {response.text}")

    if domains_to_remove:
        for domain in domains_to_remove:
            delete_url = f"{NEXTDNS_API_URL}/{domain}"
            response = requests.delete(delete_url, headers=headers)
            if response.status_code != 204:
                print(f"Error removing domain {domain}: {response.status_code} - {response.text}")
        print(f"Successfully processed {len(domains_to_remove)} domains for removal.")


if __name__ == "__main__":
    with open("blocklists.txt", "r") as f:
        blocklist_urls = [line.strip() for line in f if line.strip()]

    print("Fetching remote blocklists...")
    remote_domains = get_remote_blocklist_domains(blocklist_urls)
    print(f"Found {len(remote_domains)} unique domains in remote lists.")

    print("Fetching current NextDNS denylist...")
    current_denylist = get_current_denylist()
    print(f"Found {len(current_denylist)} domains in your NextDNS denylist.")

    domains_to_add = remote_domains - current_denylist
    domains_to_remove = current_denylist - remote_domains

    if not domains_to_add and not domains_to_remove:
        print("No changes to your denylist are needed.")
    else:
        update_denylist(domains_to_add, domains_to_remove)

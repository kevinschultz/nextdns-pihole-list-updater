import os
import requests
import json

# Your NextDNS API Key and Profile ID from GitHub Secrets
API_KEY = os.environ.get("NEXTDNS_API_KEY")
PROFILE_ID = os.environ.get("NEXTDNS_PROFILE_ID")

# The API endpoint for the denylist
NEXTDNS_API_URL = f"https://api.nextdns.io/profiles/{PROFILE_ID}/denylist"

def get_remote_blocklist_domains(blocklist_urls):
    """
    Fetches and parses unique domains from a list of blocklist URLs.
    """
    domains = set()
    session = requests.Session()
    for url in blocklist_urls:
        try:
            # Setting a timeout is a good practice
            response = session.get(url, timeout=30)
            response.raise_for_status()
            for line in response.text.splitlines():
                # Basic parsing for hosts file format or a simple list of domains
                # Removes comments and extracts the domain
                line = line.strip().split("#")[0].strip()
                if line:
                    # Handle hosts file format (e.g., "0.0.0.0 example.com")
                    parts = line.split()
                    domain = parts[-1]
                    # A simple check to avoid adding IP addresses as domains
                    if domain != '0.0.0.0' and domain != '127.0.0.1':
                        domains.add(domain)
        except requests.exceptions.RequestException as e:
            print(f"Warning: Could not fetch {url}. Error: {e}")
    return domains

def replace_denylist(domains_to_block):
    """
    Replaces the entire NextDNS denylist with the provided set of domains.
    """
    print(f"Preparing to replace denylist with {len(domains_to_block)} domains.")

    # According to the documentation, the PUT payload is an array of objects.
    # Each object must have an "id" (the domain) and an "active" status.
    payload = [{"id": domain, "active": True} for domain in domains_to_block]

    headers = {
        "X-Api-Key": API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        # We use a PUT request to replace the entire list, which is the correct
        # method for bulk updates as per the official API documentation.
        response = requests.put(NEXTDNS_API_URL, headers=headers, json=payload, timeout=120)

        # A successful request will return a 204 No Content status
        response.raise_for_status()

        print("Successfully replaced the NextDNS denylist.")
        print(f"Your denylist now contains {len(domains_to_block)} domains.")

    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to update the denylist.")
        print(f"Status Code: {e.response.status_code if e.response else 'N/A'}")
        print(f"Response Body: {e.response.text if e.response else 'N/A'}")
        # Exit with an error code to make the GitHub Action fail
        exit(1)

if __name__ == "__main__":
    if not API_KEY or not PROFILE_ID:
        raise ValueError("NEXTDNS_API_KEY and NEXTDNS_PROFILE_ID environment variables must be set in GitHub secrets.")

    with open("blocklists.txt", "r") as f:
        blocklist_urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    print("Fetching domains from remote blocklists...")
    remote_domains = get_remote_blocklist_domains(blocklist_urls)
    
    if not remote_domains:
        print("No domains were fetched. Aborting to avoid clearing the denylist.")
        exit(1)

    print(f"Found {len(remote_domains)} unique domains across all lists.")

    replace_denylist(remote_domains)

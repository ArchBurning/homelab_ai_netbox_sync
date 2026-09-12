import json
import yaml
import requests
import concurrent.futures
from netmiko import ConnectHandler
from ollama import Client

# Load environment configuration
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

NETBOX_URL = config["netbox"]["url"].rstrip("/")
NETBOX_TOKEN = config["netbox"]["token"]
OLLAMA_CLIENT = Client(host=config["ollama"]["host"])
OLLAMA_MODEL = config["ollama"]["model"]

# Automatically support classic v1 tokens or new v2 tokens
if NETBOX_TOKEN.startswith("Bearer "):
    auth_header = NETBOX_TOKEN
elif NETBOX_TOKEN.startswith("nbt_"):
    auth_header = f"Bearer {NETBOX_TOKEN}"
else:
    auth_header = f"Token {NETBOX_TOKEN}"

HEADERS = {
    "Authorization": auth_header,
    "Content-Type": "application/json",
    "Accept": "application/json",
}

def parse_with_ai(raw_cli: str) -> dict:
    prompt = f"""
You are a universal network hardware telemetry parser.
Extract device information from this raw CLI output (from Cisco, MikroTik, Ubiquiti, VyOS, etc.).

Return ONLY a valid JSON object matching this schema:
{{
  "serial_number": "<hardware/board serial number or null>",
  "model": "<hardware model/platform or null>",
  "software_version": "<OS or firmware version or null>"
}}

Do not include markdown code fences (like ```json), commentary, or extra text.

CLI Output:
{raw_cli}
"""
    response = OLLAMA_CLIENT.chat(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
        format="json",
        options={"temperature": 0.0}
    )
    
    clean_json = response.message.content.strip()
    return json.loads(clean_json)

def update_netbox(netbox_id: int, parsed_data: dict, device_name: str):
    url = f"{NETBOX_URL}/api/dcim/devices/{netbox_id}/"
    
    payload = {}
    if parsed_data.get("serial_number"):
        payload["serial"] = parsed_data["serial_number"]
    
    version = parsed_data.get("software_version", "Unknown")
    model = parsed_data.get("model", "Unknown")
    payload["comments"] = f"Auto-synced via Local AI ({OLLAMA_MODEL}).\nModel: {model}\nOS Version: {version}"

    response = requests.patch(url, headers=HEADERS, json=payload)
    if response.status_code == 200:
        print(f"[SUCCESS] NetBox updated for {device_name} (ID: {netbox_id}) -> Serial: {payload.get('serial')}")
    else:
        print(f"[!] NetBox update failed for {device_name}: {response.status_code} - {response.text}")

def sync_device(dev: dict):
    name = dev.get("name", dev["host"])
    netbox_id = dev["netbox_id"]
    command = dev.get("command", "show version")

    netmiko_params = {
        "device_type": dev["device_type"],
        "host": dev["host"],
        "username": dev["username"],
        "password": dev["password"],
    }

    try:
        print(f"[*] [{name}] Connecting via SSH ({dev['host']})...")
        with ConnectHandler(**netmiko_params) as ssh:
            raw_cli = ssh.send_command(command)
        
        print(f"[*] [{name}] Parsing CLI with {OLLAMA_MODEL}...")
        parsed_data = parse_with_ai(raw_cli)
        print(f"[+] [{name}] Extracted: {json.dumps(parsed_data, indent=2)}")

        print(f"[*] [{name}] Pushing updates to NetBox...")
        update_netbox(netbox_id, parsed_data, name)

    except Exception as e:
        print(f"[-] [{name}] Error: {e}")

def main():
    devices = config.get("devices", [])
    print(f"[*] Starting AI Network Sync for {len(devices)} device(s)...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(sync_device, devices)

if __name__ == "__main__":
    main()

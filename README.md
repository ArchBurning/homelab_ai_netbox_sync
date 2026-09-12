# Local AI Network Telemetry & NetBox Auto-Sync

An on-premises, privacy-first network automation pipeline that connects to diverse network hardware via SSH, normalizes messy vendor-specific CLI output using a local LLM via Ollama (`qwen2.5-coder:3b`), and automatically reconciles hardware inventory directly into **NetBox** via its REST API.

---

## Why Local AI for Network Telemetry?

Traditional multi-vendor network parsing usually requires brittle regular expressions, maintaining massive `TextFSM` / `ntc-templates` libraries, or writing custom parsers for every vendor CLI flavor (Cisco IOS, AireOS/Mobility Express, Junos, RouterOS, etc.).

This pipeline replaces static regex with a lightweight, local small-language-model:
* **Zero Cloud Data Leakage:** Hostnames, serial numbers, firmware versions, and topology details stay strictly local on your management plane.
* **Vendor-Agnostic Ingestion:** A single structured prompt normalizes unstructured CLI blocks into a strict, validated JSON schema.
* **NetBox Cloud & On-Prem Support:** Built-in compatibility for NetBox REST API v2 Bearer tokens and classic v1 tokens.
* **Concurrent Execution:** Uses multi-threaded worker pools to query and update multiple devices simultaneously.

---

## Architecture Flow

```text
[ Network Hardware ]
 (ISR, Catalyst, WLC, etc.)
         │
         │  SSH (Netmiko)
         ▼
[ CLI Raw Output ]
         │
         │  Local Inference (REST)
         ▼
[ Local Ollama Instance ]  ──► (qwen2.5-coder:3b / JSON Mode)
         │
         │  Normalized Schema
         ▼
{ "serial_number": "...", "model": "...", "software_version": "..." }
         │
         │  REST API (PATCH)
         ▼
[ NetBox DCIM / IPAM ]

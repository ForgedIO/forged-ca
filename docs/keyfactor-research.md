# Keyfactor — Capability Research

**Snapshot date:** 2026-05-24
**Status:** Background research for post-MVP roadmap planning. Not a design doc.
**Related roadmap entry:** "Endpoint cert lifecycle for non-ACME devices" in `docs/roadmap.md` (v2+).

## Why this document exists

User saw Keyfactor presented at a conference and recognized the shape of a feature surface ForgedCA could plausibly grow into after the current MVP slices land. This file captures Keyfactor's product line and capability surface so the decision can be revisited with real data rather than memory.

## Strategic positioning (decided 2026-05-24)

- **ForgedCA core stays internal-PKI only.** Keyfactor spans both internal and external (public/trusted, browser-rooted) PKI. We explicitly don't — keeping the surface small and the compliance burden tractable for an open-source project.
- **Endpoint lifecycle management is a candidate for a *paid SaaS tier*, not OSS core**, leveraging an existing AWS tenant + Marketplace distribution. The OSS product stays focused on "easy to deploy internal PKI + ACME."
- **Not now.** Every existing slice in `docs/roadmap.md` lands first. Do not propose, scaffold, or design this surface area until the current slice sequence completes.

## The competitive gap

The **CA layer** has strong open-source incumbents — EJBCA CE and step-ca (which we ride on). The **lifecycle layer** — discovery + non-ACME renewal + dashboard — has no strong OSS competitor. That's the differentiation opportunity if/when we extend.

## Product line

- **Keyfactor Command** — the cert lifecycle / discovery / dashboard product. This is the one matching the conference pitch. On-prem or SaaS. [Product page](https://www.keyfactor.com/products/command/)
- **Keyfactor EJBCA** (Enterprise + open-source Community Edition) — the CA engine. Supports ACME, SCEP, EST, CMP, Microsoft Autoenrollment, REST/SOAP. [EJBCA Enterprise](https://www.keyfactor.com/products/ejbca-enterprise/)
- **Keyfactor ACME** — standalone ACME front-end that talks to Command and brokers to whichever CA Command is wired to. [ACME intro](https://software.keyfactor.com/Guides/ACME/Current/Content/ACME/Introduction.htm)
- **Keyfactor Signum** — code/artifact signing. Different problem space, ignore.

## Capability surface

### 1. Cert discovery

- Two job types: *Discovery* (TLS endpoint scan across IP/port ranges with and without SNI) and *Monitoring* (re-check known certs). [SSL Discovery docs](https://software.keyfactor.com/Core-OnPrem/Current/Content/ReferenceGuide/SSLDiscovery.htm)
- Cert-store discovery also scans hosts for cert *stores* (Windows store, F5 stores, etc.) so they can be brought under management. [Cert Store Discovery](https://software.keyfactor.com/Core-OnPrem/v10.0/Content/ReferenceGuide/Certificate%20Store%20Discovery.htm)
- Real-time CA sync pulls issuance records directly from supported CAs.
- **OSS viability:** Easy–Moderate. TLS endpoint scanning is a few hundred lines of Go. The inventory model, dedup, and ownership tagging is the real design work.

### 2. Non-ACME renewal mechanics

- **Universal Orchestrator** — a .NET service installed on a host with network reach to target devices. Polls Command outbound for jobs, executes locally, returns results. [UO docs](https://pre-reqs.keyfactor.com/customer-requirements/current/universal-orchestrator-extensions)
- **Per-device extensions** as separate plugins speaking each device's native API:
  - Palo Alto (XML API with API user creds) — [paloalto-firewall-orchestrator](https://github.com/Keyfactor/paloalto-firewall-orchestrator)
  - F5 BIG-IP (REST), Cisco ASA, Citrix NetScaler, IIS/Windows cert store (WinRM), iDRAC/iLO, and others
- 42+ orchestrator extensions cover F5, Palo Alto, Cisco ASA, Citrix, Fortinet, Imperva, Kemp, A10, AWS ACM, Azure Key Vault, GCP LB, Cloudflare, Fastly, K8s, vCenter, IBM DataPower, Aruba ClearPass, IP cameras. [Integration catalog](https://keyfactor.github.io/integrations-catalog/content/orchestrator)
- Operations per extension: Add, Remove, Inventory, Reenrollment.
- **OSS viability:** Moderate framework, Hard breadth. The orchestrator-as-poller pattern is a weekend. The 42 device drivers are the moat — each one is bespoke, version-sensitive, and demands a test device. Realistic OSS path: ship 3–5 high-value drivers and rely on community contributions for the long tail.

### 3. Orchestrators / agents

- **Universal Orchestrator** is the workhorse (.NET on Windows/Linux).
- **Bash Orchestrator** for lightweight Linux host renewal.
- Polling is *outbound* from orchestrator to Command — Command never reaches into the network where the orchestrator lives. Good for DMZ / segmented networks.
- **OSS viability:** Easy. Polling-agent pattern maps directly onto ForgedCA federation (CSRs go up, signed certs come down). Same wire, different job payload.

### 4. Lifecycle dashboard

- Single inventory view across CAs, network scans, and managed stores. Filter/search by CN, SAN, issuer, expiry, key algo. [Dashboard docs](https://software.keyfactor.com/Core-OnPrem/v10.4/Content/ReferenceGuide/Dashboard.htm)
- Expiry alerts via email / SIEM / ITSM (ServiceNow).
- Weak-crypto reporting (SHA-1, MD5, RSA <2048, weak ECC).
- Ownership / tagging on every cert; drives alert routing.
- Audit trail of every issuance, revocation, orchestrator job.
- **OSS viability:** Easy–Moderate. CRUD UI over a cert table you'd build anyway. Alert routing and ownership metadata are well-trodden.

### 5. ACME story

- EJBCA has a native RFC 8555 ACME provisioner with multiple aliases and EAB (MAC + asymmetric). [EJBCA ACME](https://docs.keyfactor.com/ejbca/latest/acme)
- Keyfactor ACME is a *separate* component fronting Command to broker to any CA Command knows about.
- **OSS viability:** Already done. step-ca's ACME provisioner is what ForgedCA already rides on.

### 6. CA backends supported (AnyCA Gateway)

- Plugin framework where each plugin talks to one CA. [Gateways docs](https://software.keyfactor.com/Core-OnPrem/Current/Content/Gateways/Introduction.htm)
- Out-of-box: Microsoft ADCS, EJBCA, DigiCert CertCentral / MPKI, Entrust, GlobalSign, Sectigo, AWS Private CA, GCP CAS, plus a generic REST gateway template.
- Command is CA-agnostic by design — the opposite of ForgedCA's "we are the CA" framing.
- **OSS viability:** Probably out of reach AND not desirable. Each gateway is a paid integration plus vendor relationship. ForgedCA's "we are the CA, period" positioning is cleaner. (An "import existing CA's certs into our inventory for visibility" feature might be worth a small slice — without brokering issuance.)

## Top 3 capabilities worth ForgedCA absorbing post-MVP

Ranked by user-visible value vs. implementation cost.

1. **Lightweight poll-based orchestrator agent + 3–5 device drivers for non-ACME renewal.** The headline pitch. F5 BIG-IP (REST), Palo Alto (XML API), Windows cert store / IIS (WinRM or tiny Go agent), and a generic "SSH + drop file + run hook" driver covers ~60% of long-tail appliances. Reuse the federation polling channel. *Moderate effort, very high value.*

2. **TLS endpoint discovery scan.** "Scan 10.0.0.0/16 on :443, :8443, :9443" → dial each, grab cert, parse, classify as managed-by-us / managed-elsewhere / unmanaged. ~1 week for the scan engine; inventory schema is the real design. *Easy–Moderate effort, high value.*

3. **Expiry + weak-crypto dashboard with ownership tagging and email/webhook alerts.** Falls out for free once #1 and #2 give you the inventory table. Weak-crypto checks are trivial. Ownership tags + per-tag alert routing is the feature that makes a sysadmin actually trust the tool. *Easy effort, high value.*

## Explicitly not worth chasing

- **AnyCA Gateway-style multi-CA brokering** — dilutes the "we are the CA" positioning.
- **Code signing (Signum)** — different product, different audience.
- **The full 42-device orchestrator catalog** — community-contribution territory once #1's framework exists.

## Pricing data point

Keyfactor Command runs **~$75K–$200K/yr** depending on cert volume and support tier. ([Axelspire pricing analysis](https://axelspire.com/vault/vendors/keyfactor-command/)) The mid-market and SMB segments priced out of that are squarely the audience that would adopt an open-source equivalent — and would be the natural buyers of a ForgedCA paid SaaS tier built around the Top 3 above. There is real demand here, not a hypothetical market.

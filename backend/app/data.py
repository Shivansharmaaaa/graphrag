"""Synthetic CTI corpus compiled from widely reported public campaigns.

Documents are original composites for education — not copies of vendor reports.
Indicator values are well-known public examples or clearly fictional lab values.
"""

ACTORS = [
    {
        "id": "apt28",
        "name": "APT28",
        "aliases": ["Fancy Bear", "Sofacy", "STRONTIUM", "Forest Blizzard"],
        "origin": "Russia",
        "sponsor": "GRU Unit 26165",
        "motivation": "espionage",
        "sophistication": "advanced",
    },
    {
        "id": "apt29",
        "name": "APT29",
        "aliases": ["Cozy Bear", "The Dukes", "NOBELIUM", "Midnight Blizzard"],
        "origin": "Russia",
        "sponsor": "SVR",
        "motivation": "espionage",
        "sophistication": "advanced",
    },
    {
        "id": "sandworm",
        "name": "Sandworm",
        "aliases": ["Voodoo Bear", "Telebots", "IRON VIKING", "Seashell Blizzard"],
        "origin": "Russia",
        "sponsor": "GRU Unit 74455",
        "motivation": "sabotage",
        "sophistication": "advanced",
    },
    {
        "id": "lazarus",
        "name": "Lazarus Group",
        "aliases": ["Hidden Cobra", "LABYRINTH CHOLLIMA", "Guardians of Peace"],
        "origin": "North Korea",
        "sponsor": "RGB",
        "motivation": "espionage-and-crime",
        "sophistication": "advanced",
    },
    {
        "id": "fin7",
        "name": "FIN7",
        "aliases": ["Carbanak", "Navigator Group", "GOLD NIAGARA"],
        "origin": "Unknown",
        "sponsor": None,
        "motivation": "financial",
        "sophistication": "advanced",
    },
    {
        "id": "apt41",
        "name": "APT41",
        "aliases": ["Winnti", "Barium", "Wicked Panda", "BRONZE ATLAS"],
        "origin": "China",
        "sponsor": "MSS-linked",
        "motivation": "espionage-and-crime",
        "sophistication": "advanced",
    },
    {
        "id": "scattered-spider",
        "name": "Scattered Spider",
        "aliases": ["UNC3944", "Starfraud", "Muddled Libra"],
        "origin": "English-speaking",
        "sponsor": None,
        "motivation": "financial",
        "sophistication": "intermediate",
    },
    {
        "id": "kimsuky",
        "name": "Kimsuky",
        "aliases": ["Velvet Chollima", "Black Banshee", "Thallium"],
        "origin": "North Korea",
        "sponsor": "RGB",
        "motivation": "espionage",
        "sophistication": "intermediate",
    },
]

CAMPAIGNS = [
    {
        "id": "dnc-2016",
        "name": "DNC 2016 Compromise",
        "year": 2016,
        "target_sector": "government",
        "summary": "Coordinated intelligence collection against the US Democratic National Committee using spearphishing and implant deployment.",
    },
    {
        "id": "solarwinds",
        "name": "SolarWinds Supply Chain",
        "year": 2020,
        "target_sector": "technology",
        "summary": "SUNBURST backdoor inserted into SolarWinds Orion updates, enabling follow-on access to downstream government and tech customers.",
    },
    {
        "id": "notpetya",
        "name": "NotPetya",
        "year": 2017,
        "target_sector": "critical-infrastructure",
        "summary": "Wiper disguised as ransomware, initially seeded via the MeDoc tax-software update channel, causing global operational disruption.",
    },
    {
        "id": "wannacry",
        "name": "WannaCry",
        "year": 2017,
        "target_sector": "healthcare",
        "summary": "Wormable ransomware exploiting SMBv1 EternalBlue, with outsized impact on hospitals and unpatched Windows estates.",
    },
    {
        "id": "swift-bangladesh",
        "name": "Bangladesh Bank SWIFT Heist",
        "year": 2016,
        "target_sector": "finance",
        "summary": "Fraudulent SWIFT messages used to attempt theft of nearly one billion USD from Bangladesh Bank's NY Fed account.",
    },
    {
        "id": "industroyer",
        "name": "Industroyer / CrashOverride",
        "year": 2016,
        "target_sector": "energy",
        "summary": "ICS-aware malware used to switch breakers in the Ukrainian power grid, demonstrating purpose-built electric-sector sabotage.",
    },
    {
        "id": "3cx",
        "name": "3CX Supply Chain",
        "year": 2023,
        "target_sector": "technology",
        "summary": "Trojanized 3CXDesktopApp installers used to stage follow-on payloads against selected organizations.",
    },
    {
        "id": "carb-pos",
        "name": "FIN7 Hospitality POS",
        "year": 2017,
        "target_sector": "hospitality",
        "summary": "Point-of-sale memory scraping campaigns against restaurants and hotels using Carbanak-family tooling.",
    },
]

MALWARE = [
    {"id": "x-agent", "name": "X-Agent", "family": "Sofacy", "kind": "backdoor"},
    {"id": "koadic", "name": "Koadic", "family": "COM-based", "kind": "post-exploitation"},
    {"id": "sunburst", "name": "SUNBURST", "family": "Solorigate", "kind": "backdoor"},
    {"id": "teardrop", "name": "TEARDROP", "family": "Solorigate", "kind": "dropper"},
    {"id": "notpetya-wiper", "name": "NotPetya", "family": "Petya-derived", "kind": "wiper"},
    {"id": "industroyer-mal", "name": "Industroyer", "family": "CrashOverride", "kind": "ics"},
    {"id": "wannacry-ransom", "name": "WannaCry", "family": "EternalBlue-worm", "kind": "ransomware"},
    {"id": "carbanak", "name": "Carbanak", "family": "Anunak", "kind": "backdoor"},
    {"id": "griffon", "name": "GRIFFON", "family": "FIN7", "kind": "downloader"},
    {"id": "cobalt-strike", "name": "Cobalt Strike", "family": "Beacon", "kind": "post-exploitation"},
    {"id": "shadowpad", "name": "ShadowPad", "family": "Winnti", "kind": "backdoor"},
    {"id": "mimikatz", "name": "Mimikatz", "family": "credential", "kind": "tool"},
    {"id": "applejeus", "name": "AppleJeus", "family": "Lazarus", "kind": "trojan"},
]

TECHNIQUES = [
    {"id": "T1566", "name": "Phishing", "tactic": "initial-access"},
    {"id": "T1195", "name": "Supply Chain Compromise", "tactic": "initial-access"},
    {"id": "T1021", "name": "Remote Services", "tactic": "lateral-movement"},
    {"id": "T1003", "name": "OS Credential Dumping", "tactic": "credential-access"},
    {"id": "T1486", "name": "Data Encrypted for Impact", "tactic": "impact"},
    {"id": "T1485", "name": "Data Destruction", "tactic": "impact"},
    {"id": "T1071", "name": "Application Layer Protocol", "tactic": "command-and-control"},
    {"id": "T1090", "name": "Proxy", "tactic": "command-and-control"},
    {"id": "T1059", "name": "Command and Scripting Interpreter", "tactic": "execution"},
    {"id": "T1078", "name": "Valid Accounts", "tactic": "defense-evasion"},
]

INFRASTRUCTURE = [
    {"id": "infra-decoy-gov", "value": "accounts-mail-service.net", "kind": "c2-domain", "notes": "Credential-harvest lookalike used in diplomatic spearphish."},
    {"id": "infra-svchost-cdn", "value": "cdn-svchost-update.com", "kind": "c2-domain", "notes": "Beacon staging domain later reused across two clusters."},
    {"id": "infra-msupdate", "value": "microsoft-update-check.net", "kind": "c2-domain", "notes": "Fake update check-in used by Beacon stagers."},
    {"id": "infra-solorigate", "value": "avsvmcloud.com", "kind": "c2-domain", "notes": "Publicly reported SUNBURST C2 domain."},
    {"id": "infra-wannacry-kill", "value": "iuqerfsodp9ifjaposdfjhgosurijfaewrwergwea.com", "kind": "kill-switch", "notes": "WannaCry kill-switch domain."},
    {"id": "infra-pos-relay", "value": "pay-relay-int.com", "kind": "exfil-domain", "notes": "Card-data relay used in hospitality campaigns."},
    {"id": "infra-vps-185", "value": "185.86.77.12", "kind": "c2-ip", "notes": "Bulletproof VPS observed in GRU-linked clusters."},
    {"id": "infra-vps-shared", "value": "91.219.236.44", "kind": "c2-ip", "notes": "IP later seen serving both Beacon and X-Agent callbacks."},
    {"id": "infra-crypto-panel", "value": "trade-helper-app.com", "kind": "watering-hole", "notes": "Fake cryptocurrency trading helper used by Lazarus."},
    {"id": "infra-sunburst-ip", "value": "13.59.205.66", "kind": "c2-ip", "notes": "Second-stage host contacted after SUNBURST dormancy (lab value)."},
    {"id": "infra-apt41-vps", "value": "45.77.12.90", "kind": "c2-ip", "notes": "VPS serving ShadowPad and Beacon for APT41 (lab value)."},
    {"id": "infra-leak-onion", "value": "b7c3e1a90f44d21c99aa.onion", "kind": "leak-site", "notes": "Rotating ransom leak-site hostname (lab value)."},
    {"id": "infra-kimsuky-phish", "value": "mail-login-secure.gov-service.net", "kind": "phishing-domain", "notes": "Government-themed credential harvest page."},
]

# TTLs are operational (hours to days). Three indicators are deliberately short-lived
# (cdn-svchost-update.com 120 s, the .onion leak site 90 s, microsoft-update-check.net 300 s)
# so UC4 — an IOC TTL reaching zero while the graph keeps its history — is visible in a demo.
INDICATORS = [
    {"value": "185.86.77.12", "type": "ip", "actor": "apt28", "campaign": "dnc-2016", "severity": "high", "ttl": 604800},
    {"value": "91.219.236.44", "type": "ip", "actor": "apt28", "campaign": "dnc-2016", "severity": "critical", "ttl": 259200},
    {"value": "accounts-mail-service.net", "type": "domain", "actor": "apt28", "campaign": "dnc-2016", "severity": "high", "ttl": 172800},
    {"value": "avsvmcloud.com", "type": "domain", "actor": "apt29", "campaign": "solarwinds", "severity": "critical", "ttl": 1209600},
    {"value": "13.59.205.66", "type": "ip", "actor": "apt29", "campaign": "solarwinds", "severity": "high", "ttl": 86400},
    {"value": "cdn-svchost-update.com", "type": "domain", "actor": "apt29", "campaign": "solarwinds", "severity": "medium", "ttl": 120},
    {"value": "iuqerfsodp9ifjaposdfjhgosurijfaewrwergwea.com", "type": "domain", "actor": "lazarus", "campaign": "wannacry", "severity": "high", "ttl": 2592000},
    {"value": "trade-helper-app.com", "type": "domain", "actor": "lazarus", "campaign": "3cx", "severity": "high", "ttl": 432000},
    {"value": "pay-relay-int.com", "type": "domain", "actor": "fin7", "campaign": "carb-pos", "severity": "high", "ttl": 43200},
    {"value": "microsoft-update-check.net", "type": "domain", "actor": "scattered-spider", "campaign": "carb-pos", "severity": "medium", "ttl": 300},
    {"value": "45.77.12.90", "type": "ip", "actor": "apt41", "campaign": "3cx", "severity": "high", "ttl": 172800},
    {"value": "d1f2a9c4e8b7a001deadbeefcafebabe", "type": "hash", "actor": "sandworm", "campaign": "notpetya", "severity": "critical", "ttl": 2592000},
    {"value": "aa11bb22cc33dd44ee55ff6677889900", "type": "hash", "actor": "lazarus", "campaign": "wannacry", "severity": "critical", "ttl": 2592000},
    {"value": "b7c3e1a90f44d21c99aa.onion", "type": "domain", "actor": "scattered-spider", "campaign": "carb-pos", "severity": "medium", "ttl": 90},
    {"value": "mail-login-secure.gov-service.net", "type": "domain", "actor": "kimsuky", "campaign": "dnc-2016", "severity": "medium", "ttl": 21600},
]

# (from_label, from_id, rel, to_label, to_id)
RELATIONSHIPS = [
    ("ThreatActor", "apt28", "ATTRIBUTED_TO_CAMPAIGN", "Campaign", "dnc-2016"),
    ("ThreatActor", "apt29", "ATTRIBUTED_TO_CAMPAIGN", "Campaign", "dnc-2016"),
    ("ThreatActor", "apt29", "ATTRIBUTED_TO_CAMPAIGN", "Campaign", "solarwinds"),
    ("ThreatActor", "sandworm", "ATTRIBUTED_TO_CAMPAIGN", "Campaign", "notpetya"),
    ("ThreatActor", "sandworm", "ATTRIBUTED_TO_CAMPAIGN", "Campaign", "industroyer"),
    ("ThreatActor", "lazarus", "ATTRIBUTED_TO_CAMPAIGN", "Campaign", "wannacry"),
    ("ThreatActor", "lazarus", "ATTRIBUTED_TO_CAMPAIGN", "Campaign", "swift-bangladesh"),
    ("ThreatActor", "lazarus", "ATTRIBUTED_TO_CAMPAIGN", "Campaign", "3cx"),
    ("ThreatActor", "fin7", "ATTRIBUTED_TO_CAMPAIGN", "Campaign", "carb-pos"),
    ("ThreatActor", "scattered-spider", "ATTRIBUTED_TO_CAMPAIGN", "Campaign", "carb-pos"),
    ("ThreatActor", "apt41", "ATTRIBUTED_TO_CAMPAIGN", "Campaign", "3cx"),
    ("ThreatActor", "apt28", "USES", "Malware", "x-agent"),
    ("ThreatActor", "apt28", "USES", "Malware", "koadic"),
    ("ThreatActor", "apt28", "USES", "Malware", "mimikatz"),
    ("ThreatActor", "apt29", "USES", "Malware", "sunburst"),
    ("ThreatActor", "apt29", "USES", "Malware", "teardrop"),
    ("ThreatActor", "apt29", "USES", "Malware", "mimikatz"),
    ("ThreatActor", "sandworm", "USES", "Malware", "notpetya-wiper"),
    ("ThreatActor", "sandworm", "USES", "Malware", "industroyer-mal"),
    ("ThreatActor", "lazarus", "USES", "Malware", "wannacry-ransom"),
    ("ThreatActor", "lazarus", "USES", "Malware", "applejeus"),
    ("ThreatActor", "lazarus", "USES", "Malware", "cobalt-strike"),
    ("ThreatActor", "fin7", "USES", "Malware", "carbanak"),
    ("ThreatActor", "fin7", "USES", "Malware", "griffon"),
    ("ThreatActor", "fin7", "USES", "Malware", "cobalt-strike"),
    ("ThreatActor", "fin7", "USES", "Malware", "mimikatz"),
    ("ThreatActor", "scattered-spider", "USES", "Malware", "cobalt-strike"),
    ("ThreatActor", "scattered-spider", "USES", "Malware", "mimikatz"),
    ("ThreatActor", "apt41", "USES", "Malware", "shadowpad"),
    ("ThreatActor", "apt41", "USES", "Malware", "cobalt-strike"),
    ("ThreatActor", "kimsuky", "USES", "Malware", "mimikatz"),
    ("ThreatActor", "apt28", "SHARES_UNIT", "ThreatActor", "sandworm"),
    ("Campaign", "dnc-2016", "USES_MALWARE", "Malware", "x-agent"),
    ("Campaign", "solarwinds", "USES_MALWARE", "Malware", "sunburst"),
    ("Campaign", "solarwinds", "USES_MALWARE", "Malware", "teardrop"),
    ("Campaign", "notpetya", "USES_MALWARE", "Malware", "notpetya-wiper"),
    ("Campaign", "industroyer", "USES_MALWARE", "Malware", "industroyer-mal"),
    ("Campaign", "wannacry", "USES_MALWARE", "Malware", "wannacry-ransom"),
    ("Campaign", "carb-pos", "USES_MALWARE", "Malware", "carbanak"),
    ("Campaign", "carb-pos", "USES_MALWARE", "Malware", "griffon"),
    ("Campaign", "3cx", "USES_MALWARE", "Malware", "applejeus"),
    ("ThreatActor", "apt28", "USES_INFRA", "Infrastructure", "infra-decoy-gov"),
    ("ThreatActor", "apt28", "USES_INFRA", "Infrastructure", "infra-vps-185"),
    ("ThreatActor", "apt28", "USES_INFRA", "Infrastructure", "infra-vps-shared"),
    ("ThreatActor", "apt29", "USES_INFRA", "Infrastructure", "infra-solorigate"),
    ("ThreatActor", "apt29", "USES_INFRA", "Infrastructure", "infra-svchost-cdn"),
    ("ThreatActor", "sandworm", "USES_INFRA", "Infrastructure", "infra-vps-185"),
    ("ThreatActor", "lazarus", "USES_INFRA", "Infrastructure", "infra-wannacry-kill"),
    ("ThreatActor", "lazarus", "USES_INFRA", "Infrastructure", "infra-crypto-panel"),
    ("ThreatActor", "fin7", "USES_INFRA", "Infrastructure", "infra-pos-relay"),
    ("ThreatActor", "scattered-spider", "USES_INFRA", "Infrastructure", "infra-msupdate"),
    ("ThreatActor", "scattered-spider", "USES_INFRA", "Infrastructure", "infra-vps-shared"),
    ("ThreatActor", "apt41", "USES_INFRA", "Infrastructure", "infra-msupdate"),
    ("Campaign", "dnc-2016", "EMPLOYS", "Technique", "T1566"),
    ("Campaign", "dnc-2016", "EMPLOYS", "Technique", "T1071"),
    ("Campaign", "solarwinds", "EMPLOYS", "Technique", "T1195"),
    ("Campaign", "solarwinds", "EMPLOYS", "Technique", "T1078"),
    ("Campaign", "notpetya", "EMPLOYS", "Technique", "T1485"),
    ("Campaign", "notpetya", "EMPLOYS", "Technique", "T1195"),
    ("Campaign", "wannacry", "EMPLOYS", "Technique", "T1486"),
    ("Campaign", "industroyer", "EMPLOYS", "Technique", "T1485"),
    ("Campaign", "carb-pos", "EMPLOYS", "Technique", "T1566"),
    ("Campaign", "carb-pos", "EMPLOYS", "Technique", "T1003"),
    ("Campaign", "3cx", "EMPLOYS", "Technique", "T1195"),
    ("Campaign", "swift-bangladesh", "EMPLOYS", "Technique", "T1078"),
    ("ThreatActor", "apt28", "EMPLOYS", "Technique", "T1566"),
    ("ThreatActor", "apt29", "EMPLOYS", "Technique", "T1195"),
    ("ThreatActor", "fin7", "EMPLOYS", "Technique", "T1003"),
    ("ThreatActor", "scattered-spider", "EMPLOYS", "Technique", "T1078"),
    ("Malware", "mimikatz", "IMPLEMENTS", "Technique", "T1003"),
    ("Malware", "cobalt-strike", "IMPLEMENTS", "Technique", "T1071"),
    ("Malware", "cobalt-strike", "IMPLEMENTS", "Technique", "T1090"),
    ("Malware", "sunburst", "IMPLEMENTS", "Technique", "T1195"),
    ("Malware", "wannacry-ransom", "IMPLEMENTS", "Technique", "T1486"),
    ("Malware", "notpetya-wiper", "IMPLEMENTS", "Technique", "T1485"),
    ("Infrastructure", "infra-vps-shared", "HOSTS", "Malware", "x-agent"),
    ("Infrastructure", "infra-vps-shared", "HOSTS", "Malware", "cobalt-strike"),
    ("Infrastructure", "infra-msupdate", "HOSTS", "Malware", "cobalt-strike"),
    ("Infrastructure", "infra-solorigate", "HOSTS", "Malware", "sunburst"),
    ("Infrastructure", "infra-vps-185", "HOSTS", "Malware", "x-agent"),
    ("Infrastructure", "infra-vps-185", "HOSTS", "Malware", "notpetya-wiper"),
    ("ThreatActor", "apt29", "USES_INFRA", "Infrastructure", "infra-sunburst-ip"),
    ("ThreatActor", "apt41", "USES_INFRA", "Infrastructure", "infra-apt41-vps"),
    ("ThreatActor", "scattered-spider", "USES_INFRA", "Infrastructure", "infra-leak-onion"),
    ("ThreatActor", "kimsuky", "USES_INFRA", "Infrastructure", "infra-kimsuky-phish"),
    ("Infrastructure", "infra-sunburst-ip", "HOSTS", "Malware", "teardrop"),
    ("Infrastructure", "infra-apt41-vps", "HOSTS", "Malware", "shadowpad"),
    ("Infrastructure", "infra-apt41-vps", "HOSTS", "Malware", "cobalt-strike"),
    ("Infrastructure", "infra-crypto-panel", "HOSTS", "Malware", "applejeus"),
    ("Infrastructure", "infra-pos-relay", "HOSTS", "Malware", "carbanak"),
]

# Hash indicators observed as file artefacts of a malware family (Malware -[:HAS_IOC]-> Indicator).
# Network indicators are linked Infrastructure -[:OBSERVED_AS]-> Indicator automatically by value.
MALWARE_HASHES = [
    ("notpetya-wiper", "d1f2a9c4e8b7a001deadbeefcafebabe"),
    ("wannacry-ransom", "aa11bb22cc33dd44ee55ff6677889900"),
]

VICTIMS = [
    {"id": "vic-dnc", "name": "Democratic National Committee", "sector": "government", "country": "US"},
    {"id": "vic-solar", "name": "SolarWinds customers", "sector": "technology", "country": "US"},
    {"id": "vic-nhs", "name": "National Health Service", "sector": "healthcare", "country": "UK"},
    {"id": "vic-ua-grid", "name": "Ukrainian power distribution", "sector": "energy", "country": "UA"},
    {"id": "vic-bd-bank", "name": "Bangladesh Bank", "sector": "finance", "country": "BD"},
    {"id": "vic-hospitality", "name": "US restaurant chains", "sector": "hospitality", "country": "US"},
    {"id": "vic-maersk", "name": "Global shipping operator", "sector": "logistics", "country": "DK"},
    {"id": "vic-crypto", "name": "Cryptocurrency exchanges", "sector": "finance", "country": "multi"},
]

VICTIM_RELS = [
    ("Campaign", "dnc-2016", "TARGETS", "Victim", "vic-dnc"),
    ("Campaign", "solarwinds", "TARGETS", "Victim", "vic-solar"),
    ("Campaign", "wannacry", "TARGETS", "Victim", "vic-nhs"),
    ("Campaign", "industroyer", "TARGETS", "Victim", "vic-ua-grid"),
    ("Campaign", "notpetya", "TARGETS", "Victim", "vic-maersk"),
    ("Campaign", "notpetya", "TARGETS", "Victim", "vic-ua-grid"),
    ("Campaign", "swift-bangladesh", "TARGETS", "Victim", "vic-bd-bank"),
    ("Campaign", "carb-pos", "TARGETS", "Victim", "vic-hospitality"),
    ("Campaign", "3cx", "TARGETS", "Victim", "vic-crypto"),
    ("ThreatActor", "lazarus", "TARGETS", "Victim", "vic-crypto"),
    ("ThreatActor", "fin7", "TARGETS", "Victim", "vic-hospitality"),
]

REPORTS = [
    {
        "id": "rpt-001",
        "title": "Spearphishing against political organizations: overlapping GRU tradecraft",
        "source": "NEXUS Lab",
        "date": "2017-01-14",
        "tlp": "AMBER",
        "confidence": "high",
        "actors": ["apt28", "apt29", "sandworm"],
        "campaigns": ["dnc-2016"],
        "malware": ["x-agent"],
        "iocs": ["185.86.77.12", "accounts-mail-service.net", "91.219.236.44"],
        "body": (
            "Analysts reviewing the 2016 Democratic National Committee intrusion found two distinct Russian clusters "
            "on the same victim estate. APT28 deployed X-Agent beacons that checked in to 185.86.77.12 and the "
            "lookalike domain accounts-mail-service.net. A second implant set, consistent with APT29, used quieter "
            "token theft and did not share the X-Agent callback path. The IP 91.219.236.44 later answered both "
            "X-Agent and Cobalt Strike Beacon callbacks, making it a rare piece of shared infrastructure rather than "
            "proof of a single operator. Separately, Sandworm — another GRU unit — has been observed using 185.86.77.12 "
            "during destructive staging, which is why graph traversal from that address yields both espionage and sabotage "
            "clusters. Spearphishing remains the common initial-access technique across these GRU-linked campaigns."
        ),
        # schema variation: nested attribution
        "attribution": {"country": "Russia", "units": ["GRU 26165", "GRU 74455", "SVR"], "confidence": 0.82},
    },
    {
        "id": "rpt-002",
        "title": "SUNBURST and the SolarWinds build-system insert",
        "source": "NEXUS Lab",
        "date": "2021-02-02",
        "tlp": "GREEN",
        "confidence": "high",
        "actors": ["apt29"],
        "campaigns": ["solarwinds"],
        "malware": ["sunburst", "teardrop"],
        "iocs": ["avsvmcloud.com", "13.59.205.66"],
        "body": (
            "The SolarWinds supply-chain campaign inserted the SUNBURST backdoor into Orion platform updates. "
            "After installation, SUNBURST waited through a dormant period, then resolved C2 via avsvmcloud.com "
            "using subdomain encoding. Selected victims received TEARDROP, a memory-only dropper used to stage "
            "follow-on implants. Valid accounts and signed software allowed the actor to blend into ordinary update "
            "traffic. This is a canonical case where a document store is appropriate: the report mixes narrative, "
            "DNS patterns, and victim verticals without a stable relational schema. APT29's motivation was strategic "
            "espionage, not immediate destruction, which distinguishes SolarWinds from Sandworm's NotPetya wiper."
        ),
        "build_pipeline": {"product": "Orion", "vector": "trojanized MSI", "signed": True},
        "mitre": ["T1195", "T1078", "T1071"],
    },
    {
        "id": "rpt-003",
        "title": "NotPetya was a wiper: MeDoc, EternalBlue, and collateral logistics damage",
        "source": "NEXUS Lab",
        "date": "2018-06-11",
        "tlp": "WHITE",
        "confidence": "high",
        "actors": ["sandworm"],
        "campaigns": ["notpetya"],
        "malware": ["notpetya-wiper"],
        "iocs": ["d1f2a9c4e8b7a001deadbeefcafebabe"],
        "body": (
            "NotPetya presented a ransom note but lacked a reliable recovery path. The initial seed was a trojanized "
            "update of the Ukrainian MeDoc accounting package — a supply-chain insert — after which the worm spread "
            "with EternalBlue and credential reuse. Shipping, pharma, and legal firms outside Ukraine were collateral, "
            "including a global shipping operator whose terminals halted. Sandworm, GRU Unit 74455, is the attributed "
            "actor. Graph context matters: Sandworm shares a parent service with APT28, and both have used the VPS "
            "185.86.77.12, but NotPetya's objective was destruction (T1485), not collection. Comparing this report "
            "semantically with Industroyer reporting surfaces the same actor's ICS sabotage mandate."
        ),
        "impact": {"ransom_plausible": False, "worm": True, "estimated_loss_usd": 10000000000},
        "propagation": ["EternalBlue", "Mimikatz-derived credentials", "PsExec"],
    },
    {
        "id": "rpt-004",
        "title": "Industroyer/CrashOverride: protocol-aware attacks on substations",
        "source": "NEXUS Lab",
        "date": "2017-09-20",
        "tlp": "AMBER",
        "confidence": "high",
        "actors": ["sandworm"],
        "campaigns": ["industroyer"],
        "malware": ["industroyer-mal"],
        "body": (
            "Industroyer (CrashOverride) spoke IEC 104, IEC 61850, and OPC in order to issue legitimate-looking "
            "breaker commands. The 2016 Kyiv outage was shorter than the 2015 BlackEnergy event but more automated. "
            "Sandworm remains the consistent attribution. Unlike WannaCry, this family is not wormable ransomware; "
            "it is purpose-built for electric operations. Analysts querying 'who else sabotages critical infrastructure' "
            "should traverse from Sandworm to NotPetya rather than to FIN7, whose victims are hospitality and payment "
            "systems. Shared GRU affiliation with APT28 does not mean shared ICS tooling."
        ),
        "ics_protocols": ["IEC-104", "IEC-61850", "OPC"],
        "outage_minutes": 75,
    },
    {
        "id": "rpt-005",
        "title": "WannaCry worm path, kill-switch domain, and Lazarus financial tasking",
        "source": "NEXUS Lab",
        "date": "2017-05-28",
        "tlp": "GREEN",
        "confidence": "high",
        "actors": ["lazarus"],
        "campaigns": ["wannacry"],
        "malware": ["wannacry-ransom"],
        "iocs": ["iuqerfsodp9ifjaposdfjhgosurijfaewrwergwea.com", "aa11bb22cc33dd44ee55ff6677889900"],
        "body": (
            "WannaCry combined an SMBv1 worm with a ransomware payload. A sinkholed kill-switch domain, "
            "iuqerfsodp9ifjaposdfjhgosurijfaewrwergwea.com, halted many infections once registered. Code overlap "
            "and operational links support Lazarus Group attribution. Healthcare providers with unpatched Windows "
            "estates, including the UK National Health Service, were hit disproportionately. Lazarus simultaneously "
            "runs classic espionage and theft: the Bangladesh Bank SWIFT heist and later fake cryptocurrency apps "
            "(AppleJeus) sit on the same actor node even though the malware families differ. Shared tooling with "
            "other clusters appears mainly through Cobalt Strike, not through EternalBlue worms."
        ),
        "cve": ["CVE-2017-0144"],
        "wormable": True,
        "kill_switch": "iuqerfsodp9ifjaposdfjhgosurijfaewrwergwea.com",
    },
    {
        "id": "rpt-006",
        "title": "SWIFT message fraud at Bangladesh Bank",
        "source": "NEXUS Lab",
        "date": "2016-04-02",
        "tlp": "AMBER",
        "confidence": "medium",
        "actors": ["lazarus"],
        "campaigns": ["swift-bangladesh"],
        "body": (
            "Operators with access to Bangladesh Bank's SWIFT environment submitted fraudulent transfer messages "
            "targeting the New York Federal Reserve account. Most of the attempted one-billion-dollar theft was "
            "blocked; a portion routed through casinos in Southeast Asia was recovered only in part. Valid accounts "
            "inside the messaging environment mattered more than novel exploits. Lazarus financial tasking connects "
            "this campaign to later cryptocurrency-exchange theft and to AppleJeus-style trojans. It does not share "
            "infrastructure with APT28's diplomatic spearphish cluster."
        ),
        "attempted_usd": 951000000,
        "recovered_usd": 65000000,
        "channel": "SWIFT MT103/MT202",
    },
    {
        "id": "rpt-007",
        "title": "FIN7 POS scraping and the Beacon pivot into English-speaking crews",
        "source": "NEXUS Lab",
        "date": "2018-11-03",
        "tlp": "AMBER",
        "confidence": "high",
        "actors": ["fin7", "scattered-spider"],
        "campaigns": ["carb-pos"],
        "malware": ["carbanak", "griffon", "cobalt-strike", "mimikatz"],
        "iocs": ["pay-relay-int.com", "microsoft-update-check.net"],
        "body": (
            "FIN7's hospitality campaigns used spearphish documents to drop GRIFFON, then Carbanak for long-haul "
            "access, then memory scrapers on POS. Card data left via pay-relay-int.com. In later years the same "
            "operators and copycats standardized on Cobalt Strike Beacon. Scattered Spider, an English-speaking "
            "crew, independently adopted Beacon plus help-desk social engineering and valid-account abuse. The "
            "graph therefore shows FIN7 and Scattered Spider sharing malware (Cobalt Strike, Mimikatz) and, in this "
            "lab corpus, overlapping C2 style on microsoft-update-check.net with APT41. Shared tooling is not shared "
            "attribution — a distinction SQL star-schemas routinely flatten away."
        ),
        "payment_brands": ["Visa", "Mastercard"],
        "lure_themes": ["reservation confirmation", "labor schedule"],
        "beacon_watermark": "CS-LAB-FIN7-0041",
    },
    {
        "id": "rpt-008",
        "title": "APT41 dual mission: Winnti/ShadowPad and moonlighting crime",
        "source": "NEXUS Lab",
        "date": "2020-03-15",
        "tlp": "AMBER",
        "confidence": "high",
        "actors": ["apt41"],
        "malware": ["shadowpad", "cobalt-strike"],
        "iocs": ["45.77.12.90", "microsoft-update-check.net"],
        "body": (
            "APT41 (Winnti, Barium) runs state-aligned espionage in parallel with financially motivated intrusions. "
            "ShadowPad, a modular successor in the Winnti lineage, is the espionage workhorse. Cobalt Strike appears "
            "in the crime-adjacent side and creates a two-hop path to FIN7 and Scattered Spider. Infrastructure "
            "microsoft-update-check.net is a Beacon stager domain in this dataset, also used by Scattered Spider. "
            "Supply-chain preference later overlaps thematically with the 3CX event, which this corpus attributes "
            "primarily to Lazarus with APT41 as a secondary interested party on adjacent tooling — a deliberately "
            "messy real-world graph, not a clean tree."
        ),
        "missions": ["espionage", "financial"],
        "sectors": ["telecom", "video-game", "healthcare"],
    },
    {
        "id": "rpt-009",
        "title": "3CXDesktopApp supply chain and Lazarus crypto-targeting",
        "source": "NEXUS Lab",
        "date": "2023-04-01",
        "tlp": "GREEN",
        "confidence": "medium",
        "actors": ["lazarus", "apt41"],
        "campaigns": ["3cx"],
        "malware": ["applejeus", "cobalt-strike"],
        "iocs": ["trade-helper-app.com"],
        "body": (
            "Trojanized 3CXDesktopApp builds were used as a supply-chain beachhead. Follow-on selection favored "
            "cryptocurrency and trading-adjacent firms, consistent with Lazarus theft tasking and with AppleJeus "
            "watering holes such as trade-helper-app.com. Cobalt Strike showed up in a subset of post-exploitation "
            "activity, which is why a multi-hop query from 3CX reaches FIN7 even though FIN7 did not run the 3CX "
            "campaign. APT41 is linked here through shared Beacon infrastructure patterns, not through the 3CX "
            "build system itself. Vector search over 'supply chain signed software update' also retrieves SolarWinds "
            "and NotPetya/MeDoc, which is the point of a vector index: similar narrative, different actors."
        ),
        "package": {"name": "3CXDesktopApp", "platforms": ["Windows", "macOS"]},
        "yara_rule_name": "NEXUS_AppleJeus_trade_helper",
    },
    {
        "id": "rpt-010",
        "title": "Mimikatz as a commodity: credential dumping across rival clusters",
        "source": "NEXUS Lab",
        "date": "2019-08-19",
        "tlp": "WHITE",
        "confidence": "high",
        "actors": ["apt28", "apt29", "fin7", "scattered-spider", "kimsuky"],
        "malware": ["mimikatz"],
        "body": (
            "Mimikatz implements OS credential dumping (T1003) and is used by nation-state and criminal clusters "
            "alike. In this knowledge graph APT28, APT29, FIN7, Scattered Spider, and Kimsuky all have a USES edge "
            "to Mimikatz. That makes Mimikatz a poor sole-attribution feature and a good illustration of why "
            "multi-hop context is required. Pair credential dumping with victim sector and C2 graph: diplomatic "
            "spearphish plus X-Agent suggests APT28; help-desk vishing plus Beacon suggests Scattered Spider; "
            "POS scraping plus GRIFFON suggests FIN7. Key-value caches of fresh Mimikatz hashes go stale quickly, "
            "which is why the blocklist store uses TTL rather than a permanent relational row."
        ),
        "technique_primary": "T1003",
        "commodity": True,
        "notes_extra": "Do not treat Mimikatz presence as actor uniqueness.",
    },
    {
        "id": "rpt-011",
        "title": "Kimsuky spearphish lures against foreign-policy researchers",
        "source": "NEXUS Lab",
        "date": "2022-07-09",
        "tlp": "AMBER",
        "confidence": "medium",
        "actors": ["kimsuky"],
        "malware": ["mimikatz"],
        "iocs": ["mail-login-secure.gov-service.net"],
        "body": (
            "Kimsuky continues to phish think-tank and diplomatic targets with government-themed login pages such as "
            "mail-login-secure.gov-service.net. Tooling is less unique than Lazarus destructive or theft malware; "
            "credential harvesting and Mimikatz follow-up are typical. North Korean tasking overlaps thematically "
            "with Lazarus (same sponsor org in this model) but campaigns and malware families diverge. A graph query "
            "from Kimsuky to Lazarus is organizational, not infrastructural — they do not share the WannaCry "
            "kill-switch domain or AppleJeus watering holes in this dataset."
        ),
        "lure_language": ["English", "Korean"],
        "target_roles": ["korea desk", "nuclear policy"],
    },
    {
        "id": "rpt-012",
        "title": "Help-desk vishing, identity provider takeover, and Scattered Spider",
        "source": "NEXUS Lab",
        "date": "2023-09-18",
        "tlp": "AMBER",
        "confidence": "high",
        "actors": ["scattered-spider"],
        "malware": ["cobalt-strike", "mimikatz"],
        "iocs": ["microsoft-update-check.net", "b7c3e1a90f44d21c99aa.onion"],
        "body": (
            "Scattered Spider (UNC3944) social-engineers IT help desks to reset MFA and seize valid accounts (T1078), "
            "then deploys Cobalt Strike. Ransomware affiliates sometimes appear downstream; this corpus keeps a leak "
            "site indicator b7c3e1a90f44d21c99aa.onion with a very short TTL because leak-site hostnames churn. "
            "Beacon C2 microsoft-update-check.net is shared with APT41 in the lab graph, a caution against naive "
            "IP/domain attribution. Compared with FIN7, the initial access is vishing rather than reservation-themed "
            "spearphish, but post-exploitation tooling converges."
        ),
        "initial_access": "vishing",
        "idp": ["Okta", "Azure AD"],
        "short_ttl_reason": "ransom leak sites rotate",
    },
]

DEMO_QUERIES = [
    "Which threat actors share command-and-control infrastructure, and what malware was hosted there?",
    "How is APT29 connected to supply-chain compromises, and which reports describe SUNBURST?",
    "Who else uses Cobalt Strike besides FIN7, and do they share any domains?",
    "What destructive campaigns is Sandworm responsible for, and does it share any infrastructure with APT28?",
    "Find activity similar to spearphishing against government and political organizations.",
    "Why is Mimikatz a weak attribution signal, and which actors still use it?",
]

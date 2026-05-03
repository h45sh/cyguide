# 01: Data & The Evidence Board

In CyGuide, we don't just "print text" to the screen. We create **Objects**.

## 1. What is a "Finding"?
A **Finding** is a structured piece of information. Think of it like a Python dictionary, but with strict rules.

If `nmap` finds an open port, it doesn't just say "Port 80 is open." It creates a `NetworkService` finding. 

### Example from the code (`cyguide/schemas/network.py`):
```python
# This is how we define what a "Service" looks like
class NetworkService(BaseFinding):
    schema_type: str = "network.service"
    # The PIK (Primary Identity Key) - What makes this unique?
    # For a service, it's the IP + Port + Protocol
    pik = {"host_ip": "127.0.0.1", "port": 80, "protocol": "tcp"}
```

---

## 2. What is a PIK (Primary Identity Key)?
This is the most important concept in our data design. 

**The Problem**: If `nmap` runs twice, it will report "Port 80 is open" twice. We don't want two icons on our screen for the same port.
**The Solution**: The **PIK**. Before adding a finding to the database, the engine checks: *"Do I already have a 'network.service' with this IP, Port, and Protocol?"*
*   If **Yes**: It updates the existing one (this is called an **Upsert**).
*   If **No**: It creates a new one.

---

### 3. The Entity Graph (The Evidence Board)
Findings aren't just floating in space. They are connected.

*   **Parent Relationship**: A `network.service` (Port 80) always has a **Parent** `network.host` (the computer).
*   **Netblock Ownership**: We moved the `organization` field from the Host to a `network.netblock`.
    *   **The Intent**: Hosts are transient (DHCP can change an IP), but a Netblock is an ownership boundary. By tracking organization at the netblock level, we ensure that if a company name changes, we update one record instead of 1,000.

**How it looks in the database**:
We have a table for **Nodes** (the findings) and a table for **Edges** (the connections). This allows the UI to show you a tree:
```
[Netblock: 192.168.1.0/24 (Org: Home)]
  └── [Host: 192.168.1.5]
        └── [Service: Port 80]
              └── [Endpoint: /admin]
```


---

## 4. Canonicalization (Cleaning the Data)
Different tools speak different "dialects."
*   Tool A says: `Staging.Example.Com`
*   Tool B says: `staging.example.com`

If we didn't clean this, the PIK would think they are different!
Our **Canonicalization** layer (`cyguide/engine/canonicalize.py`) automatically makes them all lowercase so they match perfectly.

---

### Next Step:
Learn how tools are plugged in! **[02: The Detective's Kit (Plugins & Tools)](02_plugins_and_tools.md)**

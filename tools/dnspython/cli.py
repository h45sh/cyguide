"""CLI entrypoint for CyGuide pure-Python DNS probe."""

import argparse
import json
import sys
import time
from typing import Any, Dict, List, Optional

try:
    import dns.exception
    import dns.query
    import dns.resolver
    import dns.reversename
    import dns.zone
except ImportError:
    dns = None


def resolve_records(
    target: str,
    record_type: str = "A",
    nameserver: Optional[str] = None,
    timeout: float = 5.0,
) -> List[Dict[str, Any]]:
    """Resolve DNS records for target using dnspython."""
    if dns is None:
        raise RuntimeError("dnspython library is not installed.")

    record_type = record_type.upper().strip()
    resolver = dns.resolver.Resolver()
    resolver.lifetime = timeout
    resolver.timeout = timeout

    if nameserver:
        resolver.nameservers = [nameserver]

    results: List[Dict[str, Any]] = []

    # 1. Zone Transfer (AXFR)
    if record_type == "AXFR":
        ns_servers = [nameserver] if nameserver else []
        if not ns_servers:
            # Discover authoritative nameservers first
            try:
                ns_answers = resolver.resolve(target, "NS")
                ns_servers = [str(r.target).rstrip(".") for r in ns_answers]
            except Exception as e:
                return [
                    {
                        "name": target,
                        "type": "AXFR",
                        "error": f"Failed to discover NS for AXFR: {e}",
                    }
                ]

        for ns in ns_servers:
            try:
                zone = dns.zone.from_xfr(dns.query.xfr(ns, target, timeout=timeout))
                for name, node in zone.nodes.items():
                    rname = str(name)
                    full_name = f"{rname}.{target}" if rname != "@" else target
                    for rdataset in node.rdatasets:
                        rtype = dns.rdatatype.to_text(rdataset.rdtype)
                        for rdata in rdataset:
                            results.append(
                                {
                                    "name": full_name,
                                    "type": rtype,
                                    "ttl": rdataset.ttl,
                                    "value": str(rdata),
                                    "server": ns,
                                }
                            )
                return results
            except Exception as e:
                results.append(
                    {
                        "name": target,
                        "type": "AXFR",
                        "error": f"AXFR failed on {ns}: {type(e).__name__} ({e})",
                        "server": ns,
                    }
                )
        return results

    # 2. Reverse DNS Lookup (PTR)
    if record_type == "PTR":
        try:
            rev_name = dns.reversename.from_address(target)
            answers = resolver.resolve(rev_name, "PTR")
            for rdata in answers:
                results.append(
                    {
                        "name": target,
                        "type": "PTR",
                        "ttl": answers.ttl,
                        "value": str(rdata.target).rstrip("."),
                        "server": resolver.nameservers[0] if resolver.nameservers else "system",
                    }
                )
        except Exception as e:
            results.append(
                {
                    "name": target,
                    "type": "PTR",
                    "error": f"PTR lookup failed: {type(e).__name__} ({e})",
                }
            )
        return results

    # 3. Standard Record Types (A, AAAA, MX, NS, TXT, SOA, CNAME, etc.)
    try:
        answers = resolver.resolve(target, record_type)
        for rdata in answers:
            val = str(rdata)
            if record_type == "TXT":
                val = "".join(
                    s.decode("utf-8", errors="replace") if isinstance(s, bytes) else str(s)
                    for s in rdata.strings
                )
            elif record_type == "MX":
                val = f"{rdata.preference} {str(rdata.exchange).rstrip('.')}"
            elif record_type in ("NS", "CNAME"):
                val = val.rstrip(".")

            results.append(
                {
                    "name": target,
                    "type": record_type,
                    "ttl": answers.ttl,
                    "value": val,
                    "server": resolver.nameservers[0] if resolver.nameservers else "system",
                }
            )
    except dns.resolver.NXDOMAIN:
        results.append(
            {"name": target, "type": record_type, "error": "NXDOMAIN (Non-Existent Domain)"}
        )
    except dns.resolver.NoAnswer:
        results.append(
            {"name": target, "type": record_type, "error": f"No {record_type} records found."}
        )
    except Exception as e:
        results.append({"name": target, "type": record_type, "error": f"{type(e).__name__}: {e}"})

    return results


def main(args: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="CyGuide Pure-Python DNS Probe")
    parser.add_argument("target", help="Domain name or IP address to probe")
    parser.add_argument(
        "-t", "--type", default="A", help="DNS Record Type (A, AAAA, MX, NS, TXT, SOA, PTR, AXFR)"
    )
    parser.add_argument(
        "-s", "--server", default=None, help="Nameserver IP to query (e.g., 8.8.8.8, 1.1.1.1)"
    )
    parser.add_argument("--timeout", type=float, default=5.0, help="Query timeout in seconds")
    parser.add_argument("--json", action="store_true", help="Output records in JSON format")

    parsed = parser.parse_args(args)

    start_time = time.time()
    try:
        records = resolve_records(
            target=parsed.target,
            record_type=parsed.type,
            nameserver=parsed.server,
            timeout=parsed.timeout,
        )
    except Exception as e:
        if parsed.json:
            print(json.dumps([{"target": parsed.target, "error": str(e)}], indent=2))
        else:
            print(f";; ERROR: {e}", file=sys.stderr)
        return 1

    elapsed_ms = int((time.time() - start_time) * 1000)

    if parsed.json:
        print(json.dumps(records, indent=2))
        return 0

    # Human-readable dig-style output
    server_str = parsed.server or "system-default"
    print(f"; <<>> CyGuide DNS Probe (dnspython) <<>> {parsed.target} {parsed.type.upper()}")
    print(f";; SERVER: {server_str}#53")
    print(f";; QUERY TIME: {elapsed_ms} msec")
    print(f";; WHEN: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print()
    print(";; ANSWER SECTION:")
    for r in records:
        if "error" in r:
            print(f";; WARNING: {r['name']} {r['type']} -> {r['error']}")
        else:
            print(f"{r['name']}.\t{r.get('ttl', 300)}\tIN\t{r['type']}\t{r['value']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

import geoip2.database, pyasn, json, sys

#python3 cutter.py country
print("Loading","match.json")
with open("match.json", 'r') as f:
    match = json.load(f)

print("Loading","GeoLite2-ASN")
reader = geoip2.database.Reader("../GeoLite2-ASN.mmdb")

export = {}

for ip in match:
    print("Resolving",ip)
    try:
        response = reader.asn(ip)
        if not response.autonomous_system_number in export: export[response.autonomous_system_number] = response.autonomous_system_organization
    except Exception as e:
        print("Skipping",ip)

with open("results.json", 'w') as f:
    json.dump(export, f, indent=1)

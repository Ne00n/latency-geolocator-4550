import geoip2.database, pyasn, json, sys

#python3 cutter.py country
print("Loading","pingable.json")
with open("../pingable.json", 'r') as f:
    pingable =  json.load(f)

print("Loading","GeoLite2")
reader = geoip2.database.Reader("../GeoLite2-Country.mmdb")
asndb = pyasn.pyasn('../asn.dat')

export = []
filter = []

for subnet,ips in pingable.items():
    print("Resolving",subnet)
    lookup = asndb.lookup(ips[0])
    print("ASN",lookup[0])
    if lookup[0] in filter: continue
    filter.append(lookup[0])
    try:
        response = reader.country(ips[0])
        if response.country.iso_code ==  sys.argv[1]: export.append(ips[0])
        print("Adding",ips[0])
    except Exception as e:
        print("Skipping",subnet)

with open("targets.json", 'w') as f:
    json.dump(export, f)

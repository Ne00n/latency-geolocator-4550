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

print("Running")
for subnet,data in pingable.items():
    for slicedSubnet in data:
        for ip in data[slicedSubnet]:
            if slicedSubnet in filter: continue
            lookup = asndb.lookup(ip)
            try:
                response = reader.country(ip)
                if response.country.iso_code ==  sys.argv[1]: 
                    print("Adding",ip)
                    export.append(ip)
                filter.append(slicedSubnet)
                break
            except Exception as e:
                break

with open("targets.json", 'w') as f:
    json.dump(export, f)

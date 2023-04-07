from tqdm.contrib.concurrent import process_map
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

def classify(data):
    global reader
    ips = []
    for slicedSubnet in data:
        for ip in data[slicedSubnet]:
            #lookup = asndb.lookup(ip)
            try:
                response = reader.country(ip)
                if response.country.iso_code ==  sys.argv[1]:  ips.append(ip)
            except Exception as e:
                pass
            finally:
                break
    return ips

print("Preparing")
sliced = []
for subnet,data in pingable.items(): sliced.append(data)
del pingable
print("Running")
results = process_map(classify, sliced, max_workers=2,chunksize=10)
print("Saving")
for row in results:
    for ip in row:
        export.append(ip)

with open("targets.json", 'w') as f:
    json.dump(export, f)

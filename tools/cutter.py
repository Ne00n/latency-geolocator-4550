from tqdm.contrib.concurrent import process_map
import geoip2.database, ipaddress, pyasn, json, sys
from netaddr import IPNetwork, IPAddress

#python3 cutter.py country
print("Loading","pingable.json")
with open("../pingable.json", 'r') as f:
    pingable =  json.load(f)

print("Loading","country.json")
country = open('country.json', 'r')
lines = country.readlines()

ip_ranges = []
countries = []

print("Preparing","country.json")
for line in lines:
    jsonData =  json.loads(line)
    if ":" in jsonData['start_ip']: continue
    ip_ranges.append([jsonData['start_ip'], jsonData['end_ip']])
    countries.append(jsonData['country'])

print("Loading","GeoLite2")
reader = geoip2.database.Reader("../GeoLite2-Country.mmdb")
asndb = pyasn.pyasn('../asn.dat')

export = []
filter = []

def classify(data):
    global reader, sorted_ips, countries
    ips = []
    for slicedSubnet in data:
        #print(slicedSubnet)
        for ip in data[slicedSubnet]:
            #maxmind
            try:
                response = reader.country(ip)
                if response.country.iso_code ==  sys.argv[1]: 
                    ips.append(ip)
                    break
            except Exception as e:
                pass
            #ipinfo
            country = is_ip_in_ranges_fast(ip, sorted_ips, countries)
            if country is not None and country == sys.argv[1]:
                ips.append(ip)
                break
    return ips

def create_sorted_ips(ip_ranges):
    sorted_ips = []
    for ip_range in ip_ranges:
        try:
            start_ip = int(ipaddress.IPv4Address(ip_range[0]))
            end_ip = int(ipaddress.IPv4Address(ip_range[1]))
            sorted_ips.append((start_ip, end_ip))
        except ValueError:
            print(f"Invalid IP range: {ip_range}")
            continue
    return sorted(sorted_ips, key=lambda x: x[0])

def binary_search(ip, sorted_ips):
    left, right = 0, len(sorted_ips)
    while left < right:
        mid = (left + right) // 2
        if sorted_ips[mid][0] <= ip <= sorted_ips[mid][1]:
            return mid
        if sorted_ips[mid][1] < ip:
            left = mid + 1
        else:
            right = mid
    return None

def is_ip_in_ranges_fast(ip, sorted_ips, countries):
    try:
        ip = int(ipaddress.IPv4Address(ip))
    except ValueError:
        print(f"Invalid IP address: {ip}")
        return None

    index = binary_search(ip, sorted_ips)
    if index is not None:
        return countries[index]
    else:
        return None

print("Preparing")
sorted_ips = create_sorted_ips(ip_ranges)
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

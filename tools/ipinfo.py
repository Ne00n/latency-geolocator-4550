import netaddr, json

country = open('country.json', 'r')
lines = country.readlines()

db = {}
for line in lines:
    jsonData =  json.loads(line)
    if ":" in jsonData['start_ip']: continue
    cidr = str(netaddr.iprange_to_cidrs(jsonData['start_ip'], jsonData['end_ip'])[0])
    print(cidr)
    splitted = cidr.split(".")
    if not splitted[0] in db: db[splitted[0]] = {}
    db[splitted[0]][cidr] = jsonData['country']

with open("ipinfo.json", 'w') as f:
    json.dump(db, f)
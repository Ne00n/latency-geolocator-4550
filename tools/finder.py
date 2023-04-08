import subprocess, json, sys, re

carriers = {9002:"RETN",3320:"DTAG",3257:"GTT",3356:"Lumen",2914:"NTT",3491:"PCCW",6453:"TATA",1299:"Telia"}

def mtr(target):
    mtr = ['mtr','--aslookup','--report','--report-cycles','5', target]
    return subprocess.run(mtr, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False).stdout.decode('utf-8')

def classify(mtr):
    carriersOnRoute = ""
    for line in mtr.split('\n'):
        asn = re.findall("AS([0-9]+)",line, re.MULTILINE)
        if asn and int(asn[0]) in carriers:
            carriersOnRoute += f"{carriers[int(asn[0])]} "
    return carriersOnRoute

min = float(sys.argv[1])
max = float(sys.argv[2])
print(f"Latency: {min}/{max}")

with open("targets.json", 'r') as f:
    targets =  json.load(f)

count = 0
match = {}
while True:
    if count > len(targets): break
    fping = ["fping", "-c", "5"]
    for target in targets[count:count+50]: fping.append(target)
    print(f"Running {count}/{len(targets)}")
    p = subprocess.run(fping, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    parsed = re.findall("([0-9.]+).*?([0-9]+.[0-9]|timed out).*?([0-9]+)% loss",p.stdout.decode('utf-8'), re.MULTILINE)
    for ip,ms,loss in parsed:
        if "timed out" in ms: continue
        if float(ms) > min and float(ms) < max and ip not in match: 
            print(f"Found {ip}")
            match[ip] = {"mtr":""}
            print(f"Running MTR for {ip}")
            response = mtr(ip)
            match[ip]['mtr'] = classify(response)
    count = count + 50
    with open("match.json", 'w') as f:
        json.dump(match, f, indent=4)

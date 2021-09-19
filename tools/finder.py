import subprocess, json, re

with open("targets.json", 'r') as f:
    targets =  json.load(f)


count = 0
match = []
while True:
    if count > len(targets): break
    fping = ["fping", "-c", "5"]
    for target in targets[count:count+50]:
        fping.append(target)
    print("running",fping)
    p = subprocess.run(fping, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    parsed = re.findall("([0-9.]+).*?([0-9]+.[0-9]).*?([0-9])% loss",p.stdout.decode('utf-8'), re.MULTILINE)
    for ip,ms,loss in parsed:
        if float(ms) < 130 and ip not in match: match.append(ip)
    count = count + 50
    with open("match.json", 'w') as f:
        json.dump(match, f)

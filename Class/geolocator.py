import subprocess, pyasn, time, json, re, os
from multiprocessing import Process
from datetime import datetime

class Geolocator:

    masscanDir,asndb = "",""

    def __init__(self,masscanDir="/masscan/"):
        print("Loading asn.dat")
        self.asndb = pyasn.pyasn(os.getcwd()+'/asn.dat')
        self.masscanDir = os.getcwd()+masscanDir

    def cmd(self,cmd):
        p = subprocess.run(cmd, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        return [p.stdout.decode('utf-8'),p.stderr.decode('utf-8')]

    def masscan(self):
        print("Generating json")
        files = os.listdir(self.masscanDir)
        list = {}
        for file in files:
            if ".json" in file:
                print("Loading",file)
                with open(self.masscanDir+file, 'r') as f:
                    dump = f.read()
                print("Modifying",file)
                dump = re.sub(r'\[\s,', '[', dump)
                dump = dump+"]"
                with open(self.masscanDir+"tmp"+file, 'a') as out:
                    out.write(dump)
                dump = ""
                print("Parsing",file)
                with open(self.masscanDir+"tmp"+file, 'r') as f:
                    dumpJson = json.load(f)
                os.remove(self.masscanDir+"tmp"+file)
                for line in dumpJson:
                    if line['ports'][0]['status'] != "open": continue
                    lookup = self.asndb.lookup(line['ip'])
                    if lookup[1] not in list:
                        list[lookup[1]] = []
                        list[lookup[1]].append(line['ip'])
                    else:
                        if len(list[lookup[1]]) < 50: list[lookup[1]].append(line['ip'])
                dumpJson = ""
        print("Saving","pingable.json")
        with open(os.getcwd()+'/pingable.json', 'w') as f:
            json.dump(list, f)

    def getIPs(self,pingable,row,length=1000):
        list,current,count = [],0,0
        for subnet,ips in pingable.items():
            current += 1
            if current >= row:
                list.append(ips[0])
                count += 1
            if count == length: return list
        return list

    def getAvrg(self,result):
        latency = {}
        parsed = re.findall("([0-9.]+).*?:.*?([0-9+])%(.*?\/([0-9.]+))?",result, re.MULTILINE)
        for row in parsed:
            if row[3] != "":
                latency[row[0]] = row[3]
            else:
                latency[row[0]] = "retry"
        return latency

    def mapToSubnet(self,latency):
        subnet = {}
        for ip, ms in latency.items():
            lookup = self.asndb.lookup(ip)
            subnet[lookup[1]] = ms
        return subnet

    def fpingLocation(self,pingable,location):
        row = 0
        while row < len(pingable):
            ips = self.getIPs(pingable,row)
            current = int(datetime.now().timestamp())
            print(location['name'],"Running fping")
            cmd = "ssh root@"+location['ip']+" fping -c2 "
            cmd += " ".join(ips)
            result = self.cmd(cmd)
            latency = self.getAvrg(result[1])
            subnets = self.mapToSubnet(latency)
            print(location['name'],"Updating",location['name']+"-subnets.json")
            if os.path.exists(os.getcwd()+'/data/'+location['name']+"-subnets.json"):
                with open(os.getcwd()+'/data/'+location['name']+"-subnets.json", 'r') as f:
                    subnetsOld = json.load(f)
                subnets = {**subnets, **subnetsOld}
            with open(os.getcwd()+'/data/'+location['name']+"-subnets.json", 'w') as f:
                json.dump(subnets, f)
            row += 1000
            currentLoop = int(datetime.now().timestamp())
            print(location['name'],"Done",row,"of",len(pingable))
            diff = currentLoop - current
            print(location['name'],"Finished in approximately",round(diff * ( (len(pingable) - row) / 1000) / 60),"minutes")

    def geolocate(self):
        print("Geolocate")
        print("Loading locations.json")
        with open(os.getcwd()+"/locations.json", 'r') as f:
            locations = json.load(f)
        print("Loading pingable.json")
        with open(os.getcwd()+"/pingable.json", 'r') as f:
            pingable = json.load(f)
        print("Got",str(len(pingable)),"subnets")

        for location in locations:
            if os.path.exists(os.getcwd()+'/data/'+location['name']+"-subnets.json"):
                os.remove((os.getcwd()+'/data/'+location['name']+"-subnets.json"))

        for location in locations:
            p = Process(target=self.fpingLocation, args=([pingable,location]))
            p.start()

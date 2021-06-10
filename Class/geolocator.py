import subprocess, random, pyasn, time, json, sys, re, os
from multiprocessing import Process
from datetime import datetime
from shutil import copyfile

class Geolocator:

    masscanDir,locations,pingable,asndb,notPingable = "","","","",""

    def __init__(self,masscanDir="/masscan/"):
        print("Loading asn.dat")
        self.asndb = pyasn.pyasn(os.getcwd()+'/asn.dat')
        self.masscanDir = os.getcwd()+masscanDir
        print("Loading locations.json")
        with open(os.getcwd()+"/locations.json", 'r') as f:
            self.locations = json.load(f)

    def loadPingable(self):
        print("Loading pingable.json")
        with open(os.getcwd()+"/pingable.json", 'r') as f:
            self.pingable = json.load(f)

    def cmd(self,cmd):
        p = subprocess.run(cmd, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        return [p.stdout.decode('utf-8'),p.stderr.decode('utf-8')]

    def debug(self,ip):
        lookup = self.asndb.lookup(ip)
        print("Subnet",lookup[1])
        subnets = {}
        for location in self.locations:
            print("Loading",location['name']+"-subnets.json")
            with open(os.getcwd()+'/data/'+location['name']+"-subnets.json", 'r') as f:
                subnets[location['name']] = json.load(f)
            if lookup[1] in subnets[location['name']]:
                print("Latency",subnets[location['name']][lookup[1]],"ms")
            else:
                print("Not found in",location['name'])

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

    def getIPs(self,row,length=1000):
        list,current,count = [],0,0
        for subnet,ips in self.pingable.items():
            current += 1
            if current >= row:
                list.append(ips[0])
                count += 1
            if count == length: return list
        return list

    def SliceAndDice(self,notPingable,row):
        if row + 1000 > len(notPingable):
            maximale = len(notPingable)
        else:
            maximale = row + 1000
        return notPingable[row:maximale]

    def SubnetsToRandomIP(self,list):
        ips = []
        for subnet in list:
            if subnet in self.pingable:
                ips.append(random.choice(self.pingable[subnet]))
        return ips

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

    def fpingLocation(self,location,update=False):
        row = 0
        length = len(self.pingable)
        if update: length = len(self.notPingable)
        while row < length:
            if update is False: ips = self.getIPs(row)
            if update is True: ips = self.SliceAndDice(self.notPingable,row)
            current = int(datetime.now().timestamp())
            cmd = "ssh root@"+location['ip']+" fping -c2 "
            cmd += " ".join(ips)
            result = self.cmd(cmd)
            latency = self.getAvrg(result[1])
            subnets = self.mapToSubnet(latency)
            if update is False:
                print(location['name'],"Updating",location['name']+"-subnets.csv")
                csv = ""
                for line in subnets.items():
                    csv += line[0]+","+line[1]+"\n"
                with open(os.getcwd()+'/data/'+location['name']+"-subnets.csv", "a") as f:
                    f.write(csv)
            else:
                print(location['name'],"Merging",location['name']+"-subnets.json")
                with open(os.getcwd()+'/data/'+location['name']+"-subnets.json", 'r') as f:
                    subnetsCurrent = json.load(f)
                #print(subnets)
                for line in subnets.items():
                    subnetsCurrent[line[0]] = line
                print(location['name'],"Saving",location['name']+"-subnets.json")
                with open(os.getcwd()+'/data/'+location['name']+"-subnets.json", 'w') as f:
                    json.dump(subnetsCurrent, f)
            row += 1000
            currentLoop = int(datetime.now().timestamp())
            print(location['name'],"Done",row,"of",length)
            diff = currentLoop - current
            print(location['name'],"Finished in approximately",round(diff * ( (length - row) / 1000) / 60),"minutes")
        print(location['name'],"Done")

    def geolocate(self):
        print("Geolocate")
        self.loadPingable()
        print("Got",str(len(self.pingable)),"subnets")

        run = {}
        for location in self.locations:
            if os.path.exists(os.getcwd()+'/data/'+location['name']+"-subnets.csv"):
                answer = input(location['name']+"-subnets.csv already exists. Do you want to rebuild? (y/n): ")
                if answer != "y": continue
                run[location['name']] = "y"
                print(location['name'],"backing up existing file")
                if os.path.exists(os.getcwd()+'/data/'+location['name']+"-subnets.csv.bak"):
                    answer = input(location['name']+"-subnets.csv.bak already exists. Override? (y/n): ")
                    if answer == "y":
                        copyfile(os.getcwd()+'/data/'+location['name']+"-subnets.csv", os.getcwd()+'/data/'+location['name']+"-subnets.csv.bak")
                else:
                    copyfile(os.getcwd()+'/data/'+location['name']+"-subnets.csv", os.getcwd()+'/data/'+location['name']+"-subnets.csv.bak")
                os.remove((os.getcwd()+'/data/'+location['name']+"-subnets.csv"))
            else:
                run[location['name']] = "y"

        for location in self.locations:
            if len(run) > 0 and location['name'] in run:
                p = Process(target=self.fpingLocation, args=([location]))
                p.start()

    def generate(self):
        print("Generate")
        print("Loading asn.dat")
        with open(os.getcwd()+'/asn.dat', 'r') as f:
            asn = f.read()
        subnets,routing = {},{}
        for location in self.locations:
            print("Loading",location['name']+"-subnets.json")
            with open(os.getcwd()+'/data/'+location['name']+"-subnets.json", 'r') as f:
                subnets[location['name']] = json.load(f)
        lines = asn.splitlines()
        for line in lines:
            data = line.split("\t")
            for location in self.locations:
                if data[0] in subnets[location['name']]:
                    if data[0] not in routing:
                        routing[data[0]] = {}
                        routing[data[0]]['latency'] = subnets[location['name']][data[0]]
                        routing[data[0]]['datacenter'] = location['name']
                    else:
                        if routing[data[0]]['latency'] == "retry" or subnets[location['name']][data[0]] == "retry":
                            print("Skipping",data[0])
                            continue
                        if float(routing[data[0]]['latency']) > float(subnets[location['name']][data[0]]):
                            routing[data[0]]['latency'] = subnets[location['name']][data[0]]
                            routing[data[0]]['datacenter'] = location['name']

                else:
                    print("Could not find",data[0],"in",location['name'])
        export = ""
        for row in routing.items():
            export += row[0]+" => "+row[1]['datacenter']+"\n"
        with open(os.getcwd()+'/data/dc.conf', 'w+') as out:
            out.write(export)

    def corrector(self):
        print("Corrector")
        notPingable = []
        for location in self.locations:
            print("Loading",location['name']+"-subnets.json")
            with open(os.getcwd()+'/data/'+location['name']+"-subnets.json", 'r') as f:
                tmp = json.load(f)
            for line in tmp.items():
                if line[1] == "retry":
                    notPingable.append(line[0])
        notPingable,tmp = list(set(notPingable)),""
        self.loadPingable()
        self.notPingable = self.SubnetsToRandomIP(notPingable)
        notPingable = ""
        for location in self.locations:
            p = Process(target=self.fpingLocation, args=([location,True]))
            p.start()

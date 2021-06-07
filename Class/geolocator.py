import subprocess, pyasn, time, json, re, os

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

    def geolocate(self):
        print("Geolocate")
        print("Loading locations.json")
        with open(os.getcwd()+"/locations.json", 'r') as f:
            locations = json.load(f)
        print("Loading pingable.json")
        with open(os.getcwd()+"/pingable.json", 'r') as f:
            pingable = json.load(f)
        print("Got",str(len(pingable)),"subnets")

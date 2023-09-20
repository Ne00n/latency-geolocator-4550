import subprocess, netaddr, json, re, os

class Base:

    @staticmethod
    def cmd(command):
        p = subprocess.run(command, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        return [p.stdout.decode('utf-8'),p.stderr.decode('utf-8')]

    @staticmethod
    def cmdInitial(command,timeout=10):
        try:
            run = f"{command[0]} {command[1]}"
            p = subprocess.run(run, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, timeout=timeout)
            return [command[1],p.stdout.decode('utf-8'),p.stderr.decode('utf-8')]
        except:
            return ["",""]

    @staticmethod
    def SliceAndDice(notPingable,row,length=1000):
        if row + 1000 > len(notPingable):
            maximale = len(notPingable)
        else:
            maximale = row + length
        return notPingable[row:maximale]

    @staticmethod
    def dictToCsv(dict):
        csv = ""
        for line in dict.items():
            csv += str(line[0])+","+str(line[1])+"\n"
        return csv

    @staticmethod
    def listToDict(list,index=1,data=2):
        dict = {}
        for row in list:
            dict[row[index]] = row[data]
        return dict

    @staticmethod
    def mapToSubnet(latency,mapping,subnets={},networks={}):
        for ip, ms in latency.items():
            lookup = mapping[ip]
            subnets[lookup] = ms
            networks[lookup] = ip
        return subnets,networks

    @staticmethod
    def getAvrg(results):
        latency = {}
        for row in results:
            parsed = re.findall("([0-9.]+).*?:.*?([0-9+])%(.*?\/([0-9.]+))?",row[1], re.MULTILINE)
            for line in parsed:
                if line[3] != "":
                    latency[line[0]] = line[3]
                else:
                    latency[line[0]] = "retry"
        return latency

    def networkToSubs(self,subnet):
        sub, prefix = subnet.split("/")
        if int(prefix) > 22: return [subnet]
        network = netaddr.IPNetwork(subnet)
        return [str(sn) for sn in network.subnet(23)]

    def saveJson(self,data,path):
        with open(path, 'w') as f:
            json.dump(data, f)

    def loadJson(self,path):
        with open(path, 'r') as f:
            return json.load(f)

    def startJoin(self,threads):
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    def loadNetworks(self):
        if os.path.exists(os.getcwd()+'/networks.json'):
            print("Loading networks.json")
            networks = self.loadJson(os.getcwd()+'/networks.json')
        else:
            networks = []
        return networks

    def getLocationMap(self):
        subnets = {}
        for location in self.locations:
            map = self.getLocationPart(location['name'])
            subnets[location['id']] = map
        return subnets

    def getLocationPart(self,fileName):
        subnets,map = {},{}
        path = os.getcwd()+f'/data/{fileName}-subnets.csv'
        if not os.path.isfile(path):
            print("Unable to load",path)
        else:
            print("Loading",path)
            with open(path, 'r') as f:
                file = f.read()
            for row in file.splitlines():
                line = row.split(",")
                map[line[0]] = line[1]
        return map

    @staticmethod
    def parseMTR(results):
        mtrs = []
        for result in results:
            mtrs.append([result[0],re.findall("([0-9]+)\.\|--\s([0-9.]+).+?\n",result[1], re.MULTILINE)])
        return mtrs

    @staticmethod
    def getLastIP(mtrs):
        lastIP,lastIPs = "",[]
        for mtr in mtrs:
            for line in mtr[1]:
                lastIP = line[1]
                if "???" in line[1]: break
            lastIPs.append([mtr[0],lastIP])
        return lastIPs

    @staticmethod
    def listToCsv(dataList):
        csv = ""
        for line in dataList:
            csv += str(line[0])+","+str(line[1])+"\n"
        return csv
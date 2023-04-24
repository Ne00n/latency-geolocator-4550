import subprocess, netaddr, json, re, os

class Base:

    @staticmethod
    def cmd(command):
        p = subprocess.run(command, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        return [p.stdout.decode('utf-8'),p.stderr.decode('utf-8')]

    def SliceAndDice(self,notPingable,row,length=1000):
        if row + 1000 > len(notPingable):
            maximale = len(notPingable)
        else:
            maximale = row + length
        return notPingable[row:maximale]

    def csvToDict(self,csv):
        dict = {}
        for row in csv.splitlines():
            line = row.split(",")
            dict[line[0]] = line[1]
        return dict

    def dictToCsv(self,dict):
        csv = ""
        for line in dict.items():
            csv += str(line[0])+","+str(line[1])+"\n"
        return csv

    def listToDict(self,list,index=0,data=1):
        dict = {}
        for row in list:
            dict[row[index]] = row[data]
        return dict

    def getAvrg(self,results):
        latency = {}
        for row in results:
            parsed = re.findall("([0-9.]+).*?:.*?([0-9+])%(.*?\/([0-9.]+))?",row[0], re.MULTILINE)
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

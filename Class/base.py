import subprocess, netaddr, json, re

class Base:

    def cmd(self,cmd):
        p = subprocess.run(cmd, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        return [p.stdout.decode('utf-8'),p.stderr.decode('utf-8')]

    def SliceAndDice(self,notPingable,row):
        if row + 1000 > len(notPingable):
            maximale = len(notPingable)
        else:
            maximale = row + 1000
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

    def getAvrg(self,result):
        latency = {}
        parsed = re.findall("([0-9.]+).*?:.*?([0-9+])%(.*?\/([0-9.]+))?",result, re.MULTILINE)
        for row in parsed:
            if row[3] != "":
                latency[row[0]] = row[3]
            else:
                latency[row[0]] = "retry"
        return latency

    def networkToSubs(self,subnet):
        network = netaddr.IPNetwork(subnet)
        return [str(sn) for sn in network.subnet(21)]

    def saveJson(self,json,path):
        with open(path, 'w') as f:
            json.dump(json, f)

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

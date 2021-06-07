from Class.geolocator import Geolocator
import sys

print("Geolocator 4550 Premium Edition")
masscanDir = "/masscan/"

geolocator = Geolocator(masscanDir)

if len(sys.argv) == 1:
    print("masscan, geolocate")
elif sys.argv[1] == "masscan":
    geolocator.masscan()
elif sys.argv[1] == "geolocate":
    geolocator.geolocate()

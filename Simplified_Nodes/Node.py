import json
import sys
import os
import time
import tkinter
Nodelist = []

class Params:
        paramlist = [[]]
        def __init__(self,selftypes,addparams):
            self.paramtypes = selftypes
            self.paramlist = addparams
            
class Node:
    

    index=0
    name = ""
    nickname = ""
    parameters = []
    def __init__(self,index,name):
        self.index = index
        self.name = name
    def Change_nickname(self, NewNick):
        self.nickname= NewNick
    def addParams(self, Paramtypes,params):
        self.parameters = Params(Paramtypes)


print("Filepath?\n")
#with open(input(">> "), 'r', encoding='utf-8') as file:
with open("takoHouse_ff63.logic.root.json", 'r', encoding='utf-8') as file:
    data = json.load(file)
try:
    data["Info"]
except KeyError:
    raise KeyError("That's not an ainb JSON, you bozo ◔̯◔ How about we try again but you give me the right file? :3")

def Change_nickname( original, NewNick):
        for node in Nodelist:
            if node.index == original:
                node.nickname = NewNick

for JsonNode in data["Nodes"]:
    CurrentNode = Node(JsonNode["Node Index"],JsonNode["Name"])
    paramtypes = []
    paramlist = []
    subparamlist = []
    for type in JsonNode["Internal Parameters"]:
        paramtypes.append(type)
        subparamlist = []
        for parameter in JsonNode["Internal Parameters"][type]:
            subparamlist.append[parameter]["name"]
            try:
                subparamlist.append[parameter]["value"]
            except KeyError:
                print()
            paramlist.append(subparamlist)
    CurrentNode.addParams()
    Nodelist.append( CurrentNode )
for Nodule in Nodelist:
    print((Nodule.nickname if Nodule.nickname != "" else Nodule.name) + " is the node at index " ,end="")
    print(Nodule.index)
    print()
def listcommands():
    print("commands")


while True:
    print("Name a command! (-h for help)")
    Input = input(">>")
    if Input == "-h":
        listcommands()
    elif Input =="Change Nickname":
        index = int(input("Original ID: "))
        print("Game file name is " + Nodelist[index].name)
        if Nodelist[index].nickname != "":
            print("Its current nickname is " + Nodelist[index].nickname)
        Change_nickname( index, input("New Nickname: "))
    time.sleep(0.02)

import json
import sys
import os
import time
import tkinter
Nodelist = []

class InternalParams:
        paramlist = [[]]
        paramtypes = []
        def __init__(self,selftypes,addparams):
            self.paramtypes = selftypes
            self.paramlist = addparams
        def ret(self):
            output = "Parameter Types : \n"
            subout=""
            i=0
            for paramtype in self.paramtypes:
                
                output += "    " + paramtype +"\n"
                for param in self.paramlist[i]:
                    subout += "    " +str(param)+"\n"
                subout+=","
                i+=1
            output += "Parameters : \n" + subout
            
            return(output)

class OutParams:
    paramlist = [[]]
    paramtypes = []
    def __init__(self,selftypes,addparams):
        self.paramtypes = selftypes
        self.paramlist = addparams
    def ret(self):
        output = "Parameter Types : \n"
        subout=""
        i=0
        for paramtype in self.paramtypes:
            
            output += "    " + paramtype +"\n"
            for param in self.paramlist[i]:
                subout += "    " +str(param)+"\n"
            subout+=","
            i+=1
        output += "Parameters : \n" + subout
        
        return(output)


class InParams:
    paramlist = [[]]
    paramtypes = []
    def __init__(self,selftypes,addparams,names):
        self.paramtypes = selftypes
        self.paramlist = addparams
        self.names = names
    def ret(self):
        output = "Parameter Types : \n"
        subout=""
        i=0
        for paramtype in self.paramtypes:
            
            output += "    " + paramtype +"\n"
            for param in self.paramlist[i]:
                subout += "    " +self.names[i] +": "+ str(param)+"\n"
                i+=1
            subout+=","
            
        output += "Parameters : \n" + subout
        
        return(output)

class LinkedNodes:
    paramtypes = []
    paramlist = []
    def __init__(self,selftypes,addparams):
        self.paramtypes = selftypes
        self.paramlist = addparams
    def ret(self):
        output = "Parameter Types : \n"
        subout=""
        i=0
        for paramtype in self.paramtypes:
            
            output += "    " + paramtype +"\n"
            for param in self.paramlist[i]:
                subout += "    " +str(param)+"\n"
            subout+=","
            i+=1
        output += "Parameters : \n" + subout
        
        return(output)

class Node:
    index=0
    name = ""
    nickname = ""
    parameters = []
    parameters = []
    def __init__(self,index,name):
        self.index = index
        self.name = name

    def Change_nickname(self, NewNick):

        self.nickname= NewNick
    def addParams(self, Paramtypes,params):
        self.parameters = InternalParams(Paramtypes,params)

    def addinParams(self, Paramtypes,params,names):
        self.iparameters = InParams(Paramtypes,params,names)
    def addLinks(self, Paramtypes,params):
            self.links = LinkedNodes(Paramtypes,params)

    def addoutParams(self, Paramtypes,params):
        self.oparameters = OutParams(Paramtypes,params)

    def printstuff(self,donext = False):
        print("Index: " + str(self.index))
        print("Name: " + self.nickname +"/"+ self.name)
        
        print("internal params")
        try:
            print(self.parameters.ret())
        except AttributeError:
            print("none")
    
        print("output params")
        try:
            print(self.oparameters.ret())
        except AttributeError:
            print("none")
        print("input params")
        try:
            print(self.iparameters.ret())
        except AttributeError:
            print("none")
        print("Linked Nodes")
        try:
            print(self.links.ret())
            if(donext):
                for link in self.links.paramlist:
                    print("next output{ ")
                    Nodelist[link[0]].printstuff()
                    print("} ")
            else:
                for link in self.links.paramlist:
                    print(link)

        except AttributeError:
            print("none")
       



print("Filepath?\n")
#with open(input(">> "), 'r', encoding='utf-8') as file:
with open("C:\\Users\\brend\\OneDrive\\Documents\\GitHub\\ainb\\takoHouse_ff63.logic.root.json", 'r', encoding='utf-8') as file:
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
    try:
        for type in JsonNode["Internal Parameters"]:
            print("")
            paramtypes.append(type)
            subparamlist = []
            for parameter in JsonNode["Internal Parameters"][type]:
                subparamlist.append(parameter["Name"])
                try:
                    subparamlist.append(parameter["Value"])
                except KeyError:
                    print()
                paramlist.append(subparamlist)
        CurrentNode.addParams(paramtypes,paramlist)
    except KeyError:
        print()


    paramtypes = []
    paramlist = []
    subparamlist = []
    try:
        for type in JsonNode["Output Parameters"]:
            print("")
            paramtypes.append(type)
            subparamlist = []
            for parameter in JsonNode["Output Parameters"][type]:
                subparamlist.append(parameter["Name"])
                try:
                    subparamlist.append(parameter["Class"])
                except KeyError:
                    print()
                paramlist.append(subparamlist)
        CurrentNode.addoutParams(paramtypes,paramlist)
    except KeyError:
        print()

    paramtypes = []
    paramlist = []
    subparamlist = []
    try:
        for type in JsonNode["Input Parameters"]:
            print("")
            paramtypes.append(type)
            subparamlist = []
            namelist = []
        for parameter in JsonNode["Input Parameters"][type]:
                for item in parameter:
                    subparamlist = []
                    namelist = []
                    subparamlist.append(parameter["Name"])
                    namelist.append("Name")
                    try:
                        subparamlist.append(parameter["Class"])
                        namelist.append("Class")
                    except KeyError:
                        print()

                    try:
                        subparamlist.append(parameter["Node Index"])
                        namelist.append("Node Index")
                    except KeyError:
                        print()

                    try:
                        subparamlist.append(parameter["Parameter Index"])
                        namelist.append("Parameter Index")
                    except KeyError:
                        print()

                    try:
                        subparamlist.append(parameter["Value"])
                        namelist.append("Value")
                    except KeyError:
                        print()

                    paramlist.append(subparamlist)
        CurrentNode.addinParams(paramtypes,paramlist,namelist)
        
    except KeyError:
        print()

    paramtypes = []
    paramlist = []
    subparamlist = []
    try:
        for type in JsonNode["Linked Nodes"]:
            print("")
            paramtypes.append(type)
            subparamlist = []
            for parameter in JsonNode["Linked Nodes"][type]:
                subparamlist.append(parameter["Node Index"])
                subparamlist.append(parameter["Parameter"])
                paramlist.append(subparamlist)
        CurrentNode.addLinks(paramtypes,paramlist)
    except KeyError:
        print()

    Nodelist.append( CurrentNode )
for Nodule in Nodelist:
    print((Nodule.nickname if Nodule.nickname != "" else Nodule.name) + " is the node at index " ,end="")
    print(Nodule.index)


def grabinfo(index):
    return(Nodelist[index].printstuff())
def graballinfo(index):
    return(Nodelist[index].printstuff(True))
for node in Nodelist:
    try:
        node.iparameters.paramlist == []
    except AttributeError:
        try:
            if(( node.oparameters.paramlist != [] )&( node.links.paramlist !=[])):
                print(node.name)
                print(node.index)
                print()
                print(node.oparameters.paramlist)
                print()
                print(node.links.paramlist)
                print("\n")
                startpoints.append(node.index)
        except AttributeError:
            print("",end="")


while True:
    print("Name a command! (-h for help)")
    Input = input(">>")
    if Input =="Change Nickname":
        index = int(input("Original ID: "))
        print("Game file name is " + Nodelist[index].name)
        if Nodelist[index].nickname != "":
            print("Its current nickname is " + Nodelist[index].nickname)
        Change_nickname( index, input("New Nickname: "))
    elif Input =="NodeI":
        index = int(input("root ID: "))
        print(Nodelist[index].printstuff())
    time.sleep(0.02)

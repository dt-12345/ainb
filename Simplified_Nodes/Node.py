import json
import sys
import os
import time
import tkinter
Nodelist = []
def clear_screen():
    # For Windows
    if os.name == 'nt':
        _ = os.system('cls')
    # For macOS and Linux
    else:
        _ = os.system('clear')

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
                
                output += "    " + str(paramtype) +"\n"
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
            
            output += "    " + str(paramtype) +"\n"
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
            
            output += "    " + str(paramtype) +"\n"
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
            print(paramtype)
            output += "    " + str(paramtype) +"\n"
            for param in self.paramlist[i]:
                subout += "    " +str(param)+"\n"
            subout+=","
            i+=1
        output += "Parameters : \n" + subout
        
        return(output)
    def GrabOutIndices(self):
        output = ""
        for i in range(len(self.paramtypes)):
            output += str(self.paramlist[i][0]) + ","
        return output
    def GrabOutTypes(self):
        output = ""
        for i in range(len(self.paramtypes) + 1):
            output += str(self.paramlist[i][1]) + "\n"
        return output

class Node:
    index=0
    guid = ""
    name = ""
    nickname = ""
    parameters = []
    parameters = []
    def getInternalParamTypes(self):
        return InternalParams.paramlist

    def __init__(self,index,name,guid):
        self.index = index
        self.name = name
        self.guid = guid
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
       


print("Filepath?")
filepath = input(">> ")
with open(filepath, 'r', encoding='utf-8') as file:
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
    CurrentNode = Node(JsonNode["Node Index"],JsonNode["Name"],JsonNode["GUID"])
    paramtypes = []
    paramlist = []
    subparamlist = []
    try:
        for Type in JsonNode["Internal Parameters"]:
            print("")
            paramtypes.append(Type)
            subparamlist = []
            for parameter in JsonNode["Internal Parameters"][Type]:
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
        for Type in JsonNode["Output Parameters"]:
            print("")
            paramtypes.append(Type)
            subparamlist = []
            for parameter in JsonNode["Output Parameters"][Type]:
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
        for Type in JsonNode["Input Parameters"]:
            print("")
            paramtypes.append(Type)
            subparamlist = []
            namelist = []
        for parameter in JsonNode["Input Parameters"][Type]:
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
        for Type in JsonNode["Linked Nodes"]:
            print("")
            paramtypes.append(type)
            subparamlist = []
            for parameter in JsonNode["Linked Nodes"][Type]:
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
    elif Input =="Nodes":
        clear_screen()
        while True:
            
            print("Enter next Index, or other option (-h)")
            tmp = input("Index: ")
            try:
                index = int(tmp)
                clear_screen()
                print("name : " + (Nodelist[index].nickname if Nodelist[index].nickname!="" else Nodelist[index].name))
                print("\nindex : " + str(Nodelist[index].index))
                print("\ngui : " + Nodelist[index].guid)
                try:
                    print("\nOutput Nodes : " + Nodelist[index].links.GrabOutIndices())
                except AttributeError:
                    pass
            except ValueError:
                if tmp == "stop":
                    break
                elif tmp == "-h":
                    print("""\ncommands for Node Viewer:
    -h : help (duh)
    stop : stop
    types : lets you view the output types of a specific node output
    True Name : Returns the name of the node, regardless of if it has a nickname.
                (the name from earlier prefers nicknames over names when possible)
    Nick : adds a node nickname
                          """)
                elif( type(index) !=int):
                    print("\ninvalid command bro")
                elif tmp == "True Name":
                    print("\nActual Name : " + Nodelist[index].name)
                elif tmp == "type":
                    print("\noutput types(same order as output indices) :\n" + Nodelist[index].links.GrabOutTypes())
                elif tmp =="Nick":
                    Change_nickname( index, input("New Nickname: "))

    elif Input =="Save":
        save()
                    

                    
            
        time.sleep(0.02)

from converter import json_to_ainb
from converter import ainb_to_json
import os
from pathlib import Path
import json
import tkinter

def convert(file):
    ##------------------------Converting and Reading Ainb Data------------------------##
                    # creating current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    print(current_dir)

    #save the file name
    filename = file

    #convert the ainb to a Json
    ainb_to_json( Path( str(current_dir) + "\\" + filename), str(current_dir))

    #Saving the path to the new Json
    JsonPath = current_dir + "\\" + filename[0:-4] + "json"
    filename = filename[0:-4]


    # Open the JSON file
    with open(JsonPath, encoding="utf8") as data:
        # Load the JSON data into a Python dictionary
        data = json.load(data)

##------------------------gui------------------------##

# Import Module
from tkinter import *

# create root window
root = Tk()

# root window title and dimension
root.title("Ainb Node Editor")
# Set geometry (widthxheight)
root.geometry('500x400')

# all widgets will be here
EnterPrompt = Label(root, text = "Enter name of the file to edit? (ex: \'LogicTest.root.ainb\') ::")
EnterPrompt.grid()

FileIn = Entry(root, width=10)
FileIn.grid(column =1, row =0)

    
def Enterclicked():
    convert(FileIn.get())
    EnterPrompt.pack_forget()

# button widget with red color text inside
btn = Button(root, text = "Click me" ,
             fg = "red", command=Enterclicked)
# Set Button Grid
btn.grid(column=2, row=0)

# Execute Tkinter
root.mainloop()
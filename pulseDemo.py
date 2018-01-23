# -*- coding: utf-8 -*-
"""
Created on Wed Jan 10 07:07:41 2018

@author: dgray

Prototype graphics for the LED bar

    * Designs
        * Slow/wide continuous colors moving top->down; fast narrow bright pulses going down->up (bubbles)
        * Color transition via two pulses at same rate but offset

"""

import graphics as gfx   #simple helpy graphics lib.  Not fast, but easy
#import matplotlib.pyplot as plt   #for prototype work in windows
import pulses


strip = []
def createStrip(win):
    """
    Init the strip    
    It is important to create all the objects once, 
    else we'll have a ton of extra objects that seriously slows down rendering
    """
    currPoint = startPoint    
    for i in range(ledArrayLen):
        rect = gfx.Rectangle(currPoint, gfx.Point(currPoint.getX() + ledSize, currPoint.getY() + ledSize)) 
        rect.draw(win)        
        strip.append(rect)
        currPoint = gfx.Point(currPoint.getX(), currPoint.getY()+ledSize)

def createDesign(ledLen):
    #this block is a set of wide pulses that travel together to create a background wash
    gs1 = pulses.GaussCtl(arrayLen=ledLen, startCtr=-80, width=50, rate=1.0, color=pulses.Color(255,0,128))
    gs2 = pulses.GaussCtl(arrayLen=ledLen, startCtr=0, width=50, rate=1.0, color=pulses.Color(128,128,0))
    gs3 = pulses.GaussCtl(arrayLen=ledLen, startCtr=80, width=50, rate=1.0, color=pulses.Color(0,128,128))
    gs4 = pulses.GaussCtl(arrayLen=ledLen, startCtr=160, width=50, rate=1.0, color=pulses.Color(100,128,158))
    
    # a couple smaller & faster pulses
    gs5 = pulses.GaussCtl(arrayLen=ledLen, startCtr=40, width=5, rate=4.0, color=pulses.Color(0,25,255))
    gs6 = pulses.GaussCtl(arrayLen=ledLen, startCtr=100, width=3, rate=-6.5, color=pulses.Color(120,255,255))
    gs6.border = 100 #bigger border keeps it off the display longer
    gsList = [gs1, gs2, gs3, gs4, gs5, gs6]
    return gsList


ledSize = 5    #size of rect to display
startPoint = gfx.Point(10, 10) #where to locate in window
ledArrayLen = 150    #number led's
pulseList = createDesign(ledArrayLen)

def main():    
    frameRate = 20
    print ("proto soothing display for LED strip")

    win = gfx.GraphWin("My Window", 25, 800)
    win.setBackground('black')
    createStrip(win)

    while True:
        list(map(lambda x:x.update(), pulseList))   #update them all
        #colorArrays = [pulses.makeGaussian(x) for x in pulseList] #build a ColorArray for each pulse
        colorArrays = [pulses.makeGaussianFast(x) for x in pulseList] #build a ColorArray for each pulse
        outArray = sum(colorArrays) #add them all together (clamping built in)
        byteArray = pulses.byteArray(outArray)
    
        #display the result
        for i in range(ledArrayLen):
            strip[i].setFill(gfx.color_rgb(*outArray[i]))  #clamp to 255 and fill it  ('*' unpacks the tuple)  

        gfx.update(frameRate) #control the frame rate
        if win.checkMouse() != None: break  #stop via mouse click

    win.close()
        

if __name__ == '__main__':
    main()



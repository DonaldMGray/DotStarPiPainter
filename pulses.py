# -*- coding: utf-8 -*-
"""
Created on Tue Jan 16 09:34:15 2018

@author: dgray

Library for creating 1-D pulses 
Generates array directly usable for display
Supports updating to shift the pulse across the display and will handle wrapping 

TODO
    * try a squared normal to be more visually striking

"""

#import math
import numpy as np
from scipy.stats import norm
from collections import namedtuple

ColorT = namedtuple('ColorT', ['r', 'g', 'b'])
class Color(ColorT):
    """
    supports adding two colors and clamping to [0-255]
    """
    def __new__(cls, *args):  #to be more complete, could look for **kwargs (named args)
        return ColorT.__new__(cls, *args)  #'*' unpacks the r,g,b passed in
    def clamp(self, x):        #ensure all values are within range
        return max(0, min(255, x))        
    def __add__(self, other):
        return Color(*([self.clamp(sum(x)) for x in zip(self, other)]))
        
class GaussCtl():
    """
    A class to hold control and current status (eg: location) of a Guassian shape
    Has notion of size of array to be rendered onto and can be updated to shift over time
    """
    def __init__(self, arrayLen, startCtr, width, rate, color):
        self.arrayLen = arrayLen
        self.startCtr = startCtr
        self.width = width
        self.rate = rate    #how much to shift the pulse per update 
        self.color = color  #Color class
        self.currCtr = startCtr
        self.border = width*3   #how far to let the center be from the display before restarting
    def update(self):
        self.currCtr = self.currCtr + self.rate
        #once it moves past the display, move it to the other side (offset by border)
        if self.currCtr > self.arrayLen + self.border:
            self.currCtr = -self.border
        if self.currCtr < 0 - self.border:
            self.currCtr = self.arrayLen + self.border


class ColorList(list):
    """
    Holds an array of colors 
    Overrides '+' behavior to combine arrays with clamping (rather than concatenation which is what list does)
    """
    # don't need to overwrite __new__ or __init__
        
    def __add__(self, other):  #Color will clamp to [0-]
        if type(other) == int: return self    #this is to support sum, which starts by adding to '0'
        newArray = ColorList( [self[x]+other[x] for x in range(len(self))] )
        return newArray
    def __radd__(self, other):
        if type(other) == int: return self    #this is to support sum, which starts by adding to '0'
        return other + self

def makeGaussianFast(gauss):	
#	pdf = np.exp(-np.power( np.array(range(100)) - 50, 2.) / (2 * np.power(5, 2.)))
	pdf = np.exp(-np.power( np.array(range(gauss.arrayLen)) - gauss.currCtr, 2.) / (2 * np.power(gauss.width, 2.)))
	#scale the color by the gaussian pulse and build into array of colors
	# if we wanted to handle 'tight' wrapping, we could see if the center was within 2 sigma of an edge
	# then calc the modulus for the center to get the tail to come in at the other side
	tmp = [Color(int(pdf[x]*gauss.color.r), int(pdf[x]*gauss.color.g), int(pdf[x]*gauss.color.b)) for x in range(gauss.arrayLen)]
	ledColorArray = ColorList(tmp)
	return ledColorArray
				

def makeGaussian(gauss):
    """
    Generate a ColorList given a GaussCtl
    """
    #fill array with normal distrib, offset as appropriate
    rv = norm(loc = gauss.currCtr, scale = gauss.width)
    x = range(0, gauss.arrayLen)
    maxPdf = rv.pdf(gauss.currCtr)  #use max value to normalize the height of the pdf
    pdf = [rv.pdf(xx)/maxPdf for xx in x]   #generate a pdf with normalized height 
    
    #scale the color by the gaussian pulse and build into array of colors
    # if we wanted to handle 'tight' wrapping, we could see if the center was within 2 sigma of an edge
    # then calc the modulus for the center to get the tail to come in at the other side
    tmp = [Color(int(pdf[x]*gauss.color.r), int(pdf[x]*gauss.color.g), int(pdf[x]*gauss.color.b)) for x in range(gauss.arrayLen)]
    ledColorArray = ColorList(tmp)
    return ledColorArray
    
def byteArray(colorList):
    alpha = lambda clr: 0xFF
    red = lambda clr: clr.r
    grn = lambda clr: clr.g
    blu = lambda clr: clr.b
    flatArray = bytearray([f(x) for x in colorList for f in (alpha, blu, grn, red)])  #create a flat list that is alpha, grn, blu, red
    return flatArray
    

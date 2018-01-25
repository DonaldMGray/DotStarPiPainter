# -*- coding: utf-8 -*-
"""
Created on Tue Jan 23 16:37:20 2018

@author: dgray
"""

import timeit

stp = """
import numpy as np
import pulses
from collections import namedtuple
gs1 = pulses.GaussCtl(144, startCtr=-80, width=50, rate=1.0, color=pulses.Color(255,0,128))
gs2 = pulses.GaussCtl(144, startCtr=-80, width=50, rate=1.0, color=pulses.Color(255,0,128))
#pulseList = [gs1, gs2, gs1, gs2, gs1, gs2]
pulseList = [gs1]
colorArrays = [pulses.makeGaussianFast(x) for x in pulseList] #build a ColorArray for each pulse
outArray = sum(colorArrays) #add them all together (clamping built in)
byteArray = pulses.byteArray(outArray)
class ColorList(list):
	def __add__(self, other):  #Color will clamp to [0-]
	    if type(other) == int: return self    #this is to support sum, which starts by adding to '0'
        newArray = ColorList( [self[x]+other[x] for x in range(len(self))] )
        return newArray
    def __radd__(self, other):
        if type(other) == int: return self    #this is to support sum, which starts by adding to '0'
        return other + self

myTuple = namedtuple('myTuple', ['r', 'g', 'b'])

"""

code = """
#pdf = np.exp(-np.power( np.array(range(gs1.arrayLen)) - gs1.currCtr, 2.) / (2 * np.power(gs1.width, 2.)))
#colorArrays = [pulses.makeGaussianFast(x) for x in pulseList] #build a ColorArray for each pulse
#outArray = sum(colorArrays) #add them all together (clamping built in)
#byteArray = pulses.byteArray(outArray)

gauss = gs1
pdf = np.exp(-np.power( np.array(range(gauss.arrayLen)) - gauss.currCtr, 2.) / (2 * np.power(gauss.width, 2.)))
#tmp = [pulses.Color(int(pdf[x]*gauss.color.r), int(pdf[x]*gauss.color.g), int(pdf[x]*gauss.color.b)) for x in range(144)]
#ledColorArray = ColorList(tmp)

#tupleList = [ myTuple( 1,2,3 ) for x in range(144) ] #this is 1ms
#tupleList = [ myTuple( 1*x,2*x,3*x ) for x in range(144) ] #this is 1.5ms
#tupleList = [ myTuple( 1.1*x,2.2*x,3.3*x ) for x in range(144) ] #this is 1.5ms #this is 1.7ms
tupleList = [ myTuple( int(1.1*x), int(2.2*x), int(3.3*x) ) for x in range(144) ] #this is 2.5ms
#tupleList = [ myTuple( int(pdf[x]*x), int(pdf[x]*x), int(pdf[x]*x) ) for x in range(144) ] #this is 7ms

pass
"""

numTests = 100
result = timeit.timeit(setup=stp, stmt = code, number=numTests)
print (result/numTests*1000, "ms per iteration")


#learnings:
# The most time seems to be taken up in building the list of Color items
# Takes ~9ms per array generation of 144 leds (4.7ms for 72; 1.3ms for 14)
# (and if we have 6 pulses, this is 50ms total)
# Indexing pdf seems to be slow

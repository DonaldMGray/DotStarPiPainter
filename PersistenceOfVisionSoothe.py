#!/usr/bin/python

# --------------------------------------------------------------------------
# LED strip - soothing and Persistance of Vision display
# Author: Donald Gray
#
# Heavily based on: 
#   DotStar Light Painter for Raspberry Pi 
# Written by Phil Burgess / Paint Your Dragon for Adafruit Industries.
#
# Adafruit invests time and resources providing this open source code,
# please support Adafruit and open-source hardware by purchasing products
# from Adafruit!
#
# Hardware requirements:
# - Raspberry Pi computer (any model)
# - DotStar LED strip (any length, but 144 pixel/m is ideal):
#   www.adafruit.com/products/2242
# - Five momentary pushbuttons for controls, such as:
#   www.adafruit.com/products/1010
# - One 74AHCT125 logic level shifter IC:
#   www.adafruit.com/products/1787
# - High-current, high-capacity USB battery bank such as:
#   www.adafruit.com/products/1566
# - Perma-Proto HAT for Raspberry Pi:
#   www.adafruit.com/products/2310
# - Various bits and bobs to integrate the above parts.  Wire, Perma-Proto
#   PCB, 3D-printed enclosure, etc.  Your approach may vary...improvise!
#
# Software requirements:
# - Raspbian (2015-05-05 "Wheezy" version recommended; can work with Jessie
#   or other versions, but Wheezy's a bit smaller and boots to the command
#   line by default).
# - Adafruit DotStar library for Raspberry Pi:
#   github.com/adafruit/Adafruit_DotStar_Pi
# - usbmount:
#   sudo apt-get install usbmount
#   See file "99_lightpaint_mount" for add'l info.
#
# --------------------------------------------------------------------------

import os
import select
import signal
import time
import RPi.GPIO as GPIO
from dotstar import Adafruit_DotStar
from evdev import InputDevice, ecodes
from lightpaint import LightPaint
from PIL import Image
import pulses
from enum import Enum

# CONFIGURABLE STUFF -------------------------------------------------------

num_leds   = 144    # Length of LED strip, in pixels
pin_mode     = 22     # GPIO pin numbers (Broadcom numbering) for 'mode' button,
pin_next   = 17     # previous image, next image and speed +/-.
pin_prev   =  4
pin_faster = 23
pin_slower = 24
order      = 'bgr'  # 'brg' for current DotStars, 'gbr' for pre-2015 strips
vflip      = 'true' # 'true' if strip input at bottom, else 'false'

# DotStar strip data & clock MUST connect to hardware SPI pins
# (GPIO 10 & 11).  12000000 (12 MHz) is the SPI clock rate; this is the
# fastest I could reliably operate a 288-pixel strip without glitching.
# You can try faster, or may need to set it lower, no telling.
# If using older (pre-2015) DotStar strips, declare "order='gbr'" above
# for correct color order.
strip = Adafruit_DotStar(num_leds, 12000000, order=order)

path      = '/media/usb'         # USB stick mount point
mousefile = '/dev/input/mouse0'  # Mouse device (as positional encoder)
eventfile = '/dev/input/event0'  # Mouse events accumulate here
dev       = None                 # None unless mouse is detected

gamma          = (2.8, 2.8, 2.8) # Gamma correction curves for R,G,B
color_balance  = (128, 255, 180) # Max brightness for R,G,B (white balance)
power_settings = (1450, 1550)    # Battery avg and peak current

# INITIALIZATION -----------------------------------------------------------

# Set control pins to inputs and enable pull-up resistors.
# Buttons should connect between these pins and ground.
GPIO.setmode(GPIO.BCM)
GPIO.setup(pin_mode    , GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(pin_prev  , GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(pin_next  , GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(pin_slower, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(pin_faster, GPIO.IN, pull_up_down=GPIO.PUD_UP)

strip.begin() # Initialize SPI pins for output

ledBuf     = strip.getPixels() # Pointer to 'raw' LED strip data
clearBuf   = bytearray([0xFF, 0, 0, 0] * num_leds)
imgNum     = 0    # Index of currently-active image
duration   = 0.08  # Image paint time, in seconds
filename   = None # List of image files (nothing loaded yet)
lightpaint = None # LightPaint object for currently-active image (none yet)
class Mode(Enum):
    soothe = 1
    image = 2
    slideshow = 3
    #for strange reason, this does not work in python 2.7 (it should)
    def nextMode(self):
        return {
            Mode.soothe: Mode.image,
            Mode.image: Mode.slideshow,
            Mode.slideshow: Mode.soothe,
        }[self]

#...so use this instead
def nextMode(curr):
    return {
        1 : 2,
        2 : 3,
        3 : 1,
    }[curr]

currMode    = Mode.soothe

# FUNCTIONS ----------------------------------------------------------------
# Signal handler when SIGUSR1 is received (USB flash drive mounted,
# triggered by usbmount and 99_lightpaint_mount script).
def sigusr1_handler(signum, frame):
	scandir()

# Ditto for SIGUSR2 (USB drive removed -- clears image file list)
def sigusr2_handler(signum, frame):
	global filename
	filename = None
	imgNum   = 0
	# Current LightPaint object is left resident

# Scan root folder of USB drive for viable image files.
def scandir():
	global imgNum, lightpaint, filename
	files     = os.listdir(path)
	num_files = len(files) # Total # of files, whether images or not
	filename  = []         # Filename list of valid images
	imgNum    = 0
	if num_files == 0: return
	for i, f in enumerate(files):
		lower =  i      * num_leds / num_files
		upper = (i + 1) * num_leds / num_files
		for n in range(lower, upper):
			strip.setPixelColor(n, 0x010100) # Yellow
		strip.show()
		if f[0] == '.': continue
		try:    Image.open(os.path.join(path, f))
		except: continue   # Is directory or non-image file; skip
		filename.append(f) # Valid image, add to list
		time.sleep(0.05)   # Tiny pause so progress bar is visible
	strip.clear()
	strip.show()
	if len(filename) > 0:                  # Found some image files?
		filename.sort()                # Sort list alphabetically
		lightpaint = loadImage(imgNum) # Load first image

# Load image, do some conversion and processing as needed before painting.
def loadImage(index):
	num_images = len(filename)
	lower      =  index      * num_leds / num_images
	upper      = (index + 1) * num_leds / num_images
	for n in range(lower, upper):
		strip.setPixelColor(n, 0x010000) # Red = loading
	strip.show()
	print "Loading '" + filename[index] + "'..."
	startTime = time.time()
	# Load image, convert to RGB if needed
	img = Image.open(os.path.join(path, filename[index])).convert("RGB")
	print "\t%dx%d pixels" % img.size

	# If necessary, image is vertically scaled to match LED strip.
	# Width is NOT resized, this is on purpose.  Pixels need not be
	# square!  This makes for higher-resolution painting on the X axis.
	if img.size[1] != num_leds:
		print "\tResizing..."
		img = img.resize((img.size[0], num_leds), Image.BICUBIC)
		print "now %dx%d pixels" % img.size

	# Convert raw RGB pixel data to a string buffer.
	# The C module can easily work with this format.
	pixels = img.tostring()
	print "\t%f seconds" % (time.time() - startTime)

	# Do external C processing on image; this provides 16-bit gamma
	# correction, diffusion dithering and brightness adjustment to
	# match power source capabilities.
	for n in range(lower, upper):
		strip.setPixelColor(n, 0x010100) # Yellow
	strip.show()
	print "Processing..."
	startTime  = time.time()
	# Pixel buffer, image size, gamma, color balance and power settings
	# are REQUIRED arguments.  One or two additional arguments may
	# optionally be specified:  "order='gbr'" changes the DotStar LED
	# color component order to be compatible with older strips (same
	# setting needs to be present in the Adafruit_DotStar declaration
	# near the top of this code).  "vflip='true'" indicates that the
	# input end of the strip is at the bottom, rather than top (I
	# prefer having the Pi at the bottom as it provides some weight).
	# Returns a LightPaint object which is used later for dithering
	# and display.
	lightpaint = LightPaint(pixels, img.size, gamma, color_balance,
	  power_settings, order=order, vflip=vflip)
	print "\t%f seconds" % (time.time() - startTime)

	# Success!
	for n in range(lower, upper):
		strip.setPixelColor(n, 0x000100) # Green
	strip.show()
	time.sleep(0.25) # Tiny delay so green 'ready' is visible
	print "Ready!"

	strip.clear()
	strip.show()
	return lightpaint

def btn():
	if not GPIO.input(pin_mode):   return 1
	if not GPIO.input(pin_faster): return 2
	if not GPIO.input(pin_slower): return 3
	if not GPIO.input(pin_next):   return 4
	if not GPIO.input(pin_prev):   return 5
	return 0

#generate the list of pulses
def createPulseDesign(ledLen):
    #this block is a set of wide pulses that travel together to create a background wash
	# "width" is the sigma of the gaussian
    gs1 = pulses.PulseCtl(arrayLen=ledLen, startCtr=80, width=25, rate=1.0, color=pulses.Color(255,0,128))
    gs2 = pulses.PulseCtl(arrayLen=ledLen, startCtr=150, width=25, rate=1.0, color=pulses.Color(128,200,0))
    gs3 = pulses.PulseCtl(arrayLen=ledLen, startCtr=0, width=25, rate=1.0, color=pulses.Color(0,128,128))
    gs4 = pulses.PulseCtl(arrayLen=ledLen, startCtr=160, width=25, rate=1.0, color=pulses.Color(100,128,158))
    
	#evenly space them at 2 sigma intervals apart
    gsr = pulses.PulseCtl(arrayLen=ledLen, startCtr= 80, width=25, rate=1.0, color=pulses.Color(255,0,0))
    gsg = pulses.PulseCtl(arrayLen=ledLen, startCtr= 150, width=25, rate=1.0, color=pulses.Color(0,255,0))
    gsb = pulses.PulseCtl(arrayLen=ledLen, startCtr= 0, width=25, rate=1.0, color=pulses.Color(0,0,255))

    # a couple smaller & faster pulses
    gs5 = pulses.PulseCtl(arrayLen=ledLen, startCtr=40, width=5, rate=4.0, color=pulses.Color(0,25,155))
    gs5.border = 200 #bigger border keeps it off the display longer
    gs6 = pulses.PulseCtl(arrayLen=ledLen, startCtr=100, width=3, rate=-6.5, color=pulses.Color(120,255,255))
    gs6.border = 500 #bigger border keeps it off the display longer
    gsList = [gs1, gs2, gs3,   gs5, gs6]
    #gsList = [gsr, gsg, gsb]
    return gsList

# MAIN LOOP ----------------------------------------------------------------

# Init some stuff for speed selection of how long to show images
max_time    = 0.4
min_time    =  0.02 # a good time is around .04
time_range  = (max_time - min_time)
speed_pixel = int(num_leds * (duration - min_time) / time_range) 
duration    = min_time + time_range * speed_pixel / (num_leds - 1) #sweep duration in seconds
prev_btn    = 0
rep_time    = 0.2
slideShowTime = 4 # time to show each image when in slideShow mode
slideStartTime = time.time()
POVShowTime = 60 	#how long to run the POV before going to soothe mode
POVStartTime = time.time()

scandir() # USB drive might already be inserted
signal.signal(signal.SIGUSR1, sigusr1_handler) # USB mount signal
signal.signal(signal.SIGUSR2, sigusr2_handler) # USB unmount signal

#generate the list of pulses for soothing mode
pulseList = createPulseDesign(num_leds)
framerate = 24
flip = True
try:
	#main loop
	while True:
		#check for button pushes
		b = btn()
		if b == 1:
	            currMode = nextMode(currMode)     # mode change from show one image to slideshow 
                    print "mode change to: ", currMode
		    if currMode != Mode.soothe:
		        POVStartTime = time.time() #switchin to POV, so restart the timer 
    		    time.sleep(0.2) #debounce
		elif b == 2:
			# Decrease paint duration
			if speed_pixel > 0:
				speed_pixel -= 1
				duration = (min_time + time_range *
				  speed_pixel / (num_leds - 1))
			strip.setPixelColor(speed_pixel, 0x000080)
			strip.show()
			startTime = time.time()
			while (btn() == 2 and ((time.time() - startTime) <
			  rep_time)): continue
			strip.clear()
			strip.show()
                        print "show duration: %f seconds" % (duration)
		elif b == 3:
			# Increase paint duration (up to 10 sec maximum)
			if speed_pixel < num_leds - 1:
				speed_pixel += 1
				duration = (min_time + time_range *
				  speed_pixel / (num_leds - 1))
			strip.setPixelColor(speed_pixel, 0x000080)
			strip.show()
			startTime = time.time()
			while (btn() == 3 and ((time.time() - startTime) <
			  rep_time)): continue
			strip.clear()
			strip.show()
                        print "show duration: %f seconds" % (duration)
		elif b == 4 and filename != None:
			# Next image (if USB drive present)
			imgNum += 1
			if imgNum >= len(filename): imgNum = 0
			lightpaint = loadImage(imgNum)
			while btn() == 4: continue
		elif b == 5 and filename != None:
			# Previous image (if USB drive present)
			imgNum -= 1
			if imgNum < 0: imgNum = len(filename) - 1
			lightpaint = loadImage(imgNum)
			while btn() == 5: continue
		#handle button hold down
		if b > 0 and b == prev_btn:
			# If button held, accelerate speed selection
			rep_time *= 0.92
			if rep_time < 0.01: rep_time = 0.01
			continue #skip drawing while button held down
		else:
			rep_time = 0.2
		prev_btn = b

		#switch to soothing mode after a while
		if (currMode != Mode.soothe) and (time.time() - POVStartTime >= POVShowTime) :
			currMode = Mode.soothe

		#temp speed checking stuff
		gsr = pulses.PulseCtl(arrayLen=num_leds, startCtr= 72, width=25, rate=1.0, color=pulses.Color(255,0,0))
		gsg = pulses.PulseCtl(arrayLen=num_leds, startCtr= 140, width=25, rate=1.0, color=pulses.Color(0,255,0))
		tmpr = pulses.makePulseFast(gsr)
		tmpg = pulses.makePulseFast(gsg)
		byter= pulses.byteArray(tmpr)  #make a bytearray
		byteg= pulses.byteArray(tmpg)  #make a bytearray
		#done speed stuff

		#run the display
		if lightpaint != None:
			# Paint!
			while False: #see how fast we can render - per timeTest, seem to be limited by the Color construction
				for i in range(5):
					tmpr = pulses.makePulseFast(gsr)
					#byte1 = pulses.byteArray(tmpr)
				if flip:
					strip.show(byter)
				else:
					strip.show(byteg)
				flip =  not flip
				#time.sleep(.01)
			if currMode == Mode.soothe:
				#generate the pulse display
				list(map(lambda x:x.update(), pulseList))   #update all pulse controls
				colorArrays = [pulses.makePulseFast(x) for x in pulseList] #build a ColorArray for each pulse
				outArray = sum(colorArrays) #add them all together (clamping built in)
				byteArray = pulses.byteArray(outArray)  #make a bytearray
				strip.show(byteArray)  #display it
				#pause for frame rate (does not factor in code delays) let the button reads happen in between.
				#code delay is so long, we remove this
				#time.sleep(1/framerate)  
			else:  #doing a POV
				if currMode == Mode.slideshow:
					#update the image if needed
					if (time.time() - slideStartTime) >= slideShowTime: #time for next image
				            imgNum += 1
				            if imgNum >= len(filename): imgNum = 0
				            lightpaint = loadImage(imgNum)
					    slideStartTime = time.time()
				startTime = time.time()
				while True:
					t1        = time.time()
					elapsed   = t1 - startTime
					if elapsed > duration: break
					# dither() function is passed a
					# destination buffer and a float
					# from 0.0 to 1.0 indicating which
					# column of the source image to
					# render.  Interpolation happens.
					lightpaint.dither(ledBuf,
					  elapsed / duration)
					strip.show(ledBuf)


except KeyboardInterrupt:
	print "Cleaning up"
	GPIO.cleanup()
	strip.clear()
	strip.show()
	print "Done!"


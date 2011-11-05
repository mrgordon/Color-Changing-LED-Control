from socket import socket, AF_INET, SOCK_DGRAM
from time import sleep
from Tkinter import *
import array
import struct
import random

##############################################################################################
## Author: Matthew Gordon                                                                   ##
## This is an object-oriented abstraction for controlling color-changing lights over DMX512 ##
##############################################################################################

###################
## Configuration ##
###################

# Set the ip and port of your power/data supply here
ip = "192.168.1.10"
port = 6038

# How many lights would you like to be able to set up? Each light takes up three channels,
# so we will allocate 3*max_lights channels for lights to run on
max_lights = 10

#######################
## DMX Communication ##
#######################

def sendlevels(levels):
    '''
    This function sends the current RGB values for each light to the power/data supply using the DMX512 protocol over UDP.
    
    The current RGB values are stored as a list where the ``n``-th entry in the list corresponds to DMX channel ``n``. We are working with RGB
    lights so each light occupies three adjacent channels, ie. "21","22", and "23".
    '''
    arr = array.array('B', levels)
    # Construct DMX UDP packet
    out = struct.pack("LHHLBxHLB255s", 0x4adc0104, 0x0001, 0x0101, 0, 0, 0, -1, 0, arr.tostring())
    try:
        socket(AF_INET, SOCK_DGRAM).sendto(out, (ip, port))
    except:
        print "Error: no route to host or host is down. Are you connected to a DMX512 power/data supply?"
       
#########################
## Abstract Data Types ##
#########################
       
class Color:
    '''
    This class represents a color in RGB space.
    '''
    def __init__(self, red, green, blue):
        self.red = red
        self.green = green
        self.blue = blue

    @staticmethod
    def generate():
        '''A static method that returns a random color as an object'''
        return Color(random.randint(0,255), random.randint(0,255), random.randint(0,255))

    def as_list(self):
        '''Returns the RGB color of this object as a list'''
        return [self.red, self.green, self.blue]

    def scale(self, factor):
        '''Returns the RGB color of this object with each component scaled by the given factor'''
        return Color(self.red*factor, self.green*factor, self.blue*factor)

    def add(self, color):
        '''Returns the color object that results from adding the two color objects'''
        return Color(self.red+color.red, self.green+color.green, self.blue+color.blue)

    def __str__(self):
        return "["+str(self.red)+" "+str(self.green)+" "+str(self.blue)+"]"
       
class Light:
    '''
    This class represents a three-channel RGB light that we can talk to over DMX512.
    '''
    active_lights = set()

    def __init__(self, address, lighting_function):
        self.address = address
        self.lighting_function = lighting_function
        self.value = Color(0,0,0)
        Light.active_lights.add(self)

    @classmethod
    def list_all(cls):
        '''A static method that returns a list of the lights that currently exist'''
        return cls.active_lights

    def destroy(self):
        Light.active_lights.remove(self)

    def change_lighting_function(self, new_function):
        self.lighting_function = new_function

    def values(self, time):
        self.value = self.lighting_function(time, self.value)
        return self.value

#################
## Light Modes ##
#################

# These functions represent different lighting modes that can be assigned to our lights using the Light constructor or change_lighting_function()
# They replicate the built-in settings that can be configured on the lights via DIP switches

def fixed_color(color):
    '''This displays a constant color on the light'''
    return lambda t, v: color
   
def cross_fade(color1, color2, interval):
    '''This displays one complete cycle of the linear combination of color1 and color2 over the specified interval'''
    def linear_fade(interval):
        '''
        Returns two lists containing the percentages of color1 and color2 at each unit of time during the specified interval
        such that we transition from color1 to color2 linearly over the interval. For a given time ``t`` during the interval,
        color1_percentages[t]+color2_percentages[t]=1
        '''
        color2_percentages = [0]*(interval)
        for t in xrange(interval):
             color2_percentages[t] = t / float(interval)
        color1_percentages = [1-x for x in color2_percentages]
        return color1_percentages, color2_percentages
    percent1, percent2 = linear_fade(interval)
    temp = percent1
    percent1 = percent1+percent2
    percent2 = percent2+temp
    return lambda t, v: color1.scale(percent1[t%(2*interval)]).add(color2.scale(percent2[t%(2*interval)]))
    
def random_color(interval):
    '''This displays a different random color on the light every interval'''
    def function(t,v):
        if (t % interval) == 0:
            return Color.generate()
        else:
            return v
    return function

def fixed_color_strobe(color, oninterval, offinterval):
    '''This displays the chosen color for oninterval and then displays black for offinterval'''
    def function(t,v):
        time = t % (oninterval+offinterval)
        if time < oninterval:
            return color
        else:
            return Color(0,0,0)
    return function

def variable_color_strobe(oninterval, offinterval):
    '''This displays a random color for oninterval and then displays black for offinterval'''
    def function(t,v):
        time = t % (oninterval+offinterval)
        if time == 0:
            return Color.generate()
        elif time < oninterval:
            return v
        else:
            return Color(0,0,0)
    return function

##########################################
## Setup lights and start running them! ##
##########################################

def setup_lights():
    '''
    This function instantiates lights on the appropriate channels and assigns their initial lighting functions.
    '''
    for x in xrange(3):
        Light(x*3, cross_fade(Color.generate(), Color.generate(), random.randint(500,1000)))
    Light(9, cross_fade(Color(255,0,0), Color(0,128,255), 1250))
    Light(12, variable_color_strobe(780, 200))
    
def run_lights(duration=0):
    '''
    Sends the current value of every DMX512 light channel for ``duration`` units of time, where each unit is roughly equal to one-sixtieth
    of a second. If ``duration`` is set to 0, then this function will run for an unlimited duration.
    '''
    if duration < 0:
        raise ValueError("arg ``duration`` to run_lights() must be greater than or equal to zero.")
    
    # Create three channels per light to store red, green, and blue values
    light_data = [0]*(3*max_lights)
    
    time = 0
    while time < duration or duration == 0:
        for light in Light.list_all():
            dmx_address = light.address
            values = light.values(time)
            light_data[dmx_address] = values.red
            light_data[dmx_address+1] = values.green
            light_data[dmx_address+2] = values.blue
        print map(lambda x: int(round(x)), light_data)
        time += 1
        sleep(.0166)
        sendlevels(map(lambda x: int(round(x)), light_data))
    
if __name__ == "__main__":
    setup_lights()
    run_lights(0)

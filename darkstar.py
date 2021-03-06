# -*- coding: utf-8 -*-
__version__ = '1.0.2'
"""
Darkstar

"Talk to the amp. You have to talk to it, Doolittle. Teach it PHENOMENOLOGY."

Control a Blackstar ID guitar amplifier with MIDI Program Change and
Control Change messages.

Author: Todd Hartmann
License:  Public Domain, Use At Your Own Risk

Darkstar is a command line app and only requires the excellent
Outsider and awesome PyGame

https://github.com/jonathanunderwood/outsider
https://www.pygame.org/wiki/GettingStarted

Outsider needs PyQt5 for its UI and PyUSB to talk to the amp

https://wiki.python.org/moin/PyQt
https://pyusb.github.io/pyusb/

To get PyUSB to run on Windows make sure to download the latest .7z archive
and put the MINGW64 libusb-1.0.dll in the same directory as your python.exe.

https://github.com/libusb/libusb/releases

Outsider will run on Windows if you make three little changes.

First, for some reason, Windows reports one extra byte transmitted.  So
change in blackstarid.py, class BlackstarIDAmp, member _send_data() ~line 463,

        bytes_written = self.device.write(self.interrupt_out, data)
to
        bytes_written = self.device.write(self.interrupt_out, data) - 1 # HEY WINDOWS SAYS ONE MORE

Then you've got to keep it from doing the kernel driver deactivation
loop in blackstarid.py, class BlackstarIDAmp member connect(),
~line 370, change

        for intf in cfg:
to
        for intf in []: #cfg:  HEY WINDOWS DON'T DO THIS KERNEL VOODOO

and do the same sorta thing in disconnect(), ~line 429, change

        cfg = self.device.get_active_configuration()
to
        cfg = [] #self.device.get_active_configuration() HEY WINDOWS NO KERNEL VOODOO

These are bad solutions but they work with a minimum of changing.
"""

# turn off PyGame message
from os import environ
environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

import blackstarid
import pygame.midi as pm

import argparse, csv, textwrap
from collections import namedtuple

def cctocontrol(ccval, name):
    """scale CC value to named control's range"""
    fcc = float(ccval) / 127.0
    lo, hi = blackstarid.BlackstarIDAmp.control_limits[name]
    answer = fcc * float(hi - lo) + lo
    return round(answer)

# map from Midi CC number to a human-friendly mixed-case version of
# blackstarid.controls.keys() (becomes the key when .lower()ed)
# it's okay to map more than one CC to a given control

controlMap = dict( [
    (7, 'Volume'),
    (22, 'Volume'), (23, 'Bass'), (24, 'Middle'), (25, 'Treble'),
    (26, 'Mod_Switch'), (27, 'Delay_Switch'), (28, 'Reverb_Switch'),
    (14, 'Voice'), (15, 'Gain'), (16, 'ISF')
] )

def readmap(filename):
    """reads a CSV file of number,name pairs into the controlMap"""
    global controlMap
    try:
        with open(filename, 'r') as cmf:
            cm = dict( [ [ int(row[0]), row[1] ] for row in csv.reader(cmf) ] )
            for k in cm.keys():
                if k < 0 or k > 127:
                    raise ValueError('Invalid MIDI CC number {0}'.format(k))
                if cm[k].lower() not in blackstarid.BlackstarIDAmp.controls.keys():
                    raise ValueError('Invalid control name "{0}"'.format(cm[k]))
            # everything is valid
            controlMap = cm
    except FileNotFoundError as e:
        raise argparse.ArgumentTypeError(e)
    except ValueError as e:
        raise argparse.ArgumentTypeError('{0} in {1}'.format(e, filename))

    return filename
#

MidiEvent = namedtuple('MidiEvent', ['status', 'd0', 'd1', 'd2', 'delta_time'])

def midiProcess(rawEvent, amp, chan=0, quiet=False):
    event = MidiEvent._make( tuple(rawEvent[0]) + (rawEvent[1],) )

    mchan = (event.status & 0x0F) + 1;    # low nybble is channel-1
    if mchan == chan or chan == 0:
        kind  = event.status & 0xF0;              # high nybble of Status is type
        if kind == 0xC0:                        # 0xC0 is Program Change
            preset = event.d0 + 1         # presets are 1-128
            if not quiet:
                print('Preset Change to {} on channel {} at time {}'.format( preset, mchan, event.delta_time ) )
            amp.select_preset(preset)
        elif kind == 0xB0:                      # 0xB0 is Control Change
            ccnum = event.d0
            ccval = event.d1
            if ccnum in controlMap.keys():
                name = controlMap[ccnum]
                val = cctocontrol(ccval, name.lower())
                if not quiet:
                    print('{0} Change to {1:3} on channel {2:2} at time {3:3}'.format( name, val, mchan, event.delta_time ))
                amp.set_control(name.lower(), val)
            if not quiet:
                print('chan {} cc {} val {}'.format(mchan, ccnum, ccval))

def midiloop(bnum, amp, chan, quiet):
    """open midi, loop until ctrl-c etc. pressed, close midi."""
    midi_in = pm.Input(bnum)

    print('Press ctrl-C to exit')
    try:
        while True:
            while(midi_in.poll()):
                event = midi_in.read(1)[0]
                midiProcess(event, amp, chan, quiet)
    except KeyboardInterrupt:
        pass

    print("Quitting")
    midi_in.close()

DevInfo = namedtuple('DevInfo', ['num', 'interf', 'name', 'input', 'output', 'opened'])

def midiInputs():
    """return a dictionary of num:name for all MIDI input devices"""
    devices = [ DevInfo._make((i,) + pm.get_device_info(i)) for i in range(pm.get_count())  ]
    inputs = { d.num:d.name.decode('UTF-8') for d in devices if d.input == 1 }
    return inputs

def buscheck(sname):
    """argparse checker for bus name or number"""
    try:
        busnum = int(sname) # see if it's a number instead of a name
    except ValueError:      # okay it's a name try to find its number
        try:
            busnum = { v:k for (k,v) in midiInputs().items() }[sname]
        except KeyError:
            raise argparse.ArgumentTypeError('Midi input "{0}" not found'.format(sname))

    if busnum not in midiInputs().keys():
        raise argparse.ArgumentTypeError('Midi input {0} not found'.format(busnum))

    return busnum

def intrangecheck(sval, ranje, sname=None):
    """argparse check that argument is an integer within a range"""
    if sname != None:
        sname = "for {0} ".format(sname)
    else:
        sname = ''
    try:
        ival = int(sval)
    except ValueError:
        raise argparse.ArgumentTypeError('Invalid value {0}{1} should be an integer'.format(sname, sval))

    if ival not in ranje:
        msg = "Invalid value {0}{1} not in range {2}-{3}".format(sname, ival, ranje.start, ranje.stop - 1)
        raise argparse.ArgumentTypeError(msg)
    return ival

def presetcheck(sval):  return intrangecheck(sval, range(1, 129))
def volumecheck(sval):  return intrangecheck(sval, range(0, 128))
def channelcheck(sval): return intrangecheck(sval, range(0, 17))

class controlchecker:
    """first check if the control name is valid, then check if value is good for that control"""
    def __init__(self):
        self.name = None

    def __call__(self, nameThenVal):
        if(self.name == None):  # first execution is control name
            lname = nameThenVal.lower()
            if lname in blackstarid.BlackstarIDAmp.controls.keys():
                self.name = lname
            else:
                raise argparse.ArgumentTypeError('Invalid control name "{0}"'.format(nameThenVal))
            return lname
        else:
            lo, hi = blackstarid.BlackstarIDAmp.control_limits[self.name]
            rv = intrangecheck(nameThenVal, range(lo, hi + 1), self.name )
            self.name = None    # reset to initial state in case of repeated use
            return rv

controlcheck = controlchecker()

def fillit(s): return textwrap.fill(' '.join(s.split()))

def main():
    pm.init()

    parser = argparse.ArgumentParser(
        description =   fillit(""" Control a Blackstar ID guitar
                                   amplifier with MIDI Program Change
                                   and Control Change messages.
                                   Version {0}.""".format(__version__)),
        epilog = '\n\n'.join( [fillit(s) for s in [
            """Darkstar probably can't keep up with an LFO signal from
               your DAW. It's for setting a value every now-and-then,
               not continuously.  Latency appears to be ~40ms YLMV.""",
            """--preset, --volume, and --control are conveniences to quickly
               set a control then exit. They can be used together.""",
            """--version, --listbus, --listmap, --listcontrols, and
               --listlimits provide useful information then exit.
               They can be used together."""]] ),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--bus', type=buscheck, default='blackstar', help='number or exact name including spaces of MIDI bus to listen on, default="blackstar"')
    parser.add_argument('--channel', type=channelcheck, default=0, help='MIDI channel 1-16 to listen on, 0=all, default=all')
    parser.add_argument('--map', type=readmap, metavar='FILENAME', help='name of file of (cc number, control name) pairs.')
    parser.add_argument('--quiet', action='store_true', help='suppress operational messages')
    parser.add_argument('--preset', type=presetcheck, help='send a preset select 1-128')
    parser.add_argument('--volume', type=volumecheck, help="set the amp's volume")
    parser.add_argument('--control', type=controlcheck, nargs=2, metavar=('NAME', 'VALUE'), help='set the named control to the value')
    parser.add_argument('--version', action='store_true', help='print Darkstar version')
    parser.add_argument('--listbus', action='store_true', help='list Midi input busses')
    parser.add_argument('--listmap', action='store_true', help='list --map or default control mapping')
    parser.add_argument('--listcontrols', action='store_true', help='list Blackstar controls')
    parser.add_argument('--listlimits', action='store_true', help='list Blackstar controls and their limits')
    args = parser.parse_args()

    if any([ args.version, args.listbus, args.listmap, args.listcontrols, args.listlimits ]):
        if args.version:
            print('Version {0}'.format(__version__))
        if args.listbus:
            print('\n'.join([ '{0} "{1}"'.format(k, v) for k,v in midiInputs().items() ]))
        if args.listmap:
            for k in sorted(controlMap.keys()):
                print('{0:3} -> {1}'.format(k, controlMap[k]))
        if args.listcontrols:
            s = ', '.join( sorted([k for k in blackstarid.BlackstarIDAmp.controls.keys()]) )
            print(textwrap.fill(s))
        if args.listlimits:
            limits = blackstarid.BlackstarIDAmp.control_limits
            for k in sorted( limits.keys() ):
                s,e = limits[k]
                print('{0}: {1}-{2}'.format(k,s,e))
    else:
        amp = blackstarid.BlackstarIDAmp()
        amp.connect()
        print('Connected to {0}'.format(amp.model))

        if any( [ args.preset, args.volume, args.control ] ):
            if args.preset:
                print('Requesting preset {0}'.format(args.preset))
                amp.select_preset(args.preset)
            if args.volume:
                print('Setting volume to {0}'.format(args.volume))
                amp.set_control('volume', args.volume)
            if args.control:
                print('Setting control {0} to {1}'.format(args.control[0], args.control[1]))
                amp.set_control(args.control[0], args.control[1])
        else:
            busstr = midiInputs()[args.bus]
            chanstr = 'MIDI channel {0}'.format(args.channel)
            if args.channel == 0:
                chanstr = 'all MIDI channels'
            print('Listening to {0} on bus "{1}"'.format(chanstr, busstr))

            midiloop(args.bus, amp, args.channel, args.quiet)   # exit main loop with KeyboardInterrupt

        amp.disconnect()
    pm.quit()
#
if __name__ == '__main__':
    main()

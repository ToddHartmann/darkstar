# -*- coding: utf-8 -*-
__version__ = '1.0.1'
"""
Darkstar

"Talk to the amp. You have to talk to it, Doolittle. Teach it PHENOMENOLOGY."

Control a Blackstar ID guitar amplifier with MIDI Program Change and
Control Change messages.

Author: Todd Hartmann
License:  Public Domain, Use At Your Own Risk

Darkstar is a command line app and only requires the excellent
Outsider and awesome rtMidi-Python

https://github.com/jonathanunderwood/outsider
https://github.com/superquadratic/rtmidi-python

Outsider needs PyQt5 for its UI and PyUSB to talk to the amp

https://wiki.python.org/moin/PyQt
https://pypi.python.org/pypi/pyusb/1.0.0

Outsider can run on Windows if you make some changes.

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

import blackstarid
import rtmidi_python as rtmidi

import argparse, csv, textwrap
from functools import partial

def midiports(midi_in):
    """return a list of strings of Midi port names"""
    # because midi_in.ports elements end with annoying space and bus number
    return [ v[0 : v.rfind(b' ')].decode('UTF-8') for v in midi_in.ports ]
#
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
    except Exception as e:
        print(e)
        print('Problem with --map {0}, using default mapping'.format(filename))

def midicallback( message, delta_time, amp, chan, quiet ):
    """respond (or not) to midi message"""
    mchan = (message[0] & 0x0F) + 1;    # low nybble is channel-1
    if mchan == chan or chan == 0:
        kind  = message[0] & 0xF0;              # high nybble of Status is type
        if kind == 0xC0:                        # 0xC0 is Program Change
            preset = message[1] + 1         # presets are 1-128
            if not quiet:
                print('Preset Change to {0:3} on channel {1:2} at time {2:.3}'.format( preset, mchan, delta_time ) )
            amp.select_preset(preset)
        elif kind == 0xB0:                      # 0xB0 is Control Change
            ccnum = message[1]
            ccval = message[2]
            if ccnum in controlMap.keys():
                name = controlMap[ccnum]
                val = cctocontrol(ccval, name.lower())
                if not quiet:
                    print('{0} Change to {1:3} on channel {2:2} at time {3:.3}'.format( name, val, mchan, delta_time ))
                amp.set_control(name.lower(), val)
            
def midiloop(midi_in, bnum):
    """open midi, loop until ctrl-c etc. pressed, close midi."""
    midi_in.open_port(bnum)

    print('Press ctrl-C to exit')
    try:
        while True:
            pass
    except KeyboardInterrupt:
        pass
    
    print("Quitting")
    midi_in.close_port()

def buscheck(sname, midi_in):
    """argparse checker meant to be used in a partial that supplies midi_in"""
    try:
        busnum = int(sname) # see if it's a number instead of a name
    except ValueError:      # okay it's a name try to find its number
        try:
            busnum = midiports(midi_in).index(sname)
        except ValueError:
            raise argparse.ArgumentTypeError('Midi bus "{0}" not found'.format(sname))

    if busnum not in range(0, len(midi_in.ports)):
        raise argparse.ArgumentTypeError('Midi bus {0} not found'.format(busnum))

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

    def __call__(self, scon):
        if(self.name == None):  # first execution is control name
            if scon in blackstarid.BlackstarIDAmp.controls.keys():
                self.name = scon
            else:
                raise argparse.ArgumentTypeError('Invalid control name "{0}"'.format(scon))
            return scon
        else:
            lo, hi = blackstarid.BlackstarIDAmp.control_limits[self.name]
            return intrangecheck(scon, range(lo, hi + 1), self.name )

controlcheck = controlchecker()

def fillit(s): return textwrap.fill(' '.join(s.split()))

def main():
    midi_in = rtmidi.MidiIn()
    midibus = partial(buscheck, midi_in=midi_in)

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
               set a control and exit. They can be used together.""",
            """--version, --listbus, --listmap, --listcontrols, and
               --listlimits provide useful information and exit.
               They can be used together."""]] ),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--bus', type=midibus, default='blackstar', help='number or exact name including spaces of MIDI bus to listen on, default="blackstar"')
    parser.add_argument('--channel', type=channelcheck, default=0, help='MIDI channel 1-16 to listen on, 0=all, default=all')
    parser.add_argument('--map', type=str, metavar='FILENAME', help='name of file of (cc number, control name) pairs.')
    parser.add_argument('--quiet', action='store_true', help='suppress operational messages')
    parser.add_argument('--preset', type=presetcheck, help='send a preset select 1-128 and exit')
    parser.add_argument('--volume', type=volumecheck, help="set the amp's volume and exit")
    parser.add_argument('--control', type=controlcheck, nargs=2, metavar=('NAME', 'VALUE'), help='set the named control to the value and exit')
    parser.add_argument('--version', action='store_true', help='print Darkstar version and exit')
    parser.add_argument('--listbus', action='store_true', help='list Midi input busses and exit')
    parser.add_argument('--listmap', action='store_true', help='list the default control mapping and exit')
    parser.add_argument('--listcontrols', action='store_true', help='list Blackstar controls and exit')
    parser.add_argument('--listlimits', action='store_true', help='list Blackstar controls and their limits then exit')
    args = parser.parse_args()

    if any([ args.version, args.listbus, args.listmap, args.listcontrols, args.listlimits ]):
        if args.version:
            print('Version {0}'.format(__version__))
        if args.listbus:
            print('\n'.join([ '{0} "{1}"'.format(e[0], e[1]) for e in enumerate(midiports(midi_in)) ]))
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

        if args.preset != None or args.volume != None or args.control != None:
            if args.preset != None:
                print('Requesting preset {0}'.format(args.preset))
                amp.select_preset(args.preset)
            if args.volume != None:
                print('Setting volume {0}'.format(args.volume))
                amp.set_control('volume', args.volume)
            if args.control != None:
                print('Setting control {0} to {1}'.format(args.control[0], args.control[1]))
                amp.set_control(args.control[0], args.control[1])
        else:
            if args.map != None:
                readmap(args.map)

            midi_in.callback = partial(midicallback, amp=amp, chan=args.channel, quiet=args.quiet)
            
            busstr = midiports(midi_in)[args.bus]
            chanstr = 'MIDI channel {0}'.format(args.channel)
            if args.channel == 0:
                chanstr = 'all MIDI channels'
            print('Listening to {0} on bus "{1}"'.format(chanstr, busstr))
            
            midiloop(midi_in, args.bus)   # exit main loop with KeyboardInterrupt

        amp.disconnect()
#
if __name__ == '__main__':
    main()

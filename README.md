# Darkstar

> "Talk to the amp. You have to talk to it, Doolittle. Teach it **phenomenology**."

Control a Blackstar ID guitar amplifier with MIDI Program Change and
Control Change messages. Version 1.0.2.

Author: [Todd Hartmann](https://github.com/ToddHartmann)\
License:  Public Domain, Use At Your Own Risk

## The Help
```
usage: darkstar.py [-h] [--bus BUS] [--channel CHANNEL] [--map FILENAME]
                   [--quiet] [--preset PRESET] [--volume VOLUME]
                   [--control NAME VALUE] [--version] [--listbus] [--listmap]
                   [--listcontrols] [--listlimits]

Control a Blackstar ID guitar amplifier with MIDI Program Change and
Control Change messages. Version 1.0.2.

optional arguments:
  -h, --help            show this help message and exit
  --bus BUS             number or exact name including spaces of MIDI bus to
                        listen on, default="blackstar"
  --channel CHANNEL     MIDI channel 1-16 to listen on, 0=all, default=all
  --map FILENAME        name of file of (cc number, control name) pairs.
  --quiet               suppress operational messages
  --preset PRESET       send a preset select 1-128
  --volume VOLUME       set the amp's volume
  --control NAME VALUE  set the named control to the value
  --version             print Darkstar version
  --listbus             list Midi input busses
  --listmap             list --map or default control mapping
  --listcontrols        list Blackstar controls
  --listlimits          list Blackstar controls and their limits

Darkstar probably can't keep up with an LFO signal from your DAW. It's
for setting a value every now-and-then, not continuously. Latency
appears to be ~40ms YLMV.

--preset, --volume, and --control are conveniences to quickly set a
control then exit. They can be used together.

--version, --listbus, --listmap, --listcontrols, and --listlimits
provide useful information then exit. They can be used together.
```

## Getting it to Run

Darkstar is a command line app and only requires the excellent
Outsider and awesome PyGame

https://github.com/jonathanunderwood/outsider
\
https://www.pygame.org/wiki/GettingStarted

Outsider needs PyQt5 for its UI and PyUSB to talk to the amp

https://wiki.python.org/moin/PyQt
\
https://pyusb.github.io/pyusb/

### PyUSB on Windows
To get PyUSB to run on Windows make sure to download the latest .7z archive
and put the MINGW64 libusb-1.0.dll in the same directory as your python.exe.

https://github.com/libusb/libusb/releases

### Outsider on Windows
Outsider will run on Windows if you make three little changes.

First, for some reason, Windows reports one extra byte transmitted.  So
change in blackstarid.py, class BlackstarIDAmp, member _send_data() ~line 463,

 	 	
`bytes_written = self.device.write(self.interrupt_out, data)`\
to\
`bytes_written = self.device.write(self.interrupt_out, data) - 1`

Then you've got to keep it from doing the kernel driver deactivation
loop in blackstarid.py, class BlackstarIDAmp member connect(),
~line 370, change

`for intf in cfg:`\
to\
`for intf in []:`

and do the same sorta thing in disconnect(), ~line 429, change

`cfg = self.device.get_active_configuration()`\
to\
`cfg = []`

These are bad solutions but they work with a minimum of changing.

#!/usr/bin/env python3

import argparse
import mido
import logging
import configparser
import subprocess
import sys
from os.path import expanduser
from enum import Enum
from evdev import uinput, ecodes as e
from pulsectl import Pulse

class nano_keys(Enum):
    TRACK_PREV = 58
    TRACK_NEXT = 59
    CYCLE = 46
    MARKER_SET = 60
    MARKER_PREV = 61
    MARKER_NEXT = 62
    PREV = 43
    NEXT = 44
    STOP = 42
    PLAY = 41
    RECORD = 45
    PARAM1_SOLO = 32
    PARAM2_SOLO = 33
    PARAM3_SOLO = 34
    PARAM4_SOLO = 35
    PARAM5_SOLO = 36
    PARAM6_SOLO = 37
    PARAM7_SOLO = 38
    PARAM8_SOLO = 39
    PARAM1_MUTE = 48
    PARAM2_MUTE = 49
    PARAM3_MUTE = 50
    PARAM4_MUTE = 51
    PARAM5_MUTE = 52
    PARAM6_MUTE = 53
    PARAM7_MUTE = 54
    PARAM8_MUTE = 55
    PARAM1_RECORD = 64
    PARAM2_RECORD = 65
    PARAM3_RECORD = 66
    PARAM4_RECORD = 67
    PARAM5_RECORD = 68
    PARAM6_RECORD = 69
    PARAM7_RECORD = 70
    PARAM8_RECORD = 71
    PARAM1_SLIDER = 0
    PARAM2_SLIDER = 1
    PARAM3_SLIDER = 2
    PARAM4_SLIDER = 3
    PARAM5_SLIDER = 4
    PARAM6_SLIDER = 5
    PARAM7_SLIDER = 6
    PARAM8_SLIDER = 7
    PARAM1_KNOB = 16
    PARAM2_KNOB = 17
    PARAM3_KNOB = 18
    PARAM4_KNOB = 19
    PARAM5_KNOB = 20
    PARAM6_KNOB = 21
    PARAM7_KNOB = 22
    PARAM8_KNOB = 23
    
    led_support = [
        TRACK_PREV,
        TRACK_NEXT,
        CYCLE,
        MARKER_SET,
        MARKER_PREV,
        MARKER_NEXT,
        PREV,
        NEXT,
        STOP,
        PLAY,
        RECORD,
        PARAM1_SOLO,
        PARAM2_SOLO,
        PARAM3_SOLO,
        PARAM4_SOLO,
        PARAM5_SOLO,
        PARAM6_SOLO,
        PARAM7_SOLO,
        PARAM8_SOLO,
        PARAM1_MUTE,
        PARAM2_MUTE,
        PARAM3_MUTE,
        PARAM4_MUTE,
        PARAM5_MUTE,
        PARAM6_MUTE,
        PARAM7_MUTE,
        PARAM8_MUTE,
        PARAM1_RECORD,
        PARAM2_RECORD,
        PARAM3_RECORD,
        PARAM4_RECORD,
        PARAM5_RECORD,
        PARAM6_RECORD,
        PARAM7_RECORD,
        PARAM8_RECORD       
    ]


class nano_led_handler(object):
    def __init__(self, port=None):
        self.port = port
    
    def set_led(self, led=None, value=None):
        if led in nano_keys.led_support.value:
            logging.debug('nano_led_handler::set: Setting led {} to {}'.format(led, value))
            if value > 0:
                value = 127
            else:
                value = 0
            self.port.send(mido.Message('control_change', control=led, value=value))
        else:
            logging.debug('nano_led_handler::set: Key {} has no led to set'.format(led))


class nano_action(object):
    def __init__(self):
        logging.error('nano_action::__init__: Not implemented!')
    
    def action(self, key=None, value=None):
        logging.error('nano_action::action: Not implemented!')


class nano_action_evdev(nano_action):
    def __init__(self, evdev_action=None, uinput=None, led_handler=None):
        self.evdev_action = evdev_action
        self.uinput = uinput
        self.led_handler = led_handler

    def action(self, key=None, value=None):
        logging.debug('nano_action_evdev::action: Keypress {} value {} triggering event {}'.format(key, value, self.evdev_action))
        self.uinput.write(e.EV_KEY, self.evdev_action, int(value/126))
        self.led_handler.set_led(led=key, value=value)
        self.uinput.syn()   


class nano_action_mute(nano_action):
    def __init__(self, audio_device=None, pactl=None, led_handler=None):
        self.audio_device = audio_device
        self.pactl = pactl
        self.muted = audio_device.mute # Would be nice if we could set the LED appropriately too
        self.led_handler = led_handler
    
    def action(self, key=None, value=None):
        if value == 127:
            logging.debug('nano_action_mute::action: Value {} for {}'.format(value, self.audio_device.name))
            if self.muted == 0:
                self.muted = 1
            else:
                self.muted = 0
            self.led_handler.set_led(led=key, value=self.muted)
            self.pactl.mute(self.audio_device, self.muted)

class nano_action_volume(nano_action):
    def __init__(self, audio_device=None, pactl=None, max_level=100):
        self.audio_device = audio_device
        self.pactl = pactl
        self.max_level = max_level # Allow volume > 100%
    
    def action(self, key=None, value=None):
        logging.debug('nano_action_volume::action: Value {} for {}'.format(value, self.audio_device.name))
        self.pactl.volume_set_all_chans(self.audio_device, ((float(msg.value) / 127.0) * (float(self.max_level) / 100.0)))

class nano_action_volume_stream(nano_action):
    def __init__(self, stream=None, pactl=None, max_level=100):
        self.stream = stream
        self.pactl = pactl
        self.max_level = max_level

    def action(self, key=None, value=None):
        try: 
            logging.debug('nano_action_volume::action: Value {} for stream {}'.format(value, self.stream))
            self.pactl.volume_set_all_chans(self.stream, ((float(msg.value) / 127.0) * (float(self.max_level) / 100.0)))
        except Exception as e: 
            logging.error("action() execution failed: {}".format(e))
            raise e

class nano_action_exec(nano_action):
    def __init__(self, command=None):
        self.command = command
    
    def action(self, key=None, value=None):
        filled_command = self.command.format(NK_KEY_ID = key, NK_KEY_VALUE = value)
        logging.debug('nano_action_exec::action: Executing {}'.format(filled_command))
        subprocess.call(filled_command, shell=True)


def get_audio_devices(pactl, sources={}, sinks={}):
    audio_devices = {}
    
    for sink in pactl.sink_list():
        if sink.name in sinks.keys():
            logging.debug('get_audio_devices: Found sink {} at {}'.format(sinks[sink.name], sink.name))
            audio_devices[sinks[sink.name]] = sink
    
    for source in pactl.source_list():
        if source.name in sources.keys():
            logging.debug('get_audio_devices: Found source {} at {}'.format(sources[source.name], source.name))
            audio_devices[sources[source.name]] = source
    
    return audio_devices

def get_sink_inputs(pactl, streams={}):
    sink_inputs = {}
    
    for sink_inputs_item in pactl.sink_input_list():
        for stream in streams:
            if sink_inputs_item.name.endswith(stream):
                logging.debug('get_sink_inputs: Found stream {} at {}'.format(streams[stream], sink_inputs_item.name))
                sink_inputs[streams[stream]] = sink_inputs_item
    if sink_inputs == {}:
        logging.warning('get_sink_inputs: No streams found')
    return sink_inputs 

def get_sink_inputs2(pactl, streams={}):
    sink_inputs = {}
    
    for sink_inputs_item in pactl.sink_input_list():
        for stream in streams:
            if sink_inputs_item.name.endswith(stream):
                logging.debug('get_sink_inputs: Found stream {} at {}'.format(streams[stream], sink_inputs_item.name))
                # Default initialization of empty dict or assign None
                init_stream = {}
                try:
                    init_stream = sink_inputs[streams[stream]]
                    break  # We've found the requested stream; exit loop.
                except KeyError:
                    # Handle non-existent key by setting input to default or None value
                    logging.debug('No matching input for {} in list of streams.'.format(streams[stream]))
                    init_stream = None # Setting it to None was recommended instead

        if not init_stream:  # Wasn't found (or failed at initialization)
            sink_inputs[streams[stream]] = None
    return sink_inputs

def parse_config(config_path, pactl, evdev, uinput, midi_out):
    action_map = {}
    led_handler = nano_led_handler(port=midi_out)
    
    config_object = configparser.ConfigParser()
    config_object.optionxform = str # Need case sensitivity
    
    if len(config_object.read(config_path)) == 0:
        logging.error('parse_config: Failed to load config file {}'.format(config_path))
        return None
    
    if 'keymap' not in config_object.sections():
        logging.error('parse_config: Config has no keymap section')
        return None
    
    sources = {}
    if 'audioinputs' in config_object.sections():
        for source_alias in config_object.options('audioinputs'):
            sources[config_object.get('audioinputs', source_alias)] = source_alias

    # this is the steams defined into the .ini file
    streams = {}
    if 'streams' in config_object.sections():
        for stream_alias in config_object.options('streams'):
            streams[config_object.get('streams', stream_alias)] = stream_alias

    sinks = {}
    if 'audiooutputs' in config_object.sections():
        for sink_alias in config_object.options('audiooutputs'):
            sinks[config_object.get('audiooutputs', sink_alias)] = sink_alias
    
    # Get PulseAudio objects for all sinks and sources
    audio_devices = get_audio_devices(pactl, sources=sources, sinks=sinks)

    # so here I get the inputs sink     
    sink_input_devices = get_sink_inputs(pactl, streams=streams )
    
    # Create action objects for each key
    for keyname in config_object.options('keymap'):
        try:
            keycode = nano_keys[keyname].value
        except:
            logging.warn('parse_config: No such key {}'.format(keyname))
            continue
        
        actions = config_object.get('keymap', keyname).split('/', 1)
        
        if len(actions) == 1:
            # Basic evdev key mapping
            try:
                evdev_action = evdev.ecodes[actions[0]]
            except:
                logging.warning('parse_config: Unknown evdev key {}'.format(actions[0]))
                continue
                
            action_map[keycode] = nano_action_evdev(evdev_action=evdev_action, uinput=uinput, led_handler=led_handler)
        
        else:
            if actions[0] == 'mute':
                # Toggle mute of audio device
                action_map[keycode] = nano_action_mute(audio_device=audio_devices[actions[1]], pactl=pactl, led_handler=led_handler)
            
            elif actions[0] == 'volume':
                # Change volume of audio device
                volume_details = actions[1].split('/', 1)
                
                if len(volume_details) == 1:
                    # No max volume override
                    action_map[keycode] = nano_action_volume(audio_device=audio_devices[volume_details[0]], pactl=pactl)
                else:
                    # Max volume override
                    action_map[keycode] = nano_action_volume(audio_device=audio_devices[volume_details[0]], pactl=pactl, max_level=float(volume_details[1]))

            elif actions[0] == 'volumestr': 
                # Change volume of audio stream
                volume_details = actions[1].split('/', 1)

                if len(volume_details) == 1:
                    # No max volume override
                    try: 
                        action_map[keycode] = nano_action_volume_stream(stream=sink_input_devices[actions[1]], pactl=pactl)
                    except: 
                        logging.warning('parse_config: Unknown stream {}'.format(actions[1]))

            elif actions[0] == 'exec':
                # Execute a command
                action_map[keycode] = nano_action_exec(command=actions[1])
            
            else:
                logging.warning('Unknown action {}'.format(config_object.get('keymap', keyname)))
    
    return action_map
        
def get_youtube_music_streams_index(stream):
    if stream.name.endswith('YouTube Music'):
        return stream.index

def get_youtube_streams_index(stream):
    if stream.name.endswith('- YouTube'):
        return stream.index


# Parse command line args, of which we only care about one - debug mode
parser = argparse.ArgumentParser()
parser.add_argument('-d', '--debug', action='store_true', help='Enable debug output')
parser.add_argument('-c', '--config', default=expanduser('~/.config/nanoKontroller.ini'), help='Path to config file')
parser.add_argument('-l', '--list-devices', action='store_true', help='List all PulseAudio devices')
parser.add_argument('-ls', '--list-streams', action='store_true', help='List all PulseAudio Sink Inputs')
args = parser.parse_args()


# Setup logging
if args.debug:
    logging.basicConfig(format='%(asctime)-15s %(levelname)-8s %(message)s', level=logging.DEBUG)
else:
    logging.basicConfig(format='%(asctime)-15s %(levelname)-8s %(message)s', level=logging.INFO)
    
logging.debug('Starting up')

# Open PulseAudio for volume control
logging.debug('Opening PulseAudio')
pactl = Pulse('nanoKontroller')

# It the user just wanted a list of PA devices, dump them and move on
if args.list_devices:
    for device in pactl.sink_list():
        print('output: {}'.format(device.name))
    for device in pactl.source_list():
        print('input: {}'.format(device.name))
    sys.exit(0)

if args.list_streams:
    youtube_streams = []
    youtube_music_streams = []
    for stream in pactl.sink_input_list():
        youtube_streams.append(get_youtube_streams_index(stream))
        youtube_music_streams.append(get_youtube_music_streams_index(stream))

    # Filter out None values
    youtube_streams = [stream for stream in youtube_streams if stream is not None]
    youtube_music_streams = [music_stream for music_stream in youtube_music_streams if music_stream is not None]

    print ("YouTube streams: " , youtube_streams)
    print ("YouTube Music streams: " , youtube_music_streams)

    sys.exit(0)

# Open the uinput object for sending fake keypresses
ui = uinput.UInput()

# Open the MIDI objects for the nanKONTROL2 device
inport = mido.open_input(mido.get_input_names()[1])
outport = mido.open_output(mido.get_input_names()[1])

# Get config
logging.debug('Trying to load config from {}'.format(args.config))
action_map = parse_config(args.config, pactl, e, ui, outport)

# Add a volume map to store current volumes for each audio device
# volume_map = {}

# Main loop
for msg in inport:
    if msg.type == 'control_change':
        logging.debug('Keypress {} value {}'.format(msg.control, msg.value))

#        # Update the volume map
#        if msg.control in action_map.keys():
#            try: 
#                action = action_map[msg.control]
#                
#                # Check if the action is a volume change
#                if isinstance(action, (nano_action_volume, nano_action_volume_stream)):
#                    # Update the volume map
#                    volume_map[action.audio_device] = float(msg.value) / 127.0
#                    
#                # Handle the action
#                action.action(key=msg.control, value=msg.value)
#            except Exception as exception:
#                logging.warning("No stream found... reparse config to get the new ones... ")
#                
#                # Re-parse the config file and update the volume map
#                action_map = parse_config(args.config, pactl, e, ui, outport)
 

        if msg.control in action_map.keys():
            try: 
                action_map[msg.control].action(key=msg.control, value=msg.value)
            except Exception as exception:
                logging.warning("No stream found... reparse config to get the new ones... ")
                action_map = parse_config(args.config, pactl, e, ui, outport)
    else:
        logging.debug('Got other message, type {}'.format(msg.type))


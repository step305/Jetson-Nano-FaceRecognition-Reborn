import sys
#sys.path.append('/home/step305/deepstream_python_apps/apps/')

import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst

from common.bus_call import bus_call
from common.FPS import GETFPS
import pyds
import argparse
import configparser

UDP_PORT_SINK = 6000
LOG_DIR_PATH = '/home/step305/USBDsk/video/'
LOG_FILE_NAME = 'logvideo0.mp4'

def main(configuration):
    # Standard GStreamer initialization
    GObject.threads_init()
    Gst.init(None)

    # Create gstreamer elements
    # Create Pipeline element that will form a connection of other elements
    pipeline = Gst.Pipeline()
    if not pipeline:
        sys.stderr.write(" Unable to create Pipeline \n")

    # Source element for reading from RTSP
    source = Gst.ElementFactory.make("udpsrc", "source")
    if not source:
        sys.stderr.write(" Unable to create Source \n")
    #source.set_property('location', "rtsp://127.0.0.1:8001/video")
    source.set_property('port', configuration['UDP'])
    #source.set_property('latency', 0)

    caps_udpsrc = Gst.ElementFactory.make("capsfilter", "udpsrc_caps")
    if not caps_udpsrc:
        sys.stderr.write(" Unable to create udpsrc capsfilter \n")
    caps_udpsrc.set_property('caps', Gst.Caps.from_string("application/x-rtp, encoding-name=H265, payload=96"))

    queue = Gst.ElementFactory.make('queue', 'video_queue')
    if not queue:
        sys.stderr.write(" Unable to create queue \n")

    rtpdepay = Gst.ElementFactory.make("rtph265depay", "rtpdepay")
    if not rtpdepay:
        sys.stderr.write(" Unable to create rtpdepay \n")
    
    parser = Gst.ElementFactory.make('h265parse', 'h265parser')
    if not parser:
        sys.stderr.write(" Unable to create h265parser \n")

    mux = Gst.ElementFactory.make("mpegtsmux", "mux")
    if not mux:
        sys.stderr.write(" Unable to create mux \n")
    
    # Make the file sink
    sink = Gst.ElementFactory.make("filesink", "filesink")
    if not sink:
        sys.stderr.write(" Unable to create filesink")
    sink.set_property('location', configuration['DIR']+configuration['FNAME'])
    sink.set_property('sync', 'false')

    pipeline.add(source)
    pipeline.add(caps_udpsrc)
    pipeline.add(queue)
    pipeline.add(rtpdepay)
    pipeline.add(parser)
    pipeline.add(mux)
    pipeline.add(sink)
    
    source.link(caps_udpsrc)
    caps_udpsrc.link(queue)
    queue.link(rtpdepay)
    rtpdepay.link(parser)
    parser.link(mux)
    mux.link(sink)
    #source.link(sink)

    # create an event loop and feed gstreamer bus mesages to it
    loop = GObject.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect ("message", bus_call, loop)

    # start play back and listen to events
    print("Starting pipeline \n")
    pipeline.set_state(Gst.State.PLAYING)
    try:
        loop.run()
    except:
        pass
    # cleanup
    print('Stopped')
    pipeline.set_state(Gst.State.NULL)

def parse_args():
    parser = argparse.ArgumentParser(description='USB camera to UDP Streaming Application Help ')
    parser.add_argument("-c", "--config",
                  help="Configuration file path", required=True)
    # Check input arguments
    if len(sys.argv)==1:
        parser.print_help(sys.stderr)
        sys.exit(1)
    args = parser.parse_args()
    return args.config

def configure_app(config_file_path):
    udp_port = UDP_PORT_SINK
    log_file = LOG_FILE_NAME
    log_dir = LOG_DIR_PATH
    config = configparser.ConfigParser()
    config.read(config_file_path)
    if 'LOG' in config:
        if 'fileName' in config['LOG']:
            log_file = config['LOG']['fileName']
        if 'path' in config['LOG']:
            log_dir = config['LOG']['path']
    if 'UDP' in config:
        if 'port' in config['UDP']:
            udp_port = int(config['UDP']['port'])
    conf = {'UDP': udp_port, 'DIR': log_dir, 'FNAME': log_file}
    return conf

if __name__ == '__main__':
    configuration = configure_app(parse_args())
    sys.exit(main(configuration))

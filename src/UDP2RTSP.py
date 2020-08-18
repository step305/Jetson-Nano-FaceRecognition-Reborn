import sys

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')
from gi.repository import GObject, Gst, GstRtspServer

from common.bus_call import bus_call
from common.FPS import GETFPS
import pyds
import argparse
import configparser

UDP_PORT_SINK = 5000
RTSP_PORT_SRC = 8000

def rtsp_pipeline(configuration):
    # Start streaming
    server = GstRtspServer.RTSPServer.new()
    server.props.service = "{}".format(configuration['RTSP'])
    server.attach(None)
    
    factory = GstRtspServer.RTSPMediaFactory.new()
    factory.set_launch( "( udpsrc name=pay0 port={} buffer-size=122488 caps=\"application/x-rtp, media=video, clock-rate=90000, encoding-name=H265, payload=96 \" )".format(configuration['UDP']))
    factory.set_shared(True)
    server.get_mount_points().add_factory("/video", factory)
    
    print("\n *** DeepStream: Launched RTSP Streaming at rtsp://localhost:{}/video ***\n\n".format(configuration['RTSP']))

def main(configuration):
    # Standard GStreamer initialization
    GObject.threads_init()
    Gst.init(None)

    # Create gstreamer elements
    # Create Pipeline element that will form a connection of other elements
    pipeline = Gst.Pipeline()
    if not pipeline:
        sys.stderr.write(" Unable to create Pipeline \n")

    # create an event loop and feed gstreamer bus mesages to it
    loop = GObject.MainLoop()

    # start RTSP server
    rtsp_pipeline(configuration)

    try:
        loop.run()
    except:
        pass
    # cleanup
    print('Stopped')

def parse_args():
    parser = argparse.ArgumentParser(description='UDP to RTSP Streaming Application Help ')
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
    rtsp_port = RTSP_PORT_SRC
    config = configparser.ConfigParser()
    config.read(config_file_path)
    if 'UDP' in config:
        if 'port' in config['UDP']:
            udp_port = int(config['UDP']['port'])
    if 'RTSP' in config:
        if 'port' in config['RTSP']:
            rtsp_port = int(config['RTSP']['port'])
    conf = {'UDP': udp_port, 'RTSP': rtsp_port}
    return conf

if __name__ == '__main__':
    configuration = configure_app(parse_args())
    sys.exit(main(configuration))

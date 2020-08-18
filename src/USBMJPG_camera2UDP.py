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

UDP_HIGH_PORT_SINK = 5000
UDP_LOW_PORT_SINK = 5001
UDP_HIGH_BITRATE = 25000000
UDP_LOW_BITRATE = 8000000
UDP_HIGH_WIDTH = 1920
UDP_HIGH_HEIGHT = 1080
UDP_LOW_WIDTH = 1280
UDP_LOW_HEIGHT = 720
USB_CAMERA = '/dev/video0'
USB_CAMERA_WIDTH = 1920
USB_CAMERA_HEIGHT = 1080
USB_CAMERA_FORMAT = 'NV12'
USB_CAMERA_FRAMERATE = 30

class CAMERA_CONFIG:
    device = USB_CAMERA
    width = USB_CAMERA_WIDTH
    height = USB_CAMERA_HEIGHT
    format = USB_CAMERA_FORMAT
    frame_rate = USB_CAMERA_FRAMERATE

    def __init__(self):
        pass

class UDP_SINK:
    port = UDP_HIGH_PORT_SINK
    bitrate = UDP_HIGH_BITRATE
    width = UDP_HIGH_WIDTH
    height = UDP_HIGH_HEIGHT

    def __init__(self):
        pass

def main(configuration):
    cam_configuration, udp_high_configuration, udp_low_configutration = configuration 

    # Standard GStreamer initialization
    GObject.threads_init()
    Gst.init(None)

    # Create gstreamer elements
    # Create Pipeline element that will form a connection of other elements
    pipeline = Gst.Pipeline()
    if not pipeline:
        sys.stderr.write(" Unable to create Pipeline \n")

    # Source element for reading from USB camera
    source = Gst.ElementFactory.make("v4l2src", "usb-cam-source")
    if not source:
        sys.stderr.write(" Unable to create Source \n")
    source.set_property('device', cam_configuration.device)
    source.set_property('do-timestamp', 1)
    
    caps_v4l2src = Gst.ElementFactory.make("capsfilter", "v4l2src_caps")
    if not caps_v4l2src:
        sys.stderr.write(" Unable to create v4l2src capsfilter \n")
    caps_v4l2src.set_property('caps', Gst.Caps.from_string("image/jpeg, width={}, height={}, framerate={}/1, format=MJPG".format( \
                cam_configuration.width, cam_configuration.height , cam_configuration.frame_rate)))

    # jpegparser to make sure a superset of raw formats are supported
    jpegparser = Gst.ElementFactory.make("jpegparse", "jpegparse_src")
    if not jpegparser:
        sys.stderr.write(" Unable to create jpegparser \n")
    
    # jpegdecoder to make sure a superset of raw formats are supported
    jpegdecoder = Gst.ElementFactory.make("jpegdec", "jpegdecoder")
    if not jpegdecoder:
        sys.stderr.write(" Unable to create jpegdecoder \n")

    # videoconvertsrc to make sure a superset of raw formats are supported
    videoconvertsrc = Gst.ElementFactory.make("videoconvert", "videoconvert-src1")
    if not videoconvertsrc:
        sys.stderr.write(" Unable to create videoconvertsrc \n")

    # nvvideoconvert to convert incoming raw buffers to NVMM Mem (NvBufSurface API)
    nvvidconvsrc = Gst.ElementFactory.make("nvvideoconvert", "convertor_src2")
    if not nvvidconvsrc:
        sys.stderr.write(" Unable to create Nvvideoconvert \n")

    caps_vidconvsrc = Gst.ElementFactory.make("capsfilter", "nvmm_caps")
    if not caps_vidconvsrc:
        sys.stderr.write(" Unable to create capsfilter \n")
    caps_vidconvsrc.set_property('caps', Gst.Caps.from_string("video/x-raw(memory:NVMM), format=NV12"))

    tee = Gst.ElementFactory.make("tee", "tee")
    if not tee:
        sys.stderr.write("Unable to create tee \n")

    # nvvideoconvert to resize
    resize_high = Gst.ElementFactory.make("nvvideoconvert", "tee-resize-high")
    if not resize_high:
        sys.stderr.write(" Unable to create Resize-high \n")

    caps_resize_high = Gst.ElementFactory.make("capsfilter", "resize-high-caps")
    if not caps_resize_high:
        sys.stderr.write(" Unable to create caps_resize_high \n")
    caps_resize_high.set_property('caps', Gst.Caps.from_string("video/x-raw(memory:NVMM), width={}, height={}".format( \
                                            udp_high_configuration.width, udp_high_configuration.height)))

    # nvvideoconvert to resize
    resize_low = Gst.ElementFactory.make("nvvideoconvert", "tee-resize-low")
    if not resize_low:
        sys.stderr.write(" Unable to create Resize-low \n")

    caps_resize_low = Gst.ElementFactory.make("capsfilter", "resize-low-caps")
    if not caps_resize_low:
        sys.stderr.write(" Unable to create caps_resize_low \n")
    caps_resize_low.set_property('caps', Gst.Caps.from_string("video/x-raw(memory:NVMM), width={}, height={}".format( \
                                            udp_low_configutration.width, udp_low_configutration.height)))

    # Make the encoder_high
    encoder_high = Gst.ElementFactory.make("nvv4l2h265enc", "tee-encoder-high")
    if not encoder_high:
        sys.stderr.write(" Unable to create encoder-high")
    encoder_high.set_property('bitrate', udp_high_configuration.bitrate)
    encoder_high.set_property('maxperf-enable', 1)
    encoder_high.set_property('preset-level', 1)
    encoder_high.set_property('insert-sps-pps', 1)
    encoder_high.set_property('bufapi-version', 1)
    encoder_high.set_property('profile', 1)
    encoder_high.set_property('iframeinterval', 5)

    # Make the encoder_low
    encoder_low = Gst.ElementFactory.make("nvv4l2h265enc", "tee-encoder-low")
    if not encoder_low:
        sys.stderr.write(" Unable to create encoder-low")
    encoder_low.set_property('bitrate', udp_low_configutration.bitrate)
    encoder_low.set_property('maxperf-enable', 1)
    encoder_low.set_property('preset-level', 3)
    encoder_low.set_property('insert-sps-pps', 1)
    encoder_low.set_property('bufapi-version', 1)
    encoder_low.set_property('profile', 1)
    encoder_low.set_property('iframeinterval', 5)

    #Make parser_high
    parser_high = Gst.ElementFactory.make("h265parse", "tee-parser-high")
    if not parser_high:
        sys.stderr.write("Unable to create parser-high")
    
    #Make parser_low
    parser_low = Gst.ElementFactory.make("h265parse", "tee-parser-low")
    if not parser_low:
        sys.stderr.write("Unable to create parser-low")

    # Make the payload-encode video into RTP packets
    rtppay_high = Gst.ElementFactory.make("rtph265pay", "tee-rtppay-high")
    if not rtppay_high:
        sys.stderr.write(" Unable to create rtppay-high")

    # Make the payload-encode video into RTP packets
    rtppay_low = Gst.ElementFactory.make("rtph265pay", "tee-rtppay-low")
    if not rtppay_low:
        sys.stderr.write(" Unable to create rtppay-low")
    
    # Make the UDP sink-high
    sink_high = Gst.ElementFactory.make("udpsink", "udpsink-high")
    if not sink_high:
        sys.stderr.write(" Unable to create udpsink-high")
    sink_high.set_property('host', '127.0.0.1')
    sink_high.set_property('port', udp_high_configuration.port)
    sink_high.set_property('async', False)
    sink_high.set_property('sync', 0)

    # Make the UDP sink-low
    sink_low = Gst.ElementFactory.make("udpsink", "udpsink-low")
    if not sink_low:
        sys.stderr.write(" Unable to create udpsink-low")
    sink_low.set_property('host', '127.0.0.1')
    sink_low.set_property('port', udp_low_configutration.port)
    sink_low.set_property('async', False)
    sink_low.set_property('sync', 0)

    pipeline.add(source)
    pipeline.add(caps_v4l2src)
    pipeline.add(jpegparser)
    pipeline.add(jpegdecoder)
    pipeline.add(videoconvertsrc)
    pipeline.add(nvvidconvsrc)
    pipeline.add(caps_vidconvsrc)
    pipeline.add(tee)
    pipeline.add(resize_high)
    pipeline.add(resize_low)
    pipeline.add(caps_resize_high)
    pipeline.add(caps_resize_low)
    pipeline.add(encoder_high)
    pipeline.add(encoder_low)
    pipeline.add(parser_high)
    pipeline.add(parser_low)
    pipeline.add(rtppay_high)
    pipeline.add(rtppay_low)
    pipeline.add(sink_high)
    pipeline.add(sink_low)
    
    source.link(caps_v4l2src)
    caps_v4l2src.link(jpegparser)
    jpegparser.link(jpegdecoder)
    jpegdecoder.link(videoconvertsrc)
    videoconvertsrc.link(nvvidconvsrc)
    nvvidconvsrc.link(caps_vidconvsrc)

    caps_vidconvsrc.link(tee)

    resize_high.link(caps_resize_high)
    caps_resize_high.link(encoder_high)
    encoder_high.link(parser_high)
    parser_high.link(rtppay_high)
    rtppay_high.link(sink_high)

    resize_low.link(caps_resize_low)
    caps_resize_low.link(encoder_low)
    encoder_low.link(parser_low)
    parser_low.link(rtppay_low)
    rtppay_low.link(sink_low)

    tee_low_pad = tee.get_request_pad('src_0')
    tee_high_pad = tee.get_request_pad('src_1')
    if not tee_high_pad or not tee_low_pad:
        sys.stderr.write('Unable to get src pads of tee \n')
    sink_high_pad = resize_high.get_static_pad("sink")
    tee_high_pad.link(sink_high_pad)
    sink_low_pad = resize_low.get_static_pad("sink")
    tee_low_pad.link(sink_low_pad)
    
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

def get_config_value(config, section, parameter, default_value):
    param = default_value
    if section in config:
        if parameter in config[section]:
            param = config[section][parameter]
    return param

def configure_app(config_file_path):
    config = configparser.ConfigParser()
    config.read(config_file_path)

    udp_high_config = UDP_SINK()
    udp_low_config = UDP_SINK()
    usb_camera_config = CAMERA_CONFIG()

    usb_camera_config.device = get_config_value(config, 'CAMERA', 'device', USB_CAMERA)
    usb_camera_config.width = int(get_config_value(config, 'CAMERA', 'width', USB_CAMERA_WIDTH))
    usb_camera_config.height = int(get_config_value(config, 'CAMERA', 'height', USB_CAMERA_HEIGHT))
    usb_camera_config.format = get_config_value(config, 'CAMERA', 'format', USB_CAMERA_FORMAT)
    usb_camera_config.frame_rate = int(get_config_value(config, 'CAMERA', 'frame_rate', USB_CAMERA_FRAMERATE))

    udp_high_config.port = int(get_config_value(config, 'UDP-HIGH', 'port', UDP_HIGH_PORT_SINK))
    udp_high_config.width = int(get_config_value(config, 'UDP-HIGH', 'width', UDP_HIGH_WIDTH))
    udp_high_config.height = int(get_config_value(config, 'UDP-HIGH', 'height', UDP_HIGH_HEIGHT))
    udp_high_config.bitrate = int(get_config_value(config, 'UDP-HIGH', 'bitrate', UDP_HIGH_BITRATE))

    udp_low_config.port = int(get_config_value(config, 'UDP-LOW', 'port', UDP_LOW_PORT_SINK))
    udp_low_config.width = int(get_config_value(config, 'UDP-LOW', 'width', UDP_LOW_WIDTH))
    udp_low_config.height = int(get_config_value(config, 'UDP_LOW', 'height', UDP_LOW_HEIGHT))
    udp_low_config.bitrate = int(get_config_value(config, 'UDP-LOW', 'bitrate', UDP_LOW_BITRATE))

    return (usb_camera_config, udp_high_config, udp_low_config)

if __name__ == '__main__':
    configuration = configure_app(parse_args())
    sys.exit(main(configuration))

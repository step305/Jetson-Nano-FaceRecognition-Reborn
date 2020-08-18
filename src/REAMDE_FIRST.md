Code is unsorted for now. Should sort and rewrite some code from tensorrt-demo.
Working scripts^
- UDP2FILE.py - video logger. Video got from UDP stream (formed by GStreamer) and saved to file. Configuration is done by VideoLoggerconfig.txt
- USB_camera2UDP.py - USB camera capture and stream to UDP port. Tested on Logitech BRIO 4K. Configuration is done by USBcameraconfig.txt
- UDP2RTSP.py - RTSP server. Video is captured from UDP. Configuration is done by RTSPconfig.txt. Supported multiple RTSP servers (tested on two instances)
- UDP2Detector.py - face detection and recognition is done here (for now only detection, align and face encodings are ready).
  Video is captured from UDP. Configuration is done by detectorconfig.txt
- USBMJPG_camera2UDP.py - USB camera capture and stream to UDP. Special case for JPEG camera. May be buggy. Configuration is done by USBcameraJPEGconfig.txt

Other files are from https://github.com/jkjung-avt/tensorrt_demos.git and not sure what files are necessary.
mntUSBdsk.sh - some stuf for mounting USB disk for video logging.

Sample workflow:

python3 USB_camera2UDP.py -c USBcameraconfig.txt &
python3 UDP2RTSP.py -c RTSPconfig.txt &
python3 UDP2Detector -c detectorconfig.txt &
python3 UDP2RTSP.py -c RTSPconfig2.txt &
python3 UDP2FILE.py -c VideoLoggerconfig.txt &

something like that...

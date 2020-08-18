import sys
import time
import argparse
import configparser
import numpy as np
#sys.path.append('mtcnn/')

import cv2
from utils.mtcnn import TrtMtcnn
import multiprocessing as mp
from skimage import transform as trans

import face_recognition as FR

UDP_PORT_SINK = 5000
UDP_PORT_SRC = 6000
IMG_WIDTH = 1280
IMG_HEIGT = 720
IMG_FRAME_RATE = 30
BITRATE = 8000000
BBOX_COLOR = (0, 255, 0)  # green

FACES_RIBBON_COORDS = [[0, 300, 0, 300], [300, 600, 0, 300], [0, 300, 300, 600], [300, 600, 300, 600]]

SRC_NORM = np.array([
        [30.2946, 51.6963],
        [65.5318, 51.5014],
        [48.0252, 71.7366],
        [33.5493, 92.3655],
        [62.7299, 92.2041] ], dtype=np.float32)
SRC_NORM[:,0] += 8
SRC_NORM = SRC_NORM/112

class DETECTOR_CONFIG:
    udp_sink = UDP_PORT_SINK
    udp_src = UDP_PORT_SRC
    width_in = IMG_WIDTH
    height_in = IMG_HEIGT
    width_out = IMG_WIDTH
    height_out = IMG_HEIGT
    rate = IMG_FRAME_RATE
    bitrate = BITRATE

    def __init__(self):
        pass

def parse_args():
    parser = argparse.ArgumentParser(description='Face Detect Application Help ')
    parser.add_argument("-c", "--config",
                  help="Configuration file path", required=True)
    # Check input arguments
    if len(sys.argv)==1:
        parser.print_help(sys.stderr)
        sys.exit(1)
    args = parser.parse_args()
    return args.config

def show_text(img, txt):
    font = cv2.FONT_HERSHEY_PLAIN
    line = cv2.LINE_AA
    cv2.putText(img, txt, (11, 30), font, 2.0, (32, 32, 32), 8, line)
    cv2.putText(img, txt, (10, 30), font, 2.0, (240, 240, 240), 2, line)
    return img

def area(box):
    x1, y1, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
    return (x2-x1)*(y2-y1)

def extract_faces(img, boxes, landmarks):
    faces = []
    bound = img.shape

    for bb, ll in zip(boxes, landmarks):
        x1, y1, x2, y2 = int(bb[0]), int(bb[1]), int(bb[2]), int(bb[3])
        face = img[y1:y2, x1:x2]
        faces.append(face.copy())
    return faces

def show_faces(img, boxes, landmarks):
    """Draw bounding boxes and face landmarks on image."""
    for bb, ll in zip(boxes, landmarks):
        x1, y1, x2, y2 = int(bb[0]), int(bb[1]), int(bb[2]), int(bb[3])
        cv2.rectangle(img, (x1, y1), (x2, y2), BBOX_COLOR, 2)
        for j in range(5):
            cv2.circle(img, (int(ll[j]), int(ll[j+5])), 2, BBOX_COLOR, 2)
    return img

def alignFace(img, landmark):
    image_size = img.shape
    src = SRC_NORM.copy()
    src[:,0] = src[:,0] * image_size[1]
    src[:,1] = src[:,1] * image_size[0]
    dst = landmark.astype(np.float32)

    tform = trans.SimilarityTransform()
    tform.estimate(dst, src)
    M = tform.params[0:2,:]

    warped = cv2.warpAffine(img, M, (image_size[1],image_size[0]), borderValue = 0.0)

    wface = (src[1,0] - src[0,0])*2
    hfaceH = (src[2,1] - src[0,1])*2
    hfaceL = (src[3,1] - src[2,1])*2
    pointC = np.dot(M[0:2,0:2], dst[2,:])
    pointLeftEye = np.dot(M[0:2,0:2], dst[0,:])
    pointRightEye = np.dot(M[0:2,0:2], dst[1,:])
    pointRightMouth = np.dot(M[0:2,0:2], dst[4,:])
    pointLeftMouth = np.dot(M[0:2,0:2], dst[3,:])
    yUp = max(pointLeftEye[1], pointRightEye[1])+M[1,2]
    yDown = min(pointRightMouth[1], pointLeftMouth[1])+M[1,2]
    xLeft = min(pointLeftEye[0], pointLeftMouth[0])+M[0,2]
    xRight = max(pointRightEye[0], pointRightMouth[0])+M[0,2]
    hFace = yDown - yUp
    wFace = xRight - xLeft

    yL = int(max(yUp-hFace/2, 0))
    yH = int(min(yDown+hFace/3, image_size[0]))
    xL = int(max(xLeft-wFace/3, 0))
    xH = int(min(xRight+wFace/3, image_size[1]))
    warped = warped[yL:yH, xL:xH]
    #for j in range(5):
    #    cv2.circle(warped, (int(src[j][0]), int(src[j][1])), 2, BBOX_COLOR, 2)
    warped= cv2.resize(warped, (300,300))
    

    return warped

def processImage(frameBuf, boxesBuf, exitKey):
    mtcnn = TrtMtcnn()
    while not exitKey.is_set():
        if not frameBuf.empty():
            img = frameBuf.get()
            img_shape = img.shape
            img2 = cv2.resize(img, (1280,720))
            dets, landmarks = mtcnn.detect(img2, minsize=40)
            print('{} face(s) found'.format(len(dets)))
            for i in range(len(dets)):
                for j in range(5):
                    landmarks[i][j] = landmarks[i][j]/1280*img_shape[1]
                    landmarks[i][j+5] = landmarks[i][j+5]/720*img_shape[0]
                dets[i][0] = dets[i][0]/1280*img_shape[1]
                dets[i][1] = dets[i][1]/720*img_shape[0]
                dets[i][2] = dets[i][2]/1280*img_shape[1]
                dets[i][3] = dets[i][3]/720*img_shape[0]
            faces = extract_faces(img, dets, landmarks)
            nboxes = []
            nlands = []
            fcs = []
            for bb, ll, fc in zip(dets, landmarks, faces):
                if bb[4] > 0.89:
                    nboxes.append(bb)
                    nlands.append(ll)
                    if len(ll) == 10:
                        x1, y1, x2, y2 = int(bb[0]), int(bb[1]), int(bb[2]), int(bb[3])
                        land = np.array([[ll[0]-x1, ll[5]-y1], [ll[1]-x1, ll[6]-y1], \
                            [ll[2]-x1, ll[7]-y1], [ll[3]-x1, ll[8]-y1], [ll[4]-x1, ll[9]-y1]], np.float32)
                        fcs.append(alignFace(fc, land))
                    else:
                        fc = cv2.resize(fc, (300,300))
                        fcs.append(fc)
            if boxesBuf.empty():
                boxesBuf.put((nboxes, nlands, fcs))
    del(mtcnn)

def main(configuration):
    capture_gst_pipeline = 'udpsrc port={} ! application/x-rtp, encoding-name=H265, payload=96 ! ' \
                    'rtph265depay ! h265parse ! decodebin ! nvvidconv ! video/x-raw, width={}, height={}, format=BGRx ! '\
                    'videoconvert ! video/x-raw, format=BGR ! appsink'.format(configuration.udp_src, configuration.width_in, configuration.height_in)
    writer_gst_pipeline = 'appsrc ! videoconvert ! video/x-raw, format=NV12 ! ' \
                    'nvvidconv ! video/x-raw(memory:NVMM), width={}, height={}, format=NV12 ! nvv4l2h265enc bitrate={} maxperf-enable=1 '\
                    'preset-level=1 insert-sps-pps=1 profile=1 iframeinterval=1 ! h265parse ! rtph265pay ! udpsink host=127.0.0.1 '\
                    'port={} async=0 sync=0'.format(configuration.width_out, configuration.height_out, configuration.bitrate, configuration.udp_sink)
    
    writer_faces_gst_pipeline = 'appsrc ! videoconvert ! video/x-raw, format=NV12 ! ' \
                    'nvvidconv ! video/x-raw(memory:NVMM), width={}, height={}, format=NV12 ! nvv4l2h265enc bitrate={} maxperf-enable=1 '\
                    'preset-level=1 insert-sps-pps=1 profile=1 iframeinterval=1 ! h265parse ! rtph265pay ! udpsink host=127.0.0.1 '\
                    'port={} async=0 sync=0'.format(600, 600, 4000000, configuration.udp_sink+1)

    cam = cv2.VideoCapture(capture_gst_pipeline, cv2.CAP_GSTREAMER)
    writer = cv2.VideoWriter(writer_gst_pipeline, 0, configuration.rate, (configuration.width_in, configuration.height_in))
    writer_faces = cv2.VideoWriter(writer_faces_gst_pipeline, 0, configuration.rate, (600, 600))

    imgBuffer = mp.Queue(1)
    rectsBuffer = mp.Queue(1)
    stopKey = mp.Event()
    detectorProc = mp.Process(target=processImage, args=(imgBuffer, rectsBuffer, stopKey), daemon=True)
    detectorProc.start()
    boxes = []

    faces_ribbon = np.zeros((600, 600, 3), np.uint8)

    while 1:
        try:
            ret, frame = cam.read()
            if not ret:
                continue
            if frame is not None:
                if imgBuffer.empty():
                    imgBuffer.put(frame.copy())
            if not rectsBuffer.empty():
                boxes, landmarks, faces = rectsBuffer.get()
            if len(boxes) > 0:
                N = len(faces)
                if N > 4:
                    N = 4
                faces_ribbon = np.zeros((600, 600, 3), np.uint8)
                for i in range(0,N):
                    faces_ribbon[FACES_RIBBON_COORDS[i][0]:FACES_RIBBON_COORDS[i][1], FACES_RIBBON_COORDS[i][2]:FACES_RIBBON_COORDS[i][3]] = faces[i]
                show_faces(frame, boxes, landmarks)
                show_text(frame, '{} faces found'.format(len(boxes)))
            else:
                faces_ribbon = np.zeros((600, 600, 3), np.uint8)
            writer_faces.write(faces_ribbon)
            writer.write(frame)
        except:
            cam.release()
            writer.release()
            writer_faces.release()
            stopKey.set()
            detectorProc.terminate()
            break

def get_config_value(config, section, parameter, default_value):
    param = default_value
    if section in config:
        if parameter in config[section]:
            param = config[section][parameter]
    return param

def configure_app(config_file_path):
    config = configparser.ConfigParser()
    config.read(config_file_path)

    detector_config = DETECTOR_CONFIG()

    detector_config.udp_src = int(get_config_value(config, 'UDP_INPUT', 'port', UDP_PORT_SINK))
    detector_config.width_in = int(get_config_value(config, 'UDP_INPUT', 'width', IMG_WIDTH))
    detector_config.height_in = int(get_config_value(config, 'UDP_INPUT', 'height', IMG_HEIGT))
    detector_config.rate = int(get_config_value(config, 'UDP_INPUT', 'rate', IMG_FRAME_RATE))
    detector_config.udp_sink = int(get_config_value(config, 'UDP_OUTPUT', 'port', UDP_PORT_SRC))
    detector_config.width_out = int(get_config_value(config, 'UDP_OUTPUT', 'width', IMG_WIDTH))
    detector_config.height_out = int(get_config_value(config, 'UDP_OUTPUT', 'height', IMG_HEIGT))
    detector_config.bitrate = int(get_config_value(config, 'UDP_OUTPUT', 'bitrate', BITRATE))

    return detector_config

if __name__ == '__main__':
    configuration = configure_app(parse_args())
    sys.exit(main(configuration))

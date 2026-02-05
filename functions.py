import concurrent.futures as cf
import functools
import itertools
import operator
import re
import sys
import time
from collections import deque
from multiprocessing import Lock, shared_memory

import cv2
import Decorator as D
import numpy as np
from PIL import Image, ImageSequence, ImageTk

import utility as u

ThreadExecutor = cf.ThreadPoolExecutor()
LandScape = "landscape"
Portrait = "portrait"


def toGeometry(width, height, left, top):
  return f"{width}x{height}+{left}+{top}"


def fromGeometry(geometry):
  m = re.match(r"(?P<width>\d+)x(?P<height>\d+)\+(?P<left>\d+)\+(?P<top>\d+)", geometry)
  if m is not None:
    return (int(m["width"]), int(m["height"]), int(m["left"]), int(m["top"]))
  return (0, 0, 0, 0)


def getFiles(path, isRecurse, extensions=None):
  files = deque(path.iterdir())
  result = []
  while len(files) > 0:
    file = files.popleft()
    if file.is_file() and (extensions is None or file.suffix in extensions):
      result.append({"path": file})
    elif file.is_dir() and isRecurse:
      files.extend(file.iterdir())
  return u.naturalSorted(result, key=lambda x: str(x["path"]))


def resizeImage(image, width, height):
  w, h = image.shape[1], image.shape[0]
  ratio = min(width / w, height / h)
  size = (int(w * ratio), int(h * ratio))
  return cv2.resize(image, size, interpolation=cv2.INTER_LANCZOS4)


def getFrame(frame, width, height, angle):
  if angle == 180:
    frame = cv2.rotate(frame, cv2.ROTATE_180)
  return cvToPil(resizeImage(frame, width, height))


@D.printFuncInfo()
def getAllFrames(animation, width, height, angle):
  func = functools.partial(getFrame, width=width, height=height, angle=angle)
  results = ThreadExecutor.map(func, animation.frames, timeout=60)
  return list(results)


def getOrientation(size):
  return LandScape if size[0] >= size[1] else Portrait


def getSubWindowIndex(resolutions, orientation):
  for i, (_, _, o) in enumerate(resolutions):
    if orientation == o:
      return i
  return 0


@D.printFuncInfo()
def readAnimation(path):
  if not path.is_file():
    return None
  with path.open("rb") as file:
    buf = np.frombuffer(file.read(), dtype=np.uint8).reshape(1, -1)
  success, animation = cv2.imdecodeanimation(buf)
  if not success:
    return None
  return animation


@D.printFuncInfo()
def openImage(path, resolutions, angle):
  animation = readAnimation(path)
  size = (animation.frames[0].shape[1], animation.frames[0].shape[0])
  index = getSubWindowIndex(resolutions, getOrientation(size))
  images = getAllFrames(animation, resolutions[index][0], resolutions[index][1], angle)
  return {
    "path": path,
    "originalSize": size,
    "subWindow": index,
    "images": images,
    "durations": animation.durations.tolist(),
  }


def subPaths(path1, path2):
  pattern = re.sub(r"\\", r"\\\\", str(path1))
  return re.sub(rf"{pattern}", ".", rf"{path2}")


def cvToPil(image):
  newImage = image.copy()
  if newImage.ndim == 2:  # モノクロ
    pass
  elif newImage.shape[2] == 3:  # カラー
    newImage = cv2.cvtColor(newImage, cv2.COLOR_BGR2RGB)
  elif newImage.shape[2] == 4:  # 透過
    newImage = cv2.cvtColor(newImage, cv2.COLOR_BGRA2RGBA)
  return Image.fromarray(newImage)

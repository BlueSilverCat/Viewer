import concurrent.futures as cf
import functools
import re
import threading

from PIL import Image, ImageSequence, ImageTk

import utility as u

LandScape = "landscape"
Portrait = "portrait"
Extensions = (
  ".jpg",
  ".webp",
  ".png",
  ".gif",
)


def toGeometry(width, height, left, top):
  return f"{width}x{height}+{left}+{top}"


def fromGeometry(geometry):
  m = re.match(r"(?P<width>\d+)x(?P<height>\d+)\+(?P<left>\d+)\+(?P<top>\d+)", geometry)
  if m is not None:
    return (int(m["width"]), int(m["height"]), int(m["left"]), int(m["top"]))
  return (0, 0, 0, 0)


def getFiles(path, isRecurse):
  files = []
  for file in path.iterdir():
    if file.is_file() and file.suffix in Extensions:
      files.append({"path": file})
    if file.is_dir() and isRecurse:
      files += getFiles(file, True)
  return files


def resizeImage(image, width, height):
  w, h = image.size
  ratio = min(width / w, height / h)
  size = (int(w * ratio), int(h * ratio))
  return image.resize(size, Image.LANCZOS)


def getFrame(frame, width, height):
  # return resizeImage(frame, width, height), frame.info.get("duration", 1000)
  return ImageTk.PhotoImage(resizeImage(frame, width, height)), frame.info.get("duration", 1000)


def fff(result):
  image, duration = result
  return ImageTk.PhotoImage(image), duration


def getAllFramesParallel(image, width, height):
  images = []
  durations = []
  with cf.ThreadPoolExecutor() as ex:  # OK
    func = functools.partial(getFrame, width=width, height=height)
    results = ex.map(func, ImageSequence.all_frames(image))
    for img, duration in results:
      images.append(img)
      durations.append(duration)
  return images, durations


def getAllFrames(image, width, height):
  images = []
  durations = []
  for frame in ImageSequence.all_frames(image):
    images.append(ImageTk.PhotoImage(resizeImage(frame, width, height)))
    durations.append(frame.info.get("duration", 1000))
  return images, durations


def getOrientation(size):
  return LandScape if size[0] >= size[1] else Portrait


def getSubWindowIndex(resolutions, orientation):
  for i, (_, _, o) in enumerate(resolutions):
    if orientation == o:
      return i
  return 0


def openImage(path, resolutions):
  image = Image.open(path)
  size = image.size
  index = getSubWindowIndex(resolutions, getOrientation(size))
  images, durations = getAllFramesParallel(image, resolutions[index][0], resolutions[index][1])
  return {
    "path": path,
    "images": images,
    "durations": durations,
    "originalSize": size,
    "subWindow": index,
  }

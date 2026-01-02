import concurrent.futures as cf
import functools
import operator
import re
from collections import deque

from PIL import Image, ImageSequence, ImageTk

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
  result.sort(key=operator.itemgetter("path"))
  return result


def resizeImage(image, width, height):
  w, h = image.size
  ratio = min(width / w, height / h)
  size = (int(w * ratio), int(h * ratio))
  return image.resize(size, Image.LANCZOS)


def getFrame(frame, width, height):
  return ImageTk.PhotoImage(resizeImage(frame, width, height)), frame.info.get("duration", 1000)


def getAllFrames(image, width, height):
  images = []
  durations = []
  with cf.ThreadPoolExecutor() as ex:  # OK
    func = functools.partial(getFrame, width=width, height=height)
    results = ex.map(func, ImageSequence.all_frames(image), timeout=60)
    for img, duration in results:
      images.append(img)
      durations.append(duration)
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
  images, durations = getAllFrames(image, resolutions[index][0], resolutions[index][1])
  return {
    "path": path,
    "images": images,
    "durations": durations,
    "originalSize": size,
    "subWindow": index,
  }


def subPaths(path1, path2):
  pattern = re.sub(r"\\", r"\\\\", str(path1))
  return re.sub(rf"{pattern}", ".", rf"{path2}")

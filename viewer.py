import argparse
import pathlib
import re
import threading
import tkinter as tk
import uuid
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from tkinter import ttk

import cv2
import pyperclip
import Utility as U
from PIL import Image, ImageSequence, ImageTk


def toGeometry(width, height, left, top):
  return f"{width}x{height}+{left}+{top}"


def fromGeometry(geometry):
  m = re.match(r"(?P<width>\d+)x(?P<height>\d+)\+(?P<left>\d+)\+(?P<top>\d+)", geometry)
  if m is not None:
    return (int(m["width"]), int(m["height"]), int(m["left"]), int(m["top"]))
  return (0, 0, 0, 0)


def resizeImage(image, width, height):
  w, h = image.size
  ratio = min(width / w, height / h)
  size = (int(w * ratio), int(h * ratio))
  return image.resize(size, Image.LANCZOS)


def convertColor(image):
  if len(image.shape) < 3:
    return image
  if image.shape[2] == 3:
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
  return cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA)


class SubWindow(tk.Toplevel):
  def __init__(self, master=None, title="", geometry="0x0+0+0"):
    super().__init__(master)
    self.image = None
    self.sequence = []
    self.durations = []
    self.text = ""
    self.animationId = 0
    self.geometryData = fromGeometry(geometry)
    self.title(title)
    self.geometry(geometry)
    self.wm_overrideredirect(True)
    self.canvas = tk.Canvas(self)
    self.canvas.configure(width=self.geometryData[0], height=self.geometryData[1], bg="gray")
    self.canvas.pack()

  def checkImages(self, images, durations, text):
    n = len(images)
    self.clearCanvas()
    if n == 1:
      self.sequence = []
      self.durations = []
      self.drawImage(images[0])
      self.drawText(text)
    else:
      self.sequence = images
      self.durations = durations
      self.animationId += 1
      self.animation(0, self.animationId, text)

  def drawImage(self, image):
    self.image = image
    self.canvas.create_image(self.geometryData[0] // 2, self.geometryData[1] // 2, image=self.image, anchor=tk.CENTER)

  def animation(self, index, aid, text):
    end = len(self.sequence)
    if end == 0 or aid != self.animationId:
      return
    i = index if index < end else 0
    self.image = self.sequence[i]
    self.canvas.create_image(self.geometryData[0] // 2, self.geometryData[1] // 2, image=self.image, anchor=tk.CENTER)
    self.drawText(text)
    self.canvas.after(self.durations[i], self.animation, i + 1, aid, text)

  def liftTop(self):
    self.attributes("-topmost", True)
    self.attributes("-topmost", False)

  def clearCanvas(self):
    self.canvas.delete("all")

  def drawText(self, text):
    if text == "":
      return
    self.text = text
    self.canvas.create_text(self.geometryData[0] // 2, 20, text=self.text, fill="red", font=("", 20), anchor=tk.CENTER)


class Viewer(tk.Frame):
  Extensions = (
    ".jpg",
    ".webp",
    ".png",
    ".gif",
  )
  LandScape = "landscape"
  Portrait = "portrait"

  def __init__(self, master, directory, isRecurse, isKeepMemory):
    super().__init__(master)
    self.subWindows = []
    self.resolutions = []
    self.directory = directory
    self.isRecurse = isRecurse
    self.isKeepMemory = isKeepMemory
    self.files = []  # {"path":, "image":, "orientation":, "originalSize"}
    self.current = 0
    self.end = 0
    self.isPrint = False
    self.master.title("Viewer")
    self.master.resizable(True, False)

    self.setLabel()
    self.getResolutions()
    self.master.geometry(f"{self.resolutions[0][0] // 2}x35+0+0")
    self.createSubWindows()
    self.setBinds()
    self.getFiles()
    self.drawImage()
    self.pack()
    self.liftTop()

  def setLabel(self):
    self.labelText = tk.StringVar(value=" ")
    self.label = ttk.Label(
      self,
      textvariable=self.labelText,
      anchor=tk.CENTER,
      font=(None, 16),
      width=256,
      foreground="white",
      background="black",
      relief="groove",
      padding=[5, 5, 5, 5],
    )
    self.label.pack()

  def getResolutions(self):
    for width, height in U.getDisplaysResolution():
      if width >= height:
        self.resolutions.append((width, height, Viewer.LandScape))
      else:
        self.resolutions.append((width, height, Viewer.Portrait))

  def liftTop(self):
    self.master.attributes("-topmost", True)
    self.master.attributes("-topmost", False)
    self.focus_set()

  def setBinds(self):
    self.bind_all("<KeyPress-Right>", self.next)
    self.bind_all("<KeyPress-Left>", self.previous)
    self.bind_all("<KeyPress-Up>", self.listTopAll)
    self.bind_all("<KeyPress-Down>", self.withDraw)
    self.bind_all("<KeyPress-Escape>", self.destroyAll)
    self.bind_all("<KeyPress-F12>", self.setPrint)
    self.master.protocol("WM_DELETE_WINDOW", self.callDestroyAll)

  def createSubWindows(self):
    for i, (width, height, _) in enumerate(self.resolutions):
      self.subWindows.append(
        SubWindow(
          self,
          title=f"subWindow{i}",
          geometry=toGeometry(
            width,
            height,
            self.resolutions[i - 1][0] if i != 0 else 0,
            0,
          ),
        ),
      )

  def destroyAll(self, _event):
    for w in self.subWindows:
      w.destroy()
    self.master.destroy()

  def callDestroyAll(self):
    self.destroyAll(None)

  def _getFiles(self, path):
    files = []
    for file in path.iterdir():
      if file.is_file() and file.suffix in Viewer.Extensions:
        files.append({"path": file})
      if file.is_dir() and self.isRecurse:
        files += self._getFiles(file)
    return files

  def getFiles(self):
    self.files = self._getFiles(self.directory)
    self.end = len(self.files)

  def getSubWindowIndex(self, orientation):
    for i, (_, _, o) in enumerate(self.resolutions):
      if orientation == o:
        return i
    return 0

  def updateText(self):
    fileData = self.files[self.current]
    # text = f"{self.current:{len(str(self.end))}} / {self.end}: {fileData['path'].name} [{fileData['originalSize'][0]}, {fileData['originalSize'][1]}{fileData['images'][0].size}]"
    text = f"{self.current + 1:{len(str(self.end))}} / {self.end}: {fileData['path'].name} [{fileData['originalSize'][0]}, {fileData['originalSize'][1]}({fileData['images'][0].width()}, {fileData['images'][0].height()})]"
    self.labelText.set(text)
    # print("\r\x1b[1M" + text, end="")
    return text

  def getImageFromFrame(self, frame):
    image = Image.fromarray(convertColor(frame))  # 画像が劣化する事がある。
    image = resizeImage(image, self.resolutions)
    return ImageTk.PhotoImage(image)

  def getOrientation(self, size):
    return Viewer.LandScape if size[0] >= size[1] else Viewer.Portrait

  def openImage(self):  # この処理を速くしたい
    path = self.files[self.current]["path"]
    image = Image.open(path)
    images = []
    durations = []
    size = image.size
    orientation = self.getOrientation(size)
    index = self.getSubWindowIndex(orientation)
    for frame in ImageSequence.all_frames(image):
      image = resizeImage(frame, self.resolutions[index][0], self.resolutions[index][1])
      image = ImageTk.PhotoImage(image)
      images.append(image)
      durations.append(frame.info.get("duration", 0))

    return {
      "path": path,
      "images": images,
      "duration": durations,
      "orientation": orientation,
      "originalSize": size,
    }

  def drawImage(self):
    fileData = self.files[self.current]
    if fileData.get("images", None) is None:
      fileData = self.openImage()
      self.files[self.current] = fileData
    i = self.getSubWindowIndex(fileData["orientation"])
    text = self.updateText()
    if not self.isPrint:
      text = ""
    self.subWindows[i].checkImages(fileData["images"], fileData["duration"], text)
    self.subWindows[i].liftTop()
    print(f"{fileData['path'].name}: {len(fileData['images'])}, {sum(fileData['duration'])}")
    if not self.isKeepMemory:
      self.files[self.current] = {"path": self.files[self.current]["path"]}

  def listTopAll(self, _event):
    for subWindow in self.subWindows:
      subWindow.deiconify()
      subWindow.liftTop()

  def withDraw(self, _event):
    for subWindow in self.subWindows:
      subWindow.withdraw()
    self.liftTop()

  def next(self, _event):
    if self.current < self.end - 1:
      self.current += 1
    else:
      self.current = 0
    self.drawImage()

  def previous(self, _event):
    if self.current > 0:
      self.current -= 1
    else:
      self.current = self.end - 1
    self.drawImage()

  def setPrint(self, _event):
    self.isPrint = not self.isPrint


def argumentParser():
  parser = argparse.ArgumentParser()
  group = parser.add_mutually_exclusive_group(required=True)
  group.add_argument("-i", "--directory", dest="directory", type=pathlib.Path)
  group.add_argument("-c", "--clipboard", action="store_const", const="<clipboard>", dest="directory")
  parser.set_defaults(directory=".")
  parser.add_argument("-r", "--recurse", action="store_true")
  parser.add_argument("-k", "--keepMemory", action="store_true")

  args = parser.parse_args()
  if args.directory == "<clipboard>":
    path = pyperclip.paste()  # 稀に取得できない
    path = path.strip('"')
    args.directory = pathlib.Path(path)
  return args


if __name__ == "__main__":
  args = argumentParser()
  root = tk.Tk()
  viewer = Viewer(root, args.directory, args.recurse, args.keepMemory)
  viewer.mainloop()

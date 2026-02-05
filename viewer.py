import argparse
import concurrent.futures as cf
import pathlib
import tkinter as tk
from threading import Lock
from tkinter import ttk

import Decorator as D
import pyperclip
import WindowsApi as WinApi

import functions as f

ThreadExecutor = cf.ThreadPoolExecutor()


class SubWindow(tk.Toplevel):
  def __init__(self, master=None, title="", geometry="0x0+0+0"):
    super().__init__(master)
    self.image = None
    self.sequence = []
    self.durations = []
    self.text = ""
    self.animationId = 0
    self.geometryData = f.fromGeometry(geometry)
    self.center = (self.geometryData[0] // 2, self.geometryData[1] // 2)
    self.title(title)
    self.geometry(geometry)
    self.wm_overrideredirect(True)
    self.canvas = tk.Canvas(self, highlightthickness=0)
    self.canvas.configure(width=self.geometryData[0], height=self.geometryData[1], bg="gray")
    self.canvas.pack()
    self.imageId = self.canvas.create_image(*self.center, image=None, anchor=tk.CENTER)
    self.textId = self.canvas.create_text(
      10,
      20,
      text=self.text,
      fill="magenta",
      font=("TkFixedFont", 16, "bold"),
      anchor=tk.NW,
    )

  def checkImages(self, images, durations, text):
    if len(images) == 1:
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
    self.canvas.itemconfig(self.imageId, image=self.image)

  def animation(self, index, aid, text):
    end = len(self.sequence)
    if end == 0 or aid != self.animationId:
      return
    i = index if index < end else 0
    self.image = self.sequence[i]
    self.canvas.itemconfig(self.imageId, image=self.image)
    self.drawText(text)
    self.canvas.after(self.durations[i], self.animation, i + 1, aid, text)

  def liftTop(self):
    self.attributes("-topmost", True)
    self.attributes("-topmost", False)

  def drawText(self, text):
    if text == self.text:
      return
    self.text = text
    self.canvas.itemconfig(self.textId, text=self.text)


class Viewer(tk.Frame):
  Extensions = (
    ".jpg",
    ".webp",
    ".png",
    ".gif",
  )
  EventFinishGetFiles = "<<FinishGetFiles>>"

  def __init__(self, master, directory, isRecurse, isKeepMemory):
    super().__init__(master)
    self.subWindows = []
    self.resolutions = []
    self.directory = directory
    self.isRecurse = isRecurse
    self.isKeepMemory = isKeepMemory
    self.files = []  # {"path":, "images":, "durations":, "originalSize":, "subWindow":}
    self.current = -1
    self.end = 0
    self.isPrint = False
    self.directoryIndices = []
    self.lockData = Lock()
    self.lockTask = Lock()
    self.rotateOld = {"index": -1, "angle": 0}
    self.master.title("Viewer")
    self.master.resizable(True, False)

    self.setLabel()
    self.getResolutions()
    self.master.geometry(f"{self.resolutions[0][0] // 2}x78+0+0")
    self.createSubWindows()
    self.setBinds()
    self.getFiles()
    self.pack()
    self.liftTop()

    self.taskQueue = []

  def setLabel(self):
    self.labelText = tk.StringVar(value="\n\n")
    self.label = ttk.Label(
      self,
      textvariable=self.labelText,
      anchor=tk.CENTER,
      font=("TkFixedFont", 16),
      width=256,
      justify="center",
      foreground="white",
      background="black",
      relief="groove",
      padding=[5, 5, 5, 5],
    )
    self.label.pack()

  def getResolutions(self):
    for width, height in WinApi.getDisplaysResolution():
      if width >= height:
        self.resolutions.append((width, height, f.LandScape))
      else:
        self.resolutions.append((width, height, f.Portrait))

  def liftTop(self):
    self.master.attributes("-topmost", True)
    self.master.attributes("-topmost", False)
    self.focus_set()

  def setBinds(self):
    self.bind_all("<KeyPress-Right>", lambda event: self.next(event, 1))
    self.bind_all("<KeyPress-2>", lambda event: self.jump(event, "start"))
    self.bind_all("<KeyPress-5>", lambda event: self.jump(event, "middle"))
    self.bind_all("<KeyPress-8>", lambda event: self.jump(event, "end"))
    self.bind_all("<KeyPress-3>", lambda event: self.next(event, 10))
    self.bind_all("<KeyPress-6>", lambda event: self.next(event, 100))
    self.bind_all("<KeyPress-9>", lambda event: self.next(event, 1000))
    self.bind_all(Viewer.EventFinishGetFiles, lambda event: self.next(event, 1))
    self.bind_all("<KeyPress-Left>", lambda event: self.previous(event, 1))
    self.bind_all("<KeyPress-1>", lambda event: self.previous(event, 10))
    self.bind_all("<KeyPress-4>", lambda event: self.previous(event, 100))
    self.bind_all("<KeyPress-7>", lambda event: self.previous(event, 1000))
    self.bind_all("<KeyPress-Up>", self.listTopAll)
    self.bind_all("<KeyPress-Down>", self.withDraw)
    self.bind_all("<KeyPress-Escape>", self.destroyAll)
    self.bind_all("<KeyPress-F12>", self.setPrint)
    self.bind_all("<KeyPress-Next>", self.jumpDirectoryNext)
    self.bind_all("<KeyPress-Prior>", self.jumpDirectoryPrevious)
    self.bind_all("<KeyPress-r>", self.rotateImage)
    # self.bind_all("<Key>", self.debug)
    self.master.protocol("WM_DELETE_WINDOW", self.callDestroyAll)

  def createSubWindows(self):
    for i, (width, height, _) in enumerate(self.resolutions):
      self.subWindows.append(
        SubWindow(
          self,
          title=f"subWindow{i}",
          geometry=f.toGeometry(
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

  def setDirectoryIndices(self):
    old = ""
    self.directoryIndices = []
    for i, x in enumerate(self.files):
      parent = x["path"].parent
      if str(parent) != old:
        old = str(parent)
        self.directoryIndices.append(i)

  def setFiles(self, future):
    self.files = future.result()
    self.end = len(self.files)
    # self.labelText.set(f"{self.directory}: {self.end}\n\n")
    self.setDirectoryIndices()
    self.event_generate(Viewer.EventFinishGetFiles)

  def getFiles(self):
    ft = ThreadExecutor.submit(f.getFiles, self.directory, self.isRecurse, Viewer.Extensions)
    ft.add_done_callback(self.setFiles)

  def updateText(self, data):
    relativeName = pathlib.Path(f.subPaths(self.directory.absolute(), data["path"]))
    text = f"{self.current + 1:0{len(str(self.end))}} / {self.end}\n"
    text += f"{relativeName.parent}\n"
    text += f"{relativeName.name} "
    text += f"[{data['originalSize'][0]}, {data['originalSize'][1]}"
    text += f"({data['images'][0].width()}, {data['images'][0].height()})]"
    self.labelText.set(text)
    # print("\r\x1b[1M" + text, end="")
    if not self.isPrint:
      return ""
    return text

  @D.printFuncInfo()
  def drawImage(self, data):
    n = data["subWindow"]
    text = self.updateText(data)
    self.subWindows[n].checkImages(data["images"], data["durations"], text)
    self.subWindows[n].liftTop()

  @D.printFuncInfo()
  def getFileData(self, i, angle=0):
    data = self.files[i]
    if self.files[i].get("images", None) is None:
      data = f.openImage(self.files[i]["path"], self.resolutions, angle)
      if self.isKeepMemory:
        with self.lockData:
          self.files[i] = data
    self.drawImage(data)

  def listTopAll(self, _event):
    for subWindow in self.subWindows:
      subWindow.deiconify()
      subWindow.liftTop()

  def withDraw(self, _event):
    for subWindow in self.subWindows:
      subWindow.withdraw()
    self.liftTop()

  def caller(self, angle=0):
    with self.lockTask:
      future = ThreadExecutor.submit(self.getFileData, self.taskQueue[-1], angle)
      future.result(timeout=60)
      self.taskQueue = []

  def next(self, _event, n):
    if self.end < 1:
      return
    self.current += n
    while self.current >= self.end:
      self.current -= self.end
    self.taskQueue.append(self.current)
    ThreadExecutor.submit(self.caller)

  def previous(self, _event, n):
    if self.end < 1:
      return
    self.current -= n
    while self.current < 0:
      self.current += self.end
    self.taskQueue.append(self.current)
    ThreadExecutor.submit(self.caller)

  def jump(self, _event, pos):
    if self.end < 1:
      return
    if pos == "start":
      self.current = 0
    elif pos == "end":
      self.current = self.end - 1
    else:
      self.current = self.end // 2
    self.taskQueue.append(self.current)
    ThreadExecutor.submit(self.caller)

  def setPrint(self, _event):
    self.isPrint = not self.isPrint

  def jumpDirectoryNext(self, _envent):
    n = len(self.directoryIndices)
    for i in range(n):
      if i != n - 1 and self.current >= self.directoryIndices[i] and self.current < self.directoryIndices[i + 1]:
        self.current = self.directoryIndices[i + 1]
        break
      if i == n - 1:
        self.current = 0  # self.directoryIndices[0]
    self.taskQueue.append(self.current)
    ThreadExecutor.submit(self.caller)

  def jumpDirectoryPrevious(self, _envent):
    n = len(self.directoryIndices)
    for i in range(n - 1, -1, -1):
      if i != 0 and self.current <= self.directoryIndices[i] and self.current > self.directoryIndices[i - 1]:
        self.current = self.directoryIndices[i - 1]
        break
      if i == 0:
        self.current = self.directoryIndices[-1]
    self.taskQueue.append(self.current)
    ThreadExecutor.submit(self.caller)

  def rotateImage(self, _event):  # 回転を保持し続けるか?
    if self.files[self.current].get("images", None) is not None:
      self.files[self.current]["images"] = None
    angle = 180
    if self.rotateOld["index"] == self.current:
      angle = 180 if self.rotateOld["angle"] == 0 else 0
    self.rotateOld = {"index": self.current, "angle": angle}
    self.taskQueue.append(self.current)
    ThreadExecutor.submit(self.caller, angle)


# def debug(self, event):
#   print(event)
#   print(f"Keysym: {event.keysym}, Keycode: {event.keycode}")


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
    path = pyperclip.paste()  # 稀に取得できない?
    path = path.strip('"')
    args.directory = pathlib.Path(path)
  return args


if __name__ == "__main__":
  args = argumentParser()
  root = tk.Tk()
  viewer = Viewer(root, args.directory, args.recurse, args.keepMemory)
  viewer.mainloop()

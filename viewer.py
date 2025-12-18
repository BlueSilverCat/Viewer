import argparse
import pathlib
import re
import tkinter as tk
from tkinter import ttk

import Utility as U
from PIL import Image, ImageTk


def toGeometry(width, height, left, top):
  return f"{width}x{height}+{left}+{top}"


def fromGeometry(geometry):
  m = re.match(r"(?P<width>\d+)x(?P<height>\d+)\+(?P<left>\d+)\+(?P<top>\d+)", geometry)
  if m is not None:
    return (int(m["width"]), int(m["height"]), int(m["left"]), int(m["top"]))
  return (0, 0, 0, 0)


def resize(image, width, height):
  w, h = image.size
  ratio = width / w if width <= height else height / h
  size = (int(w * ratio), int(h * ratio))
  return image.resize(size, Image.LANCZOS)


def getFiles(path, extensions=None, *, isRecuse=False):
  files = []
  for file in path.iterdir():
    if file.is_file() and (extensions is None or file.suffix in extensions):
      files.append(file)
    if file.is_dir() and isRecuse:
      files += getFiles(file, extensions, isRecuse=isRecuse)
  return files


class SubWindow(tk.Toplevel):
  def __init__(self, master=None, title="", geometry="0x0+0+0"):
    super().__init__(master)
    self.image = None
    self.text = None
    self.oldId = None
    self.info = fromGeometry(geometry)
    self.title(title)
    self.geometry(geometry)
    self.wm_overrideredirect(True)
    self.canvas = tk.Canvas(self)
    self.canvas.configure(width=self.info[0], height=self.info[1], bg="gray")
    self.canvas.pack()

  def setImage(self, image):
    self.image = ImageTk.PhotoImage(image)
    self.canvas.create_image(self.info[0] // 2, self.info[1] // 2, image=self.image, anchor=tk.CENTER)

  def liftTop(self):
    self.attributes("-topmost", True)
    self.attributes("-topmost", False)

  def deleteOldText(self):
    if self.oldId is not None:
      self.canvas.delete(self.oldId)

  def setText(self, text):
    self.text = text
    self.deleteOldText()
    self.oldId = self.canvas.create_text(
      self.info[0] // 2, 20, text=self.text, fill="red", font=("", 20), anchor=tk.CENTER
    )


class Viewer(tk.Frame):
  Extensions = (
    ".jpg",
    ".webp",
    ".png",
  )

  def __init__(self, directory, isRecurse, master=None):
    super().__init__(master)
    self.root = root
    self.subWindows = []
    self.resolutions = []
    self.orientations = []
    self.directory = directory
    self.isRecurse = isRecurse
    self.files = []
    self.current = 0
    self.end = 0
    self.isPrint = False
    self.root.title("Viewer")
    self.root.resizable(True, False)

    self.setLabel()
    self.getResolutions()
    self.root.geometry(f"{self.resolutions[0][0] // 2}x35+0+0")
    self.getFiles()
    self.createSubWindows()
    self.setBinds()
    self.openImage()
    self.pack()
    self.liftTop()

  def setLabel(self):
    self.labelText = tk.StringVar(value="test")
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
    self.resolutions = U.getDisplaysResolution()
    self.orientations = ["landscape" if width >= height else "portrait" for width, height in self.resolutions]

  def liftTop(self):
    self.root.attributes("-topmost", True)
    self.root.attributes("-topmost", False)
    self.focus_set()

  def setBinds(self):
    self.bind_all("<KeyPress-Right>", self.next)
    self.bind_all("<KeyPress-Left>", self.previous)
    self.bind_all("<KeyPress-Up>", self.listTopAll)
    self.bind_all("<KeyPress-Down>", self.withDraw)
    self.bind_all("<KeyPress-Escape>", self.destroyAll)
    self.bind_all("<KeyPress-F12>", self.setPrint)

  def createSubWindows(self):
    for i, r in enumerate(self.resolutions):
      self.subWindows.append(
        SubWindow(
          self,
          title=f"subWindow{i}",
          geometry=toGeometry(
            r[0],
            r[1],
            self.resolutions[i - 1][0] if i != 0 else 0,
            0,
          ),
        ),
      )

  def destroyAll(self, _event):
    for w in self.subWindows:
      w.destroy()
    self.root.destroy()

  def getFiles(self):
    self.files = getFiles(self.directory, Viewer.Extensions, isRecuse=self.isRecurse)
    self.end = len(self.files)

  def updateText(self, i, size, resized):
    text = f"{self.current:{len(str(self.end))}} / {self.end}: {self.files[self.current].name} [{size[0]}, {size[1]}{resized}]"
    self.labelText.set(text)
    # print("\r\x1b[1M" + text, end="")
    if self.isPrint:
      self.subWindows[i].setText(text)

  def resize(self, image):
    w, h = image.size
    o = "landscape" if w >= h else "portrait"
    i = U.indexList(self.orientations, o, 0)
    image = resize(image, *self.resolutions[i])
    return (i, image, (w, h), image.size)

  def openImage(self):
    image = Image.open(self.files[self.current])
    (i, image, size, resized) = self.resize(image)
    self.subWindows[i].setImage(image)
    self.updateText(i, size, resized)
    self.subWindows[i].liftTop()

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
    self.openImage()

  def previous(self, _event):
    if self.current > 0:
      self.current -= 1
    else:
      self.current = self.end - 1
    self.openImage()

  def setPrint(self, _event):
    self.isPrint = not self.isPrint
    if not self.isPrint:
      for subWindow in self.subWindows:
        subWindow.deleteOldText()


def argumentParser():
  parser = argparse.ArgumentParser()
  parser.add_argument("directory", type=pathlib.Path)
  parser.add_argument("-r", "--recurse", action="store_true")
  args = parser.parse_args()
  return args.directory, args.recurse


if __name__ == "__main__":
  directory, isRecurse = argumentParser()
  root = tk.Tk()
  viewer = Viewer(directory, isRecurse, root)
  viewer.mainloop()

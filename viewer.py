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
  ratio = min(width / w, height / h)
  size = (int(w * ratio), int(h * ratio))
  return image.resize(size, Image.LANCZOS)


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

  def __init__(self, master, directory, isRecurse, isKeepMemory):
    super().__init__(master)
    self.root = root
    self.subWindows = []
    self.resolutions = []  # ディスプレイが2つ固定ならばもっと単純になる。
    self.orientations = []
    self.directory = directory
    self.isRecurse = isRecurse
    self.isKeepMemory = isKeepMemory
    self.files = []  # {"path":, "image":, "orientation":, "originalSize"}
    self.current = 0
    self.end = 0
    self.isPrint = False
    self.root.title("Viewer")
    self.root.resizable(True, False)

    self.setLabel()
    self.getResolutions()
    self.root.geometry(f"{self.resolutions[0][0] // 2}x35+0+0")
    self.createSubWindows()
    self.setBinds()
    self.getFiles()
    self.drawImage()
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
    for i, o in enumerate(self.orientations):
      if o == orientation:
        return i
    return 0

  def updateText(self):
    fileData = self.files[self.current]
    text = f"{self.current:{len(str(self.end))}} / {self.end}: {fileData['path'].name} [{fileData['originalSize'][0]}, {fileData['originalSize'][1]}{fileData['image'].size}]"
    self.labelText.set(text)
    # print("\r\x1b[1M" + text, end="")
    if self.isPrint:
      i = self.getSubWindowIndex(fileData["orientation"])
      self.subWindows[i].setText(text)

  def openImage(self):
    image = Image.open(self.files[self.current]["path"])
    w, h = image.size
    o = "landscape" if w >= h else "portrait"
    i = self.getSubWindowIndex(o)
    image = resize(image, *self.resolutions[i])  # PhotoImageで保存しておくと、古い画像が残ってしまう
    return {
      "path": self.files[self.current]["path"],
      "image": image,
      "orientation": o,
      "originalSize": (w, h),
    }

  def drawImage(self):
    fileData = self.files[self.current]
    if fileData.get("image", None) is None:
      fileData = self.openImage()
      self.files[self.current] = fileData
    i = self.getSubWindowIndex(fileData["orientation"])
    self.subWindows[i].setImage(fileData["image"])
    self.updateText()
    self.subWindows[i].liftTop()

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
    if not self.isPrint:
      for subWindow in self.subWindows:
        subWindow.deleteOldText()


def argumentParser():
  parser = argparse.ArgumentParser()
  parser.add_argument("directory", type=pathlib.Path)
  parser.add_argument("-r", "--recurse", action="store_true")
  parser.add_argument("-k", "--keepMemory", action="store_true")
  return parser.parse_args()


if __name__ == "__main__":
  args = argumentParser()
  root = tk.Tk()
  viewer = Viewer(root, args.directory, args.recurse, args.keepMemory)
  viewer.mainloop()

import datetime
import functools
import gc
import random
import re
import threading
import time


def getRandomInt(minN, maxN):
  return random.randrange(minN, maxN)


def getRandomStr(string="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWSVZ0123456789", rMin=1, rMax=10):
  return "".join(random.choices(string, k=random.randint(rMin, rMax)))


def getRandomData():
  return [(getRandomStr(rMin=10, rMax=12), getRandomInt(5, 8)) for _ in range(10)]


def getNowTime(fmt="%H:%M:%S.%f"):
  return datetime.datetime.now().strftime(fmt)


def printTime(*args):
  print(f"{getNowTime()}:", *args)


def strKargs(kwargs):
  return "".join([f"{k}={v}, " for k, v in kwargs.items()])[:-1]


def printThreadInfo():
  print(f"threading.current_thread: {threading.current_thread()}")
  print(f"threading.main_thread: {threading.main_thread()}")
  print(f"threading.active_count: {threading.active_count()}")


def printFuncInfo(
  isPrintStart=True,
  isPrinteEnd=True,
  isPrintName=True,
  nameWidth=20,
  isPrintArgs=False,
  isPrintExecTime=True,
  FormatExecTime="10.6f",
  isPrintResult=False,
):
  def printFuncInfoWrapper(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
      name = f"{func.__name__:{nameWidth}}" if isPrintName else ""
      argsStr = f"{args}, {strKargs(kwargs)}" if isPrintArgs else ""
      if isPrintStart:
        print(f"{getNowTime()}: Start    {name} {argsStr}")
      gc.collect()
      gc.disable()
      start = time.perf_counter()
      result = func(*args, **kwargs)
      end = time.perf_counter()
      diff = end - start
      execTime = f"{diff:{FormatExecTime}}" if isPrintExecTime else ""
      resultStr = f"{result}" if isPrintResult else ""
      if isPrinteEnd:
        print(f"{getNowTime()}:      End {name} {execTime} {resultStr}")
      gc.enable()
      return result

    return wrapper

  return printFuncInfoWrapper


def wrapsplitStrNum(func):
  @functools.wraps(func)
  def wrapper(*args, **kwargs):
    return splitStrNum(func(*args, **kwargs))

  return wrapper


def splitStrNum(s):
  return [int(c) if c.isdecimal() else c for c in re.split(r"(\d+)", s)]


def naturalSorted(lt, *, key=None, reverse=False):
  if key is None:
    return sorted(lt, key=splitStrNum, reverse=reverse)
  return sorted(lt, key=wrapsplitStrNum(key), reverse=reverse)


def naturalSort(lt, *, key=None, reverse=False):
  if key is None:
    lt.sort(key=splitStrNum, reverse=reverse)
  lt.sort(key=wrapsplitStrNum(key), reverse=reverse)

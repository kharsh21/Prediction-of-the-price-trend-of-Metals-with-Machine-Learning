import os

LOG_FILE = "log.txt"

# log into file
def log(text):
  f = open(LOG_FILE, "a")
  f.write(text + "\n")
  f.close()

def removeLogFile():
  try:
    os.remove(LOG_FILE)
  except FileNotFoundError:
    pass

import time
import os
import psutil
import subprocess

keepAliveFilesPath = "./"

# Call this periodically in the supervised process.
def iAmAlive(scriptPath):
  scriptName = os.path.basename(scriptPath)
  f = open(keepAliveFilesPath + scriptName + ".watchdog","w")
  f.write("x")
  f.close()

# Call this periodically in the supervising process.
# If iAmAlive() was not called within the last intervalSeconds seconds then the script is (re-)started.
def restartOnDeath(scriptPath, intervalSeconds):
  scriptName = os.path.basename(scriptPath)
  # check if supervised process gave a sign of live recently
  try:
    modificationTime = os.path.getmtime(keepAliveFilesPath + scriptName)
  except os.error:
    modificationTime = 0
  if (modificationTime + intervalSeconds) < time.time():
    # process hangs => kill it
    for proc in psutil.process_iter():
      if len(proc.cmdline()) > 1:
        script = os.path.basename(proc.cmdline()[1])
        if scriptName == script:
          proc.kill()
          time.sleep(1)
          break
    # restart
    subprocess.call("python3 " + scriptPath, shell=True)

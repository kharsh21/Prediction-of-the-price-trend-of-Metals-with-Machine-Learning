import os
from log import log
from instruments import instruments
import datetime as dt

#path_to_model_export='/storage/candles/Model_export/'
#path_to_akt_image='/storage/candles/akt_candles/'
path_to_model_export = ("./models08", "./models10")
path_to_akt_image = ("./images08", "./images10")

# get a file-system-friendly representation of the instrument's name
def instrumentFileName(instrument):
  return instrument.replace("/", "_")

def modelFileName(instrument):
  return instrumentFileName(instrument) + '_RN34_' + str(instruments[instrument]['days']) + 'd_Model_export_1.pkl'
# e.g. 'EUR_GBP_RN34_56d_Model_export_1.pkl'

def imageFileName(instrument, date):
  return instrumentFileName(instrument) + '_' + str(instruments[instrument]['days']) + '_' + date.strftime('%Y-%m-%d') + '.png'
# e.g. 'EUR_GBP_56_2019-12-19.png'

def imagePath(date, MODEL):
  return path_to_akt_image[MODEL] + '/' + date.strftime("%Y-%m-%d")

def normalizedImagePath(date, MODEL):
#  return path_to_akt_image[MODEL] + '/' + date.strftime("%Y-%m-%d") + '_n'
  return path_to_akt_image[MODEL] + '/' + date.strftime("%Y-%m-%d")

def imageFilePath(instrument, date, MODEL):
  return imagePath(date, MODEL) + '/' + imageFileName(instrument, date)

def normalizedImageFilePath(instrument, date, MODEL):
  return normalizedImagePath(date, MODEL) + '/' + imageFileName(instrument, date)

def createPath(path):
  try:
    os.makedirs(path)
    log("created path " + path)
  except FileExistsError:
    pass # path already existed

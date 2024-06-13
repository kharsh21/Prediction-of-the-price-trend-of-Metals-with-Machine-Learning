#%reload_ext autoreload
#%autoreload 2
#%matplotlib inline

# If you haven't installed orca yet, you can do so using conda as follows:
#    $ conda install -c plotly plotly-orca
# ----------------------
# To check if orca is running
# pio.orca.status
# ----------------------
# https://plot.ly/python/orca-management/

#!conda install -c plotly plotly-orca

#!pip3 install plotly
#!pip3 install psutil
#!pip3 install Xvfb

#!pip3 install plotly
#!pip3 install psutil
#!sudo apt-get install -y xvfb  for server only! see https://github.com/plotly/orca!
#!pip3 install fastai
#!pip3 install ipython
#uninstall orca (a screen reader)
#see https://github.com/plotly/orca, standalone binary
#sudo apt install libcanberra-gtk-module libcanberra-gtk3-module

import plotly.graph_objects as go
import pandas as pd
import datetime as dt
import pytz
import fxcmpy
import numpy as np
import plotly.io as pio
from IPython.display import SVG, display
import pandas as pd
import fastai.vision
from log import log
import files
from trading_day import TIMEZONE, UTC_TIMEZONE, tradingDayStartUtc
from instruments import instruments
import os

pio.orca.config.use_xvfb = True

#pio.orca.config.executable='/opt/conda/envs/fastai/lib/orca_app/orca'
#pio.orca.config.executable = '/usr/bin/orca'
#pio.orca.config.executable = '/usr/local/bin/orca'
#pio.orca.config.executable = '/home/eckart/anaconda3/bin/orca'
pio.orca.config.executable = '/home/eckart/.local/bin/orca'

def Normalize_images_path(source_image_path, source_image_name, target_image_path, target_image_name):
  fnames = [source_image_name, source_image_name]
  num_files = 2
  filenames=pd.DataFrame(fnames, columns=['fname'])
  filenames['label']=['0']*num_files
  data = fastai.vision.ImageDataBunch.from_df(source_image_path, filenames, valid_pct=0., no_check=True)
  data_norm = data.normalize(fastai.vision.imagenet_stats)
  data_norm.train_ds.x[0].save(target_image_path+'/'+ target_image_name)

# Data Frequency Examples
# The parameter period defines the frequency of the data to be retrieved. 
# minutes: m1, m5, m15 and m30,
# hours: H1, H2, H3, H4, H6 and H8,
# one day: D1,
# one week: W1,
# one month: M1.
# returns True if an image has been created
def Create_Candle(instrument, days, connection, MODEL, pred_day=dt.date.today(), frequency='D1', debug=False, candles=None):
  # check if instrument exist in list\n",
  if instrument not in instruments:
    log('    Instrument %s not known' % instrument)
    return False
  #check if the instrument is traded on the prediction day\n",
  if not pred_day.weekday() in instruments[instrument]['trading_days']:
    log('    %d not a trading weekday for %s' % (pred_day.weekday(), instrument))
    return False
  if(frequency=='D1'):
    timestep=dt.timedelta(days=1)
  else:
    log('    Frequency %s not known' % frequency)
    return False
  filepath = files.normalizedImageFilePath(instrument, pred_day, MODEL)
  if os.path.exists(filepath):
    log("    (normalized) candle image %s exists" % filepath)
    return True
  if debug:
    log('    Prediction day %s, Weekday %d' % (pred_day.strftime('%Y-%m-%d'), pred_day.weekday()))

  #calculate borders of timeframe |
  # akt_start and akt_stop in UTC without timezone information | because get_candles accepts not timezone information
  akt_stop = tradingDayStartUtc(pred_day)
  #akt_stop = akt_stop - dt.timedelta(minutes=30) # prevent getting a candle for pred_day itself (must not include a point in time from that trading day)
  akt_start = akt_stop - dt.timedelta(days=days)
  if debug:
    log('    Calculated [%s, %s]' % (akt_start.strftime('%Y-%m-%d %T %Z (%z)'), akt_stop.strftime('%Y-%m-%d %T %Z (%z)')))

  stop_weekday = akt_stop.astimezone(TIMEZONE).weekday()

  # the fxcm api cannot handle datetime with timezone (sigh...)
  akt_start = akt_start.replace(tzinfo=None)
  akt_stop = akt_stop.replace(tzinfo=None)

  if candles is None:
    try:
      # read candle prices
      candle_values=connection.get_candles(instrument, period=frequency, start=akt_start, stop=akt_stop)
      log(candle_values.to_string())
    except Exception as e:
      log('Wertpapier-Daten können nicht gelesen werden: %s' % e)
      return False
  else:
    candle_values=candles[akt_start.strftime("%Y-%m-%d %T") : akt_stop.strftime("%Y-%m-%d %T")]

  # Check if candle prices are too old
  last_price_date = candle_values.index[-1]
  if last_price_date < akt_stop:
    allowedDiffSecs = 0
    if stop_weekday == 6:
      allowedDiffSecs = 48*3600 # 2 days
    elif stop_weekday == 5:
      allowedDiffSecs = 24*3600 # 1 day
    if (akt_stop - last_price_date).seconds > allowedDiffSecs:
      log('Error: Daily data too old: %s %s' % (instrument, pred_day.strftime("%Y-%m-%d %T")))
      return False

  # Change time, date to New York timezone
  candle_values = candle_values.tz_localize(tz='UTC')
  candle_values = candle_values.tz_convert(tz='US/Eastern')

  # delete rows with Saturday or Sunday data\n",
  candle_values['weekday'] = candle_values.index.dayofweek
  candle_values = candle_values.loc[candle_values['weekday'] < 5]

  # calculate OHLC
  candle_values['open']=(candle_values['bidopen']+candle_values['askopen'])/2
  candle_values['high']=(candle_values['bidhigh']+candle_values['askhigh'])/2
  candle_values['low']=(candle_values['bidlow']+candle_values['asklow'])/2
  candle_values['close']=(candle_values['bidclose']+candle_values['askclose'])/2
  candle_values=candle_values.drop(columns=['bidopen','bidclose','bidhigh', 'bidlow','askopen', 'askclose',
                                            'askhigh', 'asklow','tickqty', 'weekday'])
  # remove duplicates
  candle_values=candle_values.reset_index().drop_duplicates(subset='date',keep='first').set_index('date')

  # select start and stop
  start = candle_values.index[0]
  stop = candle_values.index[-1]

  if debug:
    log('    Delivered  [%s, %s]' % (start.strftime('%Y-%m-%d %T %Z (%z)'), stop.strftime('%Y-%m-%d %T %Z (%z)')))

  fig = go.Figure(data=[go.Candlestick(x=candle_values.index,
                          open=candle_values['open'], high=candle_values['high'],
                          low=candle_values['low'], close=candle_values['close'],
                          opacity=1.0, increasing_line_color= '#0F0', decreasing_line_color= '#F00')
                       ])

  fig.update_layout(xaxis_rangeslider_visible=False,
                    width=224, height=224,
                    showlegend=False, xaxis_visible=False, yaxis_visible=False,
                    paper_bgcolor='#000', plot_bgcolor='#FFF',
                    margin_l=0,margin_r=0, margin_t=0, margin_b=0)

  file_name = files.imageFileName(instrument, pred_day)
  filepath = files.imagePath(pred_day, MODEL) + '/' + file_name
  files.createPath(files.imagePath(pred_day, MODEL))
  if debug:
    log('    %s Timeframe borders : %s | %s' % (filepath, start.strftime('%Y-%m-%d %T %Z (%z)'), stop.strftime('%Y-%m-%d %T %Z (%z)')))
  fig.write_image(filepath)
  log('    created candle image file %s' % filepath)

  # Normalize candles images
  # files.createPath(files.normalizedImagePath(pred_day, MODEL))
  # Normalize_images_path(files.imagePath(pred_day, MODEL), file_name, files.normalizedImagePath(pred_day, MODEL), file_name)

  #closePositionTime = stop + timestep

  return True

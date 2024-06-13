import fxcmpy
import pandas as pd
import datetime as dt
import pytz
import time
import watchdog
import predictor
from PIL import Image
import files
from log import log, LOG_FILE, removeLogFile
from candles import Create_Candle
from instruments import instruments, instrumentList
import os
import traceback
from trading_day import nextTradingDayStart, tradingDayStart, tradingDayEnd, lastTradingDayEnd, TIMEZONE, shiftToEndOfTradingDay
import sys
import math
import fastai.vision

DO_TRADE = 0 # issue trading requests, otherwise just track prices at order execution times
LIVE = 1     # use live servers, otherwise use test servers
CONNECTION_LOG = "./connection.log.txt"
DEBUG = 0
MODEL = 0 # 0 for 0.8% models, 1 for 1% models
MAX_MICRO_LOTS = 1 # max number of lots to trade in one position
MIN_PROBABILITY = 0.55 # signals with lower probability are ignored

POSOPENHOUR = 19
POSOPENMINUTE = 0

if LIVE:
  TOKEN_FILE = "./token_real.txt" # file with connection token
else:
  TOKEN_FILE = "./token_test.txt" # file with connection token

startTime = dt.datetime.now(TIMEZONE)

def nowString():
  return dt.datetime.now(TIMEZONE).strftime('%Y-%m-%d %T %Z (%z)')

# read the connection token from filePath
def readTokenFromFile():
  f = open(TOKEN_FILE, "r")
  token = f.read()
  f.close()
  return token.rstrip(" \t\r\n").strip(" \t\r\n")

def posTypeStr(longPos):
  return "long" if longPos else "short"

def subscribe(connection, instrument):
  if not connection.is_subscribed(instrument):
    connection.subscribe_market_data(instrument)
    log("subscribed %s" % instrument)

# create the candle image file for the current day
def createCandleImageForPredictor(connection, instrument, pred_day=dt.date.today()):
  # Create days directory
  today=pred_day.strftime("%Y-%m-%d")
  files.createPath(files.path_to_akt_image[MODEL]+'/'+today)
  files.createPath(files.path_to_akt_image[MODEL]+'/'+today+'_n')

  imageFilePath = files.normalizedImageFilePath(instrument, pred_day, MODEL)
  if os.path.exists(imageFilePath):
    log("    candle image %s exists" % imageFilePath)
  else:
    Create_Candle(instrument, instruments[instrument]['days'], connection, MODEL, pred_day, debug = True)

def probToString(p):
  return "%d%%" % int(100*p)

# returns String "0", "L", "S", the probability and the list of all probabilities
def predict(instrument, pred_day=dt.date.today()):
  candleImagePath = files.normalizedImageFilePath(instrument, pred_day, MODEL)
  try:
    signal, probabilities = predictor.Do_prediction_from_file(candleImagePath, files.path_to_model_export[MODEL], files.modelFileName(instrument))
    # probabilities is a PyTorch tensor
    probabilities = probabilities.tolist()
    log("    prediction for %s is %s (probabilities %s)" % (instrument, signal, ','.join(map(probToString, probabilities))))
    if signal == "0":
      probability = probabilities[0]
    if signal == "L":
      probability = probabilities[1]
    if signal == "S":
      probability = probabilities[2]
  except FileNotFoundError as e:
    log("    predict() failed: %s %s" % (e.strerror, e.filename))
    return "0", 0.0, []
  return signal, probability, probabilities

# function only used for testing
def Predict_one_day(connection, pred_day=dt.date.today()):
  # Create days directory
  today=pred_day.strftime("%Y-%m-%d")
  files.createPath(files.path_to_akt_image[MODEL]+'/'+today)
  files.createPath(files.path_to_akt_image[MODEL]+'/'+today+'_n')

  # Create Candles
  image_cnt=0
  for instrument in instruments:
    days=instruments[instrument]['days']
    #
    imageFilePath = files.normalizedImageFilePath(instrument, pred_day, MODEL)
    if not os.path.exists(imageFilePath):
      Create_Candle(instrument, days, connection, MODEL, pred_day, debug=True )
    image_cnt +=1

  if image_cnt == len(instruments):
    print('Correct amount of images produced'+'\\n')
  else:
    print(str(images_cnt)+' images produced from '+str(num_instruments))

  print('Prediction 0.8% for', today)
  filesList = os.listdir(files.path_to_akt_image[MODEL]+'/'+today+'_n')
  for file in filesList:
    print(file)
    if file.endswith('.png'):
      akt_date_split=file.split('_')
      if(len(akt_date_split)==3):
        akt_date=akt_date_split[2]
        instrument=akt_date_split[0]
      else:
        akt_date=akt_date_split[3]
        instrument=akt_date_split[0]+'/'+akt_date_split[1]
      date_components=akt_date.split('.')[0].split('-')
      date=dt.date(int(date_components[0]), int(date_components[1]), int(date_components[2]))
      log(date.strftime("%Y-%m-%d") +' '+ instrument)
      days=instruments[instrument]['days']
      model_fname=files.instrumentFileName(instrument)+'_RN34_'+str(days)+'d_Model_export_1.pkl'
      log(instrument +' '+ file +' '+ files.normalizedImagePath(date, MODEL))
      log(akt_date +' '+ instrument +' '+ str(days) +' '+ files.path_to_model_export[MODEL] +' '+ model_fname)
      signal, probabilities = predictor.Do_prediction_from_file(files.normalizedImageFilePath(instrument, date, MODEL), files.path_to_model_export[MODEL], model_fname)
      log(instrument +' '+ signal +' ('+ str(probabilities.tolist()) +')')

# create a new task
def newTask(instrument, price, orderSuccessful):
  task = {}
  task['instrument'] = instrument
  task['close'] = orderSuccessful # we have an open position that we want to close later
  task['price'] = price
  task['time'] = closeTime(task['instrument'])
  log("  created task: instrument=%s, close=%s, price=%s, time=%s" % (task['instrument'], str(task['close']), str(task['price']), task['time'].strftime('%Y-%m-%d %T %Z (%z)')))
  return task

def convertToEur(connection, currency, value):
  if currency == 'EUR':
    return value
  else:
    exchangeInstrument = 'EUR/' + currency
    subscribe(connection, exchangeInstrument)
    quote = connection.get_last_price(exchangeInstrument)
    return value / (quote.Ask + quote.Bid) * 2

def amountBy1000(a):
  return int(round(a * 1, 0)) # amountK is NOT in 1000's units !!! The unit is microlots. A microlot means 1000 units of currency.

# get the trade price at which the position was opened
def openPositionPriceAndAmount(connection, tradeId):
  for position in connection.get_open_positions(kind='list'):
    if position.tradeId == tradeId:
      return position.open, amountBy1000(position.amountK)
  return 0.0

# get the trade price at which the position was closed
def closePositionPrice(connection, tradeId):
  for position in connection.get_closed_positions(kind='list'):
    if position.tradeId == tradeId:
      return position.close
  return 0.0

# determine the time when to open a position
def openTime(instrument, pred_day):
  if DEBUG:
    return startTime + dt.timedelta(minutes=2)
  else:
    return pred_day.replace(hour=POSOPENHOUR, minute=POSOPENMINUTE, second=0, microsecond=0)

# determine the time when to close a position
def closeTime(instrument):
  if DEBUG:
    return startTime + dt.timedelta(minutes=3)
  else:
    return tradingDayEnd().replace(hour=16, minute=0, second=0, microsecond=0)

def getPipValuePerMicroLotInEur(connection, instrument):
  if 'index' in instruments[instrument]:
    # index or commodity
    pipValuePerContract = instruments[instrument]['index']['pipValue'] * instruments[instrument]['index']['pipPerPoint']
    currency = instruments[instrument]['index']['pipCurrency']
  else:
    # currency pair
    pipValuePerContract = 1000 * instruments[instrument]['pip'] # 1 micro-lot = 1000 units
    currencies = instrument.split('/')
    currency = currencies[1]
  return convertToEur(connection, currency, pipValuePerContract)

# determine the size of a position, i.e. how much shall be bought/sold
def calculateQuantity(connection, instrument, isLong):
  # get capital available for margin
  account = connection.get_accounts().T[0]
  capitalToUse = account.usableMargin

  # get the current rate
  subscribe(connection, instrument)
  quote = connection.get_last_price(instrument)
  if isLong:
    price = quote.Ask
  else:
    price = quote.Bid

  lever = 1
  if 'index' in instruments[instrument]:
    # index or commodity
    parts = instrument.split('/')
    if len(parts) == 2:
      # commodity: price is price per unit already
      pricePerContract = price
      baseCurrency = parts[1]
    else:
      # index: price is in points, need to calculate price per contract
      pricePerContract = price * instruments[instrument]['index']['pipValue'] * instruments[instrument]['index']['pipPerPoint']
      baseCurrency = instruments[instrument]['index']['pipCurrency']
  else:
    # the price is the current ratio of currencies: need to convert into price per micro-lot, in EUR
    pricePerContract = price * 1000 # a micro-lot has 1000 units
    baseCurrency = instrument.split('/')[1]
  pricePerContract = convertToEur(connection, baseCurrency, pricePerContract)
  #log("  current price: %s%f -> price per contract EUR%f" % (baseCurrency, price, pricePerContract))

  # limit quantity so that:
  # if price-rate worsens by 1%, that results in lever% loss of (total) capital
  lever = pricePerContract/instruments[instrument]['mmr']
  quantity = lever*capitalToUse/pricePerContract # quantity*pricePerContract*1% = lever*1%*capitalToUse

  origQuantity = 0
  # limit quantity in order to not surpass our available capital
  if int(math.floor(quantity)) * instruments[instrument]['mmr'] > capitalToUse:
    origQuantity = int(math.floor(quantity))
    quantity = capitalToUse / instruments[instrument]['mmr']

  # use smaller quantities for debugging resp. interface testing
  if DEBUG:
    quantity = quantity/100
  # quantities are integers, not real numbers
  quantity = int(math.floor(quantity))
  if quantity > MAX_MICRO_LOTS:
    quantity = MAX_MICRO_LOTS
  if origQuantity > 0:
    log("  current rate %s %f, capital available EUR %f, lever %f, price per contract EUR %f => quantity %d (reduced from %d because of capital limitation)" % (baseCurrency, price, capitalToUse, lever, pricePerContract, quantity, origQuantity))
  else:
    log("  current rate %s %f, capital available EUR %f, lever %f, price per contract EUR %f => quantity %d" % (baseCurrency, price, capitalToUse, lever, pricePerContract, quantity))
  return quantity

# create a timely ordered list of tasks
def createExecutionPlan(connection, instrumentsWithOpenPositionOrOrder, pred_day):
  now = dt.datetime.now(TIMEZONE)
  log("createExecutionPlan() " + nowString())
  executionPlan = []

  # create task for all open orders
  orderList = connection.get_orders(kind='list')
  log("  have %d open orders" % len(orderList))
  for order in orderList:
    if not order['isStopOrder']: # ignore the stop orders within the OCO orders
      if order['ocoBulkId']:
        close = True
      else:
        close = False
      if order['open'] is None:
        price = 0.0
      else:
        price = order['open']
      task = newTask(order['currency'], price, close)
      task['order'] = order
      task['time'] = closeTime(order['currency']) # for active open orders: prevent task from being ordered before opening tasks without orders
      task['long'] = order['isBuy']
      task['quantity'] = amountBy1000(order['amountK'])
      executionPlan.append(task)
      instrumentsWithOpenPositionOrOrder[task['instrument']] = True
      log("  PLAN %s order: %d %s %s" % ("close" if task['close'] else "open", task['quantity'], task['instrument'], posTypeStr(task['long'])))

  # create a close-position task for open positions
  openPositionList = connection.get_open_positions(kind='list') # openPositionList[].isBuy, amountK, time, usedMargin, tradeId, open
  log("  have %d open positions" % len(openPositionList))
  for position in openPositionList:
    log("open position: %s" % str(position))
    task = newTask(position['currency'], position['open'], True)
    task['long'] = position['isBuy']
    task['time'] = closeTime(task['instrument'])
    task['quantity'] = amountBy1000(position['amountK'])
    if DO_TRADE:
      task['order'] = issueCloseOrder(connection, task)
    executionPlan.append(task)
    instrumentsWithOpenPositionOrOrder[task['instrument']] = True
    log("  PLAN close position: %s %d %s price %f tradeId %s" % (posTypeStr(task['long']), task['quantity'], task['instrument'], task['price'], task['tradeId']))

  # (re-)check for all instruments of interest without open position or open order whether there is a trade signal
  # if there is a trade signal then create a task
  log("  have %d instruments" % len(instruments.keys()))
  instrumentsWithSignals = []
  for instrument in instruments:
    if instrument in instrumentsWithOpenPositionOrOrder:
      log("  %s already has an open position or order" % instrument)
    else:
      log("  " + instrument)
      createCandleImageForPredictor(connection, instrument, pred_day)
      signal, probability, probabilities = predict(instrument, pred_day)
      if signal == "0" and not DEBUG:
        continue # no trade signal
      if probability < MIN_PROBABILITY:
        log("Signal %s for %s ignored because probability %f < %f" % (signal, instrument, probability, MIN_PROBABILITY))
        continue # signal too weak
      instrumentsWithSignals.append((instrument, signal, probability))
  log("  have %d instruments with signals" % len(instrumentsWithSignals))
  if len(instrumentsWithSignals):
    # get the instrument with trading signal and maximal (probability for occurrence) / (minimal margin request)
    bestInstrument = ("", "", 0.0) # instrument, signal, assessment value
    for instrument, signal, probability in instrumentsWithSignals:
      modelError = instruments[instrument]['error'][MODEL]
      probability = probability * (1.0 - modelError) + (1.0 - probability) * modelError
      assessment = probability / instruments[instrument]['mmr']
      if assessment > bestInstrument[2]:
        bestInstrument = (instrument, signal, assessment)
    # create a task for that instrument
    instrument, signal, assessment = bestInstrument
    openingTime = openTime(instrument, pred_day)
    if DEBUG or openingTime >= now: # no position opening task with execution time in the past
      task = newTask(instrument, 0.0, False)
      task['long'] = True if signal == "L" else False
      task['time'] = openingTime
      executionPlan.append(task)
      log("  PLAN %s: %s at %s with probability %f and mmr %f" % (posTypeStr(task['long']), task['instrument'], task['time'].strftime("%T"), probability, instruments[instrument]['mmr']))
    else:
      log("  execution time for %s is in the past: %s" % (instrument, openingTime.strftime("%T")))
  return executionPlan

# get quotes for instruments of interest via stream
def subscribePrices(connection, instrumentsWithOpenPositionOrOrder, executionPlan):
  for task in executionPlan:
    subscribe(connection, task['instrument'])
  for instrument in instrumentsWithOpenPositionOrOrder:
    subscribe(connection, instrument)

# create a position-opening order
# task: values for the keys quantity, long, instrument must already have been set
# returns the order
def issueOpenOrder(connection, task):
  quote = connection.get_last_price(task['instrument'])
  if task['long']:
    currentRate = quote.Ask
  else:
    currentRate = quote.Bid
  task['assumedOpeningRate'] = currentRate
  if task['estimatedCost'] is None:
    log("TRADE open %s %d %s, current rate %f (bid %f, ask %f) trade costs cannot be estimated" % (posTypeStr(task['long']), task['quantity'], task['instrument'], currentRate, quote.Bid, quote.Ask))
  else:
    log("TRADE open %s %d %s, current rate %f (bid %f, ask %f) trade cost %f" % (posTypeStr(task['long']), task['quantity'], task['instrument'], currentRate, quote.Bid, quote.Ask, task['estimatedCost']))
  if task['quantity'] > MAX_MICRO_LOTS:
    exit()
  return connection.open_trade(account_id=connection.get_account_ids()[0],
         symbol=task['instrument'], # (mandatory param)
         is_buy = task['long'], # (mandatory param)
         amount = task['quantity'], # in micro-lots resp. contracts (mandatory param)
         time_in_force = 'IOC', # Immediate Or Cancel (mandatory param)
         order_type = 'AtMarket', # at current market rate (mandatory param)
#           is_in_pips = False, # refers to stop/limit rate
#           rate = 105,
#           limit = 120
         )

# create an OCO order for closing the position
# task: values for the keys quantity, long, instrument, time, price (opening rate) must already have been set
# returns the limit order
# stop-loss at 1%, at least 1% earnings (NO trailing limit, otherwise earnings >=1% could not be guaranteed)
def issueCloseOrder(connection, task):
  log("TRADE close %s %d %s" % (posTypeStr(task['long']), task['quantity'], task['instrument']))
  if task['long']:
    limitRate=task['price'] * 1.01
    stopRate2=task['price'] * 0.99
  else:
    limitRate=task['price'] * 0.99
    stopRate2=task['price'] * 1.01
# TODO the following magic is for buy orders
  rateValue = limitRate * 0.99 # rate must be below limit
  rate2Value = limitRate * 1.01 # rate must be above stop, stop must be < current rate @#$!!
  oco_order = connection.create_oco_order(account_id=connection.get_account_ids()[0],
                                 symbol=task['instrument'],
                                 is_buy=not task['long'],
                                 is_buy2=not task['long'],
                                 amount=task['quantity'],
                                 is_in_pips=False,
                                 time_in_force='GTC',
                                 at_market=0,
                                 order_type='AtMarket',
                                 limit=limitRate,
                                 rate=rateValue,
                                 rate2=rate2Value,
                                 stop2=stopRate2,
                                 trailing_step=0, trailing_step2=0,
                                 trailing_stop_step=0,
                                 trailing_stop_step2=0)
  # return the limit order, not the oco order
  for o in oco_order.get_order_ids():
    if o.isLimitOrder:
      return o;
  log("Have no limit order in OCO order!")
  return Null;

def getCurrentRate(longPos, close, quote):
  if longPos and close or not longPos and not close:
    return quote.Bid # sell (closing a LONG position or opening a short position)
  return quote.Ask # buy (opening a LONG position or closing a short position

# process tasks
def executePlan(connection, instrumentsWithOpenPositionOrOrder, executionPlan):
  log("executePlan(%d tasks) %s" % (len(executionPlan), nowString()))
  while len(executionPlan):
    # sort here, because the task being handled in the former loop iteration may have changed execution time
    executionPlan = sorted(executionPlan, key=lambda task: task['time'])
    # sleep until it is time to do something
    while True:
      task = executionPlan[0]
      waitTime = task['time'] - dt.datetime.now(TIMEZONE)
      sleepTime = waitTime.days * 86400 + waitTime.seconds + waitTime.microseconds/1000000
      if sleepTime <= 0:
        break # there is something to do ...
      sleepTime = min(15, sleepTime) # wait for at most 15 secs
      time.sleep(sleepTime)
      # tell the watchdog we are still operational
      watchdog.iAmAlive(os.path.realpath(__file__))
      # check status of open orders
      toBeDeleted = [] # remember tasks that must be deleted to delete them after iterating the executionPlan
      for task in executionPlan:
        if 'order' in task:
          state = task['order'].get_status()
          if state == 'Canceled':
            if task['close']:
              log("Canceled close %s! Position stays open! %d at %f" % (task['instrument'], task['quantity'], task['price']))
            else:
              log("Canceled open %s" % task['instrument'])
            toBeDeleted.append(task)
          elif state == 'Executed':
            if task['close']:
              # closing order done
              closingPrice = closePositionPrice(connection, task['order'].tradeId)
              log("TRADE closed %d %s %s, %f->%f" % (task['quantity'], task['instrument'], posTypeStr(task['long']), task['price'], closingPrice))
              toBeDeleted.append(task)
            else:
              # opening order done
              task['price'], actualPositionAmount = openPositionPriceAndAmount(connection, task['order'].tradeId)
              instrumentsWithOpenPositionOrOrder[task['instrument']] = True
              if 'assumedOpeningRate' in task:
                log("TRADE opened %d/%d %s %s for %f per microlot (should have been %f)" % (actualPositionAmount, task['quantity'], task['instrument'], posTypeStr(task['long']), task['price'], task['assumedOpeningRate']))
              else:
                log("TRADE opened %d/%d %s %s for %f per microlot" % (actualPositionAmount, task['quantity'], task['instrument'], posTypeStr(task['long']), task['price']))
              task['quantity'] = actualPositionAmount
              # reuse task as closing-position task
              task['close'] = True
              task['time'] = closeTime(task['instrument'])
              if DO_TRADE:
                task['order'] = issueCloseOrder(connection, task)
              else:
                del task['order']
          else:
            log("Order state of %s is %s" % (task['instrument'], state))
      for t in toBeDeleted:
        executionPlan.remove(t)
      # re-sort by time
      executionPlan = sorted(executionPlan, key=lambda task: task['time'])

    # handle the 1st task
    task = executionPlan[0]
    log("process task at " + nowString() + " with task execution time " + task['time'].strftime('%Y-%m-%d %T %Z (%z)'))
    quote = connection.get_last_price(task['instrument'])
    if task['close']: # close position
      if DO_TRADE:
        # The closing order has not been executed yet. We need to close the position unconditionally (limitless) now.
        task['time'] = closeTime(task['instrument']) + dt.timedelta(minutes=30)
        #connection.change_trade_stop_limit(task['order'].tradeId, is_stop=False, rate=0, trailing_step=0)
        task['order'].set_limit_rate(limit_rate=0) # TODO: "limit_rate=0" removes limit? "limit_rate=Null" ignores the rate
      else:
        closingPrice = getCurrentRate(task['long'], close, quote)
        log("NO TRADE close %s %d %s %f->%f" % (posTypeStr(task['long']), task['quantity'], task['instrument'], task['price'], closingPrice))
        # task is done
        executionPlan.remove(task)
    else: # open position
      account = connection.get_accounts().T[0]
      task['quantity'] = calculateQuantity(connection, task['instrument'], task['long'])
      # trade cost (current value, not necessarily the same value at execution time)
      spread = quote.Ask - quote.Bid
      pipValuePerMicroLot = getPipValuePerMicroLotInEur(connection, task['instrument'])
      if not pipValuePerMicroLot is None:
        task['estimatedCost'] = 2 * spread * pipValuePerMicroLot * task['quantity'] # 2* because opening and closing is charged each
      if DO_TRADE:
        task['order'] = issueOpenOrder(connection, task)
        task['time'] = tradingDayEnd().replace(year=3000) # just shift it far into the future (towards end of time-ordered task list) while we are waiting for the order to execute
      else:
        task['price'] = getCurrentRate(task['long'], False, quote)
        instrumentsWithOpenPositionOrOrder[task['instrument']] = True
        if 'estimatedCost' in task:
          log("NO TRADE open %s %d %s for %f, spread %f, estimated cost %f" % (posTypeStr(task['long']), task['quantity'], task['instrument'], task['price'], spread, task['estimatedCost']))
        else:
          log("NO TRADE open %s %d %s for %f, spread %f" % (posTypeStr(task['long']), task['quantity'], task['instrument'], task['price'], spread))
        # we pretend to have opened a position, now convert this task into a closing-position task
        task['close'] = True
        task['time'] = closeTime(task['instrument'])

# startDate and endDate must have no timezone info
def PostMortemForInstrument(connection, instrument, startDate, endDate):
  log("postmortem for %s" % instrument)
  results = []
  # read candle prices
  try:
    candles=connection.get_candles(instrument, period='D1', start=startDate - dt.timedelta(days=56), stop=endDate)
    candlesHourly=connection.get_candles(instrument, period='H1', start=startDate - dt.timedelta(days=56), stop=endDate)
    candlesHourly['open'] =(candlesHourly['bidopen'] +candlesHourly['askopen']) /2
    candlesHourly['close']=(candlesHourly['bidclose']+candlesHourly['askclose'])/2
    candlesHourly=candlesHourly.drop(columns=['bidopen','bidclose','bidhigh', 'bidlow','askopen', 'askclose',
                                              'askhigh', 'asklow','tickqty'])
    #log(candles.to_string())
  except Exception as e:
    log('Wertpapier-Daten für %s können nicht gelesen werden: %s' % (instrument, e))
    return results

  # create images and predict
  rangeLen = (endDate - startDate).days
  date = startDate
  while date < endDate:
    log("  %s" % date.strftime("%Y-%m-%d"))
    if Create_Candle(instrument, instruments[instrument]['days'], connection, MODEL, date, debug = True, candles=candles):
      signal, probability, probabilities = predict(instrument, pred_day=date)
      try:
        # get hourly prices from 19:00 at date to 16:00 at date+1 in EST (but need UTC here)
        s = date + dt.timedelta(days=1)
        s = s.replace(hour=0, minute=0, second=0, microsecond=0)
        e = s.replace(hour=21, minute=0, second=0, microsecond=0)
        #candlesIntraday=connection.get_candles(instrument, period='H1', start=s, stop=e)
        candlesIntraday=candlesHourly[s.strftime("%Y-%m-%d %T") : e.strftime("%Y-%m-%d %T")]
        log("    Intraday [%s, %s]" % (candlesIntraday.index[0].strftime("%Y-%m-%d %T"), candlesIntraday.index[-1].strftime("%Y-%m-%d %T")))
        #print(candlesIntraday.to_string())

#        # calculate OC
#        candlesIntraday['open'] =(candlesIntraday['bidopen'] +candlesIntraday['askopen']) /2
#        candlesIntraday['close']=(candlesIntraday['bidclose']+candlesIntraday['askclose'])/2
#        candlesIntraday=candlesIntraday.drop(columns=['bidopen','bidclose','bidhigh', 'bidlow','askopen', 'askclose',
#                                                      'askhigh', 'asklow','tickqty'])

        # calculate change
        open = candlesIntraday.at[candlesIntraday.index[0],'open']
        close = candlesIntraday.at[candlesIntraday.index[-1],'close']
        if open is not None and not open == 0.0:
          change = (close - open)/open
        else:
          change = 0
        log("    open %f, close %f, change %.2f%%" % (open, close, round(100*change,2)))
        results.append((date, signal, probabilities, change))
      except Exception as e:
        log('Intraday-Daten für %s können nicht gelesen werden: %s' % (instrument, e))
    else:
      results.append((date, "no data", (0.0, 0.0, 0.0), 0.0))
    date = date + dt.timedelta(days=1)
  return results

# start, end: no timezone, only day
def PostMortemAll(connection, start, end):
  # post mortem analysis for all instruments
  f = open("pm.csv", "w")
  # write date lines
  line = ","
  tmp = start
  days = (end-start).days
  for x in range(days):
    line = line + tmp.strftime("%Y-%m-%d") + ",,,,,"
    tmp = tmp + dt.timedelta(days=1)
  f.write("%s\n" % line)
  # write header line
  line = "instrument," + ("signal,0-prob,L-prob,S-prob,change," * days)
  f.write("%s\n" % line)
  for instr in instruments:
    f.write("%s," % instr)
    r = PostMortemForInstrument(connection, instr, start, end)
    for x in range(len(r)):
      signal = r[x][1]
      if signal == "0":
        signal = ""
      else:
        signal = '\"' + signal + '\"'
      f.write("%s,%s,%s,%s,%s," % (signal, probToString(r[x][2][0]), probToString(r[x][2][1]), probToString(r[x][2][2]), ("%.2f%%" % (100*r[x][3]))))
    f.write("\n")
    #print("stop after 1st instrument")
    #break
  f.close()

#
def avgError():
  errors = 0.0
  for i in instrumentList:
    errors += i[2][MODEL]
  avg_error = errors/len(instrumentList)
  print("avg error %f" % avg_error)

#avgError()
#exit()

def getPredictionDay():
  # determine prediction day
  posOpeningTime=tradingDayStart()
  posOpeningTime=posOpeningTime.replace(hour=POSOPENHOUR, minute=POSOPENMINUTE, second=0, microsecond=0) # shift to position-opening time
  if dt.datetime.now(TIMEZONE) > posOpeningTime:
    # we passed the time at which a position must be opened, so do the prediction for the next trading day
    posOpeningTime = nextTradingDayStart()
  pred_day = posOpeningTime
  # pred_day = dt.datetime(2020, 1, 2)
  log("Prediction for %s" % pred_day.strftime('%Y-%m-%d %T %Z (%z)'))

  files.createPath(files.imagePath(pred_day, MODEL))
  files.createPath(files.normalizedImagePath(pred_day, MODEL))
  return pred_day

removeLogFile()
log("================== starting " + ("LIVE " if LIVE else "TEST ") + ("TRADE " if DO_TRADE else "NO_TRADE ") + ("DEBUG " if DEBUG else "") + nowString() + " ====================")
files.createPath(files.path_to_akt_image[MODEL])
token = readTokenFromFile()
try:
  fxcmServer = 'real' if LIVE else 'demo'
  log("connect to server '%s' with token '%s'" % (fxcmServer, token))
  connection = fxcmpy.fxcmpy(access_token = token, log_file = CONNECTION_LOG, log_level = 'info', server = fxcmServer)
  log("connection %sestablished at %s" % ("" if connection.is_connected() else "NOT ", nowString()))
  log("account IDs " + ', '.join(map(str, connection.get_account_ids())))
  if len(connection.get_account_ids()):
    log(str(connection.get_accounts()))
#  log("tradeable instruments " + '\n  '.join(map(str, connection.get_instruments())))
  log("instruments of concern")
  for i in instruments:
    log("  %s %d days, error %.1f%%" % (i, instruments[i]['days'], 100.0*instruments[i]['error'][MODEL]))
  log("open positions")
  if len(connection.get_open_positions(kind='list')):
    log(str(connection.get_open_positions()))
  log("regular order IDs " + ', '.join(map(str, connection.get_order_ids())))
  if len(connection.get_order_ids()):
    log(str(connection.get_orders()))
  log("oco order IDs " + ', '.join(map(str, connection.get_oco_order_ids())))
  if len(connection.get_oco_order_ids()):
    log(str(connection.get_oco_order_ids()))
  instrumentsWithOpenPositionOrOrder = {}

  # determine prediction day
  pred_day = getPredictionDay()

  files.createPath(files.imagePath(pred_day, MODEL))
  files.createPath(files.normalizedImagePath(pred_day, MODEL))

#  # print prediction results for all instruments
#  for instrument in instruments:
#    createCandleImageForPredictor(connection, instrument, pred_day)
#    signal, probability, probabilities = predict(instrument, pred_day)
#    log("%s %s %f" % (instrument, signal, probability))

  # subscribe exchange rates needed for indices and commodities
  for i in instruments:
    if 'index' in instruments[i] and not instruments[i]['index']['pipCurrency'] == 'EUR':
      pair = 'EUR/' + instruments[i]['index']['pipCurrency']
      subscribe(connection, pair)

#  # log current prices of indices and commodities
#  for i in instruments:
#    subscribe(connection, i)
#  log("Current prices")
#  for i in instruments:
#    quote = connection.get_last_price(i)
#    log("  %s ask %f, bid %f" % (i, quote.Ask, quote.Bid))

#  # print all prediction results for one day
#  Predict_one_day(connection, dt.datetime(2020, 1, 1))

#  # post mortem analysis for all instruments
#  PostMortemAll(connection, dt.datetime(2020, 2, 8), dt.datetime(2020, 2, 18))

#  q = calculateQuantity(connection, 'AUD/CHF', True)
#  q = calculateQuantity(connection, 'AUS200', True)
#  q = calculateQuantity(connection, 'XAU/USD', True)

  executionPlan = createExecutionPlan(connection, instrumentsWithOpenPositionOrOrder, pred_day)
  subscribePrices(connection, instrumentsWithOpenPositionOrOrder, executionPlan)
  executePlan(connection, instrumentsWithOpenPositionOrOrder, executionPlan)

except Exception:
  #traceback.print_exc() # print exception including stack to console
  exceptionText = traceback.format_exc()
  exceptionText.replace('\\n', '\n')
  log(exceptionText)
log("================== ending " + nowString() + " ====================")
print("processing ended")

# NOTE: closing position with close_trade() is for hedging accounts only, use open_trade() with opposite direction

# https://www.fxcm.com/de/konto/spread-kosten/:
# ( Spread ) x ( Pip Kosten ) x ( Anzahl der Lots ) = Spreadkosten

import datetime as dt
import pytz

TIMEZONE = pytz.timezone('US/Eastern')
UTC_TIMEZONE = pytz.timezone('UTC')

# trading week
#   start: Sunday 17:00-17:15 ET
#   end:   Friday 16:55 ET

# Return the begin of the trading day.
# Time: at which a new position may be opened.
def nextTradingDayStart():
  now = dt.datetime.now(TIMEZONE)
  if now.time() > dt.time(17, 0, tzinfo = TIMEZONE): # we are within the 1st calendar day of the trading day
    now = now + dt.timedelta(days=1)
  weekday = now.weekday()
  if weekday == 4 or weekday == 5: # trading day starting at Friday 17:00 ET or Saturday 17:00 ET
    now = now + dt.timedelta(days=(6-weekday)) # shift to next Sunday
  return now.replace(hour=17, minute=15, second=0, microsecond=0)

# Return the begin of the trading day.
# If we are currently not in a trading day (weekend), then return the last trading day.
def tradingDayStart():
  now = dt.datetime.now(TIMEZONE)
  if now.time() < dt.time(17, tzinfo = TIMEZONE): # we are within the 2nd calendar day of the trading day
    now = now - dt.timedelta(days=1)
  weekday = now.weekday()
  if weekday == 4 or weekday == 5: # trading day starting at Friday 17:00 ET or Saturday 17:00 ET
    now = now - dt.timedelta(days=(weekday-3)) # shift to last Thursday
  return now.replace(hour=17, minute=15, second=0, microsecond=0)

# Return the end of the trading day.
# If we are currently not in a trading day (weekend), then return the next trading day.
def tradingDayEnd():
  now = dt.datetime.now(TIMEZONE)
  if now.time() >= dt.time(17, tzinfo = TIMEZONE): # we are within the 1st calendar day of the trading day
    now = now + dt.timedelta(days=1)
  weekday = now.weekday()
  if weekday == 5 or weekday == 6: # trading day ending at Saturday 17:00 ET or Sunday 17:00 ET
    now = now + dt.timedelta(days=(7-weekday)) # shift to next Monday
  return now.replace(hour=17, minute=0, second=0, microsecond=0)

# Return the end of the last trading day.
def lastTradingDayEnd():
  now = dt.datetime.now(TIMEZONE)
  if now.time() < dt.time(17, tzinfo = TIMEZONE): # we are within the 2nd calendar day of the trading day
    now = now - dt.timedelta(days=1)
  if now.day == 1 and now.month ==1: # no trade on 1.1.
    now = now - dt.timedelta(days=1)
  weekday = now.weekday()
  if weekday == 5: # trading day ending at Saturday 17:00 ET
    now = now - dt.timedelta(days=1) # shift to last Friday
  return now.replace(hour=17, minute=0, second=0, microsecond=0)

def shiftToEndOfTradingDay(dateTime):
  return dateTime.replace(hour=17, minute=0, second=0, microsecond=0)

def tradingDayStartUtc(date):
  start = dt.datetime(date.year, date.month, date.day, 17, 0)
  startLocal = pytz.timezone('US/Eastern').localize(start)
  return startLocal.astimezone(pytz.timezone('UTC'))

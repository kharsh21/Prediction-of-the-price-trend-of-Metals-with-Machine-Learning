# instruments of concern: name, days, error for 0.8%, error for 1%, minimal margin requirement for EUR account, commission per lot for USD account, list of trading weekdays (Monday=0),
#                         indices/commodities only: max trade size, pip value in fxcm contract, pip value currency, PIP/point resp. PIP/CCY
# data for indices: https://docs.fxcorporate.com/user-guide/ug-cfd-product-guide-fxcmmarkets-en.pdf
# MMR:              https://docs.fxcorporate.com/MMR/margin_notification_center_ltd_de.pdf
instrumentList=(('AUD/CHF', 56, (0.142, 0.066), 0.0001,  35.0,  0.06, (0,1,2,3,6),     0, 0,    '',      0),
                ('AUD/JPY', 32, (0.131, 0.096), 0.01,    35.0,  0.06, (0,1,2,3,6),     0, 0,    '',      0),
                ('AUD/USD', 56, (0.123, 0.069), 0.0001,  35.0,  0.06, (0,1,2,3,6),     0, 0,    '',      0),
                ('AUS200',  32, (0.128, 0.052), 0.1,     25.0,  0.0,  (0,1,2,3,6),  5000, 0.1,  'AUD',   1.0), # 250 fxcm contracts = 1 ASX/SPI 200 Index Future (A$25/point) => max $2.3M
                ('CAD/CHF', 56, (0.088, 0.050), 0.0001,  26.64, 0.06, (0,1,2,3,6),     0, 0,    '',      0),
                ('CAD/JPY', 32, (0.121, 0.076), 0.01,    26.64, 0.06, (0,1,2,3,6),     0, 0,    '',      0),
                ('EUR/AUD', 56, (0.119, 0.045), 0.0001,  50.0,  0.06, (0,1,2,3,6),     0, 0,    '',      0),
                ('EUR/GBP', 56, (0.062, 0.035), 0.0001,  33.30, 0.06, (0,1,2,3,6),     0, 0,    '',      0),
                ('EUR/JPY', 32, (0.125, 0.055), 0.01,    33.30, 0.06, (0,1,2,3,6),     0, 0,    '',      0),
                ('EUR/NZD', 32, (0.104, 0.043), 0.0001,  50.0,  0.06, (0,1,2,3,6),     0, 0,    '',      0),
                ('EUR/TRY', 56, (0.091, 0.107), 0.0001, 120.0,  0.06, (0,1,2,3,6),     0, 0,    '',      0),
                ('GBP/AUD', 56, (0.119, 0.067), 0.0001,  65.0,  0.06, (0,1,2,3,6),     0, 0,    '',      0),
                ('GBP/CAD', 32, (0.100, 0.047), 0.0001,  43.29, 0.06, (0,1,2,3,6),     0, 0,    '',      0),
                ('GBP/CHF', 32, (0.035, 0.043), 0.0001,  43.29, 0.06, (0,1,2,3,6),     0, 0,    '',      0),
                ('GBP/JPY', 56, (0.148, 0.073), 0.01,    43.29, 0.06, (0,1,2,3,6),     0, 0,    '',      0),
                ('GBP/NZD', 56, (0.045, 0.050), 0.0001,  65.0,  0.06, (0,1,2,3,6),     0, 0,    '',      0),
                ('GBP/USD', 56, (0.056, 0.028), 0.0001,  43.29, 0.04, (0,1,2,3,6),     0, 0,    '',      0),
                ('NAS100',  32, (0.160, 0.132), 0.1,     45.0,  0.0,  (0,1,2,3,6),  5000, 0.1,  'USD',   1.0), # 200 fxcm contracts = 1 NASDAQ 100 E-mini Future ($20/point) => max $4.5M
                ('NZD/CAD', 56, (0.101, 0.050), 0.0001,  35.0,  0.06, (0,1,2,3,6),     0, 0,    '',      0),
                ('NZD/CHF', 32, (0.108, 0.055), 0.0001,  35.0,  0.06, (0,1,2,3,6),     0, 0,    '',      0),
                ('NZD/JPY', 56, (0.158, 0.081), 0.01,    35.0,  0.06, (0,1,2,3,6),     0, 0,    '',      0),
                ('NZD/USD', 32, (0.055, 0.071), 0.0001,  35.0,  0.06, (0,1,2,3,6),     0, 0,    '',      0),
                ('SPX500',  56, (0.115, 0.063), 1.0,    160.0,  0.0,  (0,1,2,3,6),  5000, 0.1,  'USD',  10.0), # 50 fxcm contracts = 1 E-mini S&P Future ($50/point) => max $16M
                ('US30',    32, (0.121, 0.094), 0.0001, 140.0,  0.0,  (0,1,2,3,6),  4000, 0.1,  'USD',   1.0), # 50 fxcm contracts = 1 E-mini Dow Future ($5/point) => max $11M
                ('USD/NOK', 32, (0.145, 0.068), 0.0001,  50.0,  0.06, (0,1,2,3,6),     0, 0,    '',      0),
                ('USD/SEK', 56, (0.119, 0.086), 0.0001,  50.0,  0.06, (0,1,2,3,6),     0, 0,    '',      0),
                ('XAU/USD', 56, (0.196, 0.132), 1.0,     75.0,  0.0,  (0,1,2,3,6), 10000, 0.01, 'USD', 100.0)  # price in USD/troy ounce
)

instruments = {}
for name, days, error, pip, mmr, commission, trading_days, maxSize, pipValue, pipCurrency, pipPerPoint in instrumentList:
  instruments[name] = {}
  instruments[name]['days'] = days
  instruments[name]['error'] = error
  instruments[name]['pip'] = pip
  instruments[name]['mmr'] = mmr
  instruments[name]['trading_days'] = trading_days
  if not maxSize == 0:
    # is index or commodity
    instruments[name]['index'] = {'maxSize':maxSize, 'pipValue':pipValue, 'pipCurrency':pipCurrency, 'pipPerPoint':pipPerPoint}

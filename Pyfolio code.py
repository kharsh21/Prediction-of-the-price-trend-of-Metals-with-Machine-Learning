# Holger post for pyfolio report
import pandas as pd
import pyfolio as pf

holger = pd.read_excel("candles_Backtest_XAG_USD.xlsx", na_values = '-', parse_dates=True , index_col=0)
holger = holger[holger['P:XAG/USD'].notna()]
holger.head(15)




#returns = holger['R:XAG/USD'].astype(float)
pf.create_simple_tear_sheet(holger['Selected trades'], benchmark_rets=None)

pf.create_full_tear_sheet(holger['Selected trades'])

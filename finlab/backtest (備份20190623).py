import datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import warnings
import math

warnings.simplefilter(action='ignore', category=FutureWarning)

def backtest(start_date, end_date, hold_days, strategy, data, weight='average', benchmark=None, stop_loss=None, stop_profit=None):
    
    # portfolio check
    if weight != 'average' and weight != 'price':
        print('Backtest stop, weight should be "average" or "price", find', weight, 'instead')

    # get price data in order backtest
    data.date = end_date
    
    price = data.get('收盤價', (end_date - start_date).days)
    #自己加配息:
    dividend = data.get('CASH', 20)
    #
    # start from 1 TWD at start_date, 
    end = 1
    date = start_date
    
    # record some history
    equality = pd.Series()
    nstock = {}
    transections = pd.DataFrame()
    maxreturn = -10000
    minreturn = 10000
    
    def trading_day(date):
        if date not in price.index:
            temp = price.loc[date:]
            if temp.empty:
                return price.index[-1]
            else:
                return temp.index[0]
        else:
            return date
    
    def date_iter_periodicity(start_date, end_date, hold_days):
        date = start_date
        while date < end_date:
            yield (date), (date + datetime.timedelta(hold_days))
            date += datetime.timedelta(hold_days)
                
    def date_iter_specify_dates(start_date, end_date, hold_days):
        dlist = [start_date] + hold_days + [end_date]
        if dlist[0] == dlist[1]:
            dlist = dlist[1:]
        if dlist[-1] == dlist[-2]:
            dlist = dlist[:-1]
        for sdate, edate in zip(dlist, dlist[1:]):
            yield (sdate), (edate)
    
    if isinstance(hold_days, int):
        dates = date_iter_periodicity(start_date, end_date, hold_days)
    elif isinstance(hold_days, list):
        dates = date_iter_specify_dates(start_date, end_date, hold_days)
    else:
        print('the type of hold_dates should be list or int.')
        return None
    for sdate, edate in dates:
        
        # select stocks at date
        data.date = sdate
        stocks = strategy(data)
        
        # hold the stocks for hold_days day
        s = price[stocks.index & price.columns][sdate:edate].iloc[1:]
        sma_120 = price[stocks.index & price.columns][sdate - datetime.timedelta(days=1440):edate].rolling(120).mean().reindex(s.index)
        #自己加，配息:
        div = dividend[stocks.index & dividend.columns][sdate:edate]
        #
        if s.empty:
            s = pd.Series(1, index=pd.date_range(sdate + datetime.timedelta(days=1), edate))
        else:
            
            if stop_loss == 'sma_120':
                below_stop = s < sma_120
                below_stop = (below_stop.cumsum() > 0).shift(2).fillna(False)
                s[below_stop] = np.nan

            elif stop_loss != None:
                below_stop = ((s / s.bfill().iloc[0]) - 1)*100 < -np.abs(stop_loss)
                below_stop = (below_stop.cumsum() > 0).shift(2).fillna(False)
                s[below_stop] = np.nan
                
            if stop_profit != None:
                above_stop = ((s / s.bfill().iloc[0]) - 1)*100 > np.abs(stop_profit)
                above_stop = (above_stop.cumsum() > 0).shift(2).fillna(False)
                s[above_stop] = np.nan
                
            s.dropna(axis=1, how='all', inplace=True)
            
            # record transections
            transections = transections.append(pd.DataFrame({
                'buy_price': s.bfill().iloc[0],
                'sell_price': s.apply(lambda s:s.dropna().iloc[-1]),
                'lowest_price': s.min(),
                'highest_price': s.max(),
                'buy_date': pd.Series(s.index[0], index=s.columns),
                'sell_date': s.apply(lambda s:s.dropna().index[-1]),
            }))
            
            transections['profit(%)'] = (transections['sell_price'] / transections['buy_price'] - 1) * 100
            
            s.ffill(inplace=True)
                
            # calculate equality
            # normalize and average the price of each stocks
            #自己修改報酬算法，以下是原碼
            # if weight == 'average':
            #     s = s/s.bfill().iloc[0]
            # s = s.mean(axis=1)
            # s = s / s.bfill()[0]
            #自己加:
            if weight == 'average':
                w = 1/s.bfill().iloc[0]
                w = w/w.sum()
            else:
                w = 1/len(s.columns)
            try:
                p = s.iloc[s.index > div.index[0]]+div.iloc[-1].astype(float)
                s.update(p)
            except:
                print('no dividend')
            # 進場、退場價
            # print(','.join( str('%.2f'%( s.iloc[-1]) + '-' + '%.2f'%( s.iloc[0])) for i in s.columns)  )
            print(','.join(  str( round((s[i].iloc[-1]/s[i].iloc[0])*100-100,1) ) for i in s.columns)  )
            s = (s*w).mean(axis=1)
            s = s / s.bfill()[0]
            #
        # print some log
        #改寫報酬，原碼如下:
        print(sdate,'-', edate, 
              '報酬率: %.2f'%( s.iloc[-1]/s.iloc[0] * 100 - 100), 
              '%', 'nstock', len(stocks))
        print(','.join(str(i) for i in stocks.index))
        print('-----------------------------------------------------')
        maxreturn = max(maxreturn, s.iloc[-1]/s.iloc[0] * 100 - 100)
        minreturn = min(minreturn, s.iloc[-1]/s.iloc[0] * 100 - 100)
        
        # plot backtest result
        ((s*end-1)*100).plot()
        equality = equality.append(s*end)
        end = (s/s[0]*end).iloc[-1]

        if math.isnan(end):
            end = 1
        
        # add nstock history
        nstock[sdate] = len(stocks)
        
    print('每次換手最大報酬 : %.2f ％' % maxreturn)
    print('每次換手最少報酬 : %.2f ％' % minreturn)
    
    if benchmark is None:
        benchmark = price['0050'][start_date:end_date].iloc[1:]
    
    # bechmark (thanks to Markk1227)
    ((benchmark/benchmark[0]-1)*100).plot(color=(0.8,0.8,0.8))
    plt.ylabel('Return On Investment (%)')
    plt.grid(linestyle='-.')
    plt.show()
    ((benchmark/benchmark.cummax()-1)*100).plot(legend=True, color=(0.8,0.8,0.8))
    ((equality/equality.cummax()-1)*100).plot(legend=True)
    plt.ylabel('Dropdown (%)')
    plt.grid(linestyle='-.')
    plt.show()
    pd.Series(nstock).plot.bar()
    plt.ylabel('Number of stocks held')
    return equality, transections

def portfolio(stock_list, money, data, lowest_fee=20, discount=0.6, add_cost=10):
    price = data.get('收盤價', 1)
    stock_list = price.iloc[-1][stock_list].transpose()
    print('estimate price according to', price.index[-1])

    print('initial number of stock', len(stock_list))
    while (money / len(stock_list)) < (lowest_fee - add_cost) * 1000 / 1.425 / discount:
        stock_list = stock_list[stock_list != stock_list.max()]
    print('after considering fee', len(stock_list))
        
    while True:
        invest_amount = (money / len(stock_list))
        ret = np.floor(invest_amount / stock_list / 1000)
        
        if (ret == 0).any():
            stock_list = stock_list[stock_list != stock_list.max()]
        else:
            break
    
    print('after considering 1000 share', len(stock_list))
        
    return ret, (ret * stock_list * 1000).sum()
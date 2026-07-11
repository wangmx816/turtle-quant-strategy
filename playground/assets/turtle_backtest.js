/* 浏览器端海龟策略回测引擎 — 与 src/backtest.py 逻辑一致 */

function rollingMax(arr, window) {
  const out = new Array(arr.length).fill(null);
  for (let i = window; i < arr.length; i++) {
    let m = -Infinity;
    for (let j = i - window; j < i; j++) m = Math.max(m, arr[j]);
    out[i] = m;
  }
  return out;
}

function rollingMin(arr, window) {
  const out = new Array(arr.length).fill(null);
  for (let i = window; i < arr.length; i++) {
    let m = Infinity;
    for (let j = i - window; j < i; j++) m = Math.min(m, arr[j]);
    out[i] = m;
  }
  return out;
}

function wilderEma(arr, period) {
  const out = new Array(arr.length).fill(null);
  let sum = 0;
  for (let i = 0; i < arr.length; i++) {
    if (arr[i] == null) continue;
    if (i < period) {
      sum += arr[i];
      if (i === period - 1) out[i] = sum / period;
    } else if (out[i - 1] != null) {
      out[i] = (out[i - 1] * (period - 1) + arr[i]) / period;
    }
  }
  return out;
}

function computeATR(rows, period) {
  const tr = rows.map((r, i) => {
    if (i === 0) return r.h - r.l;
    const prev = rows[i - 1].c;
    return Math.max(r.h - r.l, Math.abs(r.h - prev), Math.abs(r.l - prev));
  });
  return wilderEma(tr, period);
}

function computeDonchian(rows, entryN, exitM) {
  const highs = rows.map(r => r.h);
  const lows = rows.map(r => r.l);
  return {
    entryHigh: rollingMax(highs, entryN),
    entryLow: rollingMin(lows, entryN),
    exitHigh: rollingMax(highs, exitM),
    exitLow: rollingMin(lows, exitM),
  };
}

function computeTurtleSignals(rows, cfg) {
  const { entryPeriod, exitPeriod, atrPeriod, stopAtrMult } = cfg;
  const ch = computeDonchian(rows, entryPeriod, exitPeriod);
  const atr = computeATR(rows, atrPeriod);
  const n = rows.length;

  const position = new Array(n).fill(0);
  const buySignal = new Array(n).fill(0);
  const sellSignal = new Array(n).fill(0);
  const stopPrice = new Array(n).fill(null);
  const trigger = new Array(n).fill('');

  let pos = 0;
  let highest = 0;

  for (let i = 0; i < n; i++) {
    const close = rows[i].c;
    const eh = ch.entryHigh[i];
    const el = ch.exitLow[i];
    const a = atr[i];

    if (eh == null || el == null || a == null) {
      position[i] = pos;
      continue;
    }

    if (pos === 0) {
      if (close > eh) {
        pos = 1;
        highest = close;
        buySignal[i] = 1;
        trigger[i] = 'BREAKOUT';
        stopPrice[i] = highest - stopAtrMult * a;
      }
    } else {
      highest = Math.max(highest, close);
      const stop = highest - stopAtrMult * a;
      stopPrice[i] = stop;
      if (close < stop) {
        pos = 0;
        sellSignal[i] = 1;
        trigger[i] = 'STOP_LOSS';
      } else if (close < el) {
        pos = 0;
        sellSignal[i] = 1;
        trigger[i] = 'CHANNEL_EXIT';
      }
    }
    position[i] = pos;
  }

  return { ...ch, atr, position, buySignal, sellSignal, stopPrice, trigger };
}

function filterRowsByPeriod(rows, periodKey) {
  if (!rows.length) return rows;
  const daysMap = { '3m': 63, '6m': 126, '1y': 252, '2y': 504 };
  const n = daysMap[periodKey] || rows.length;
  return rows.slice(-Math.min(n, rows.length));
}

function runBacktest(rows, cfg) {
  const {
    entryPeriod, exitPeriod, atrPeriod, stopAtrMult,
    capital, commission, slippage, positionRatio,
  } = cfg;

  const sig = computeTurtleSignals(rows, cfg);
  const dates = rows.map(r => r.d);
  const closes = rows.map(r => r.c);

  let startIdx = 0;
  for (let i = 0; i < rows.length; i++) {
    if (sig.entryHigh[i] != null && sig.exitLow[i] != null && sig.atr[i] != null) {
      startIdx = i;
      break;
    }
  }

  let cash = capital;
  let shares = 0;
  const trades = [];
  const tradeDetails = [];
  let openTrade = null;
  const buyCost = 1 + commission + slippage;
  const sellCost = 1 - commission - slippage;
  const firstClose = closes[startIdx];
  const strategyNv = [];

  for (let i = startIdx; i < rows.length; i++) {
    const price = closes[i];

    if (sig.buySignal[i] === 1 && shares === 0) {
      const budget = cash * positionRatio;
      const execPrice = price * buyCost;
      const qty = Math.floor(budget / execPrice);
      if (qty > 0) {
        cash -= qty * execPrice;
        shares = qty;
        openTrade = { entryDate: dates[i], entryPrice: price, execEntry: execPrice, qty };
        trades.push({ action: 'BUY', idx: i, date: dates[i], price, execPrice, qty, trigger: sig.trigger[i] });
      }
    } else if (sig.sellSignal[i] === 1 && shares > 0) {
      const execPrice = price * sellCost;
      const entryDate = openTrade ? openTrade.entryDate : dates[i];
      const entryPrice = openTrade ? openTrade.entryPrice : price;
      const execEntry = openTrade ? openTrade.execEntry : price;
      const holdDays = Math.max(0, Math.round((new Date(dates[i]) - new Date(entryDate)) / 86400000));
      const retPct = ((execPrice - execEntry) / execEntry) * 100;
      cash += shares * execPrice;
      trades.push({
        action: 'SELL', idx: i, date: dates[i], price, execPrice, qty: shares,
        trigger: sig.trigger[i], entryDate, entryPrice, returnPct: retPct, holdDays,
      });
      tradeDetails.push({
        entryDate, exitDate: dates[i], entryPrice, exitPrice: price,
        qty: shares, returnPct: retPct, holdDays, trigger: sig.trigger[i],
      });
      shares = 0;
      openTrade = null;
    }

    strategyNv.push((cash + shares * price) / capital);
  }

  if (shares > 0) {
    const last = rows.length - 1;
    const execPrice = closes[last] * sellCost;
    const entryDate = openTrade.entryDate;
    const entryPrice = openTrade.entryPrice;
    const retPct = ((execPrice - openTrade.execEntry) / openTrade.execEntry) * 100;
    const holdDays = Math.max(0, Math.round((new Date(dates[last]) - new Date(entryDate)) / 86400000));
    cash += shares * execPrice;
    tradeDetails.push({
      entryDate, exitDate: dates[last], entryPrice, exitPrice: closes[last],
      qty: shares, returnPct: retPct, holdDays, trigger: 'END_CLOSE',
    });
    shares = 0;
    strategyNv[strategyNv.length - 1] = cash / capital;
  }

  const sliceDates = dates.slice(startIdx);
  const sliceCloses = closes.slice(startIdx);
  const benchmarkNv = sliceCloses.map(c => c / firstClose);

  const metrics = computeMetrics(strategyNv, benchmarkNv, tradeDetails, sliceDates.length, sliceDates);

  const buyDates = [], buyPrices = [], sellDates = [], sellPrices = [];
  for (let i = startIdx; i < rows.length; i++) {
    if (sig.buySignal[i]) { buyDates.push(dates[i]); buyPrices.push(closes[i]); }
    if (sig.sellSignal[i]) { sellDates.push(dates[i]); sellPrices.push(closes[i]); }
  }

  return {
    dates: sliceDates,
    close: sliceCloses,
    entryHigh: sig.entryHigh.slice(startIdx),
    exitLow: sig.exitLow.slice(startIdx),
    atr: sig.atr.slice(startIdx),
    stopPrice: sig.stopPrice.slice(startIdx),
    position: sig.position.slice(startIdx),
    strategyNv,
    benchmarkNv,
    buyDates, buyPrices, sellDates, sellPrices,
    tradeDetails,
    metrics,
  };
}

function computeMetrics(strategyNv, benchmarkNv, tradeDetails, nDays, dates) {
  const years = Math.max(nDays / 252, 1 / 252);
  const finalNv = strategyNv[strategyNv.length - 1] || 1;
  const benchFinal = benchmarkNv[benchmarkNv.length - 1] || 1;

  const annReturn = (Math.pow(finalNv, 1 / years) - 1) * 100;
  const benchAnn = (Math.pow(benchFinal, 1 / years) - 1) * 100;

  let maxDd = 0, peak = strategyNv[0] || 1;
  for (let i = 0; i < strategyNv.length; i++) {
    peak = Math.max(peak, strategyNv[i]);
    maxDd = Math.min(maxDd, strategyNv[i] / peak - 1);
  }

  const dailyRet = [];
  for (let i = 1; i < strategyNv.length; i++) {
    dailyRet.push(strategyNv[i] / strategyNv[i - 1] - 1);
  }
  const rf = 0.02 / 252;
  let sharpe = 0;
  if (dailyRet.length > 1) {
    const mean = dailyRet.reduce((a, b) => a + b, 0) / dailyRet.length;
    const std = Math.sqrt(dailyRet.reduce((s, r) => s + (r - mean) ** 2, 0) / dailyRet.length);
    sharpe = std > 0 ? ((mean - rf) / std) * Math.sqrt(252) : 0;
  }

  const wins = tradeDetails.filter(t => t.returnPct >= 0);
  const winRate = tradeDetails.length ? (wins.length / tradeDetails.length) * 100 : 0;
  const stopLossCount = tradeDetails.filter(t => t.trigger === 'STOP_LOSS').length;

  return {
    annualized_return: annReturn,
    sharpe_ratio: sharpe,
    max_drawdown: maxDd * 100,
    win_rate: winRate,
    trade_count: tradeDetails.length,
    stop_loss_count: stopLossCount,
    benchmark_annualized: benchAnn,
    cumulative_return: (finalNv - 1) * 100,
  };
}

window.TurtleBacktest = {
  computeDonchian,
  computeATR,
  computeTurtleSignals,
  filterRowsByPeriod,
  runBacktest,
};

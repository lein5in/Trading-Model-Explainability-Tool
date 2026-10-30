export const APP_NAME = 'TME'

export const DISCLAIMER =
  'Educational tool, not investment advice. Backtests use historical data and do not predict future returns. Prices come from Yahoo Finance through yfinance and may be delayed or inaccurate. Market regimes are fitted on the full history to explain behavior, not to forecast it.'

export const POINT_IN_TIME_NOTICE = {
  title: 'Point-in-time limit.',
  body: 'Every feature must use only information available at the close of its own bar. TME cannot detect look-ahead in features you supply, so a leaky model will look better than it is.',
}

export const CATALOG_POINT_IN_TIME_NOTICE =
  'Catalog indicators are computed from bars up to each close. Features you upload are assumed to follow the same rule, and TME cannot check it.'

export const LIMITS = {
  maxModelBytes: 10 * 1024 * 1024,
  maxCsvBytes: 5 * 1024 * 1024,
  maxYears: 10,
  maxFeatures: 30,
  maxCostBps: 100,
}

export const MODEL_EXTENSIONS = ['.pkl', '.pickle', '.joblib']

export const JOB_TIMEOUT_SECONDS = 300

export const SHAP_ADDITIVITY_LIMIT = 0.01

export const POLL_INTERVAL_MS = 1500

export const POLL_MAX_RETRIES = 5

export const REQUEST_TIMEOUT_MS = 30000

export const UPLOAD_TIMEOUT_MS = 120000

export const REPORT_TIMEOUT_MS = 300000

export const HISTORY_KEY = 'tme.history'

export const HISTORY_MAX = 20

export const TRADES_PER_PAGE = 12

export const TRADE_WINDOW_BEFORE = 20

export const TRADE_WINDOW_AFTER = 10

export const DEFAULT_FORM = {
  ticker: 'SPY',
  startDate: '2018-01-02',
  endDate: '2024-12-31',
  feeBps: '5',
  slippageBps: '2',
}

export const DEFAULT_DEMO_MODEL_ID = 'demo_xgboost'

export const DASHBOARD_TABS = ['overview', 'features', 'trades', 'report']

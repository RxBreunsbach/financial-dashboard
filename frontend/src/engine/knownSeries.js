/** Series ids known to work with the currently configured plugins, for the editor's dropdown. */
export const KNOWN_SERIES = [
  // Currently configured in config/sources.yaml
  { id: "fred:DGS10", label: "fred:DGS10 — 10-Year Treasury Yield" },
  { id: "fred:DGS2", label: "fred:DGS2 — 2-Year Treasury Yield" },
  { id: "stock:NVDA", label: "stock:NVDA — NVIDIA" },
  { id: "stock:URA", label: "stock:URA — Global X Uranium ETF" },
  { id: "stock:GOOGL", label: "stock:GOOGL — Alphabet" },
  { id: "stock:VDC", label: "stock:VDC — Vanguard Consumer Staples ETF" },
  { id: "stock:TAN", label: "stock:TAN — Invesco Solar ETF" },
  { id: "stock:UPS", label: "stock:UPS — United Parcel Service" },
  { id: "stock:SMR", label: "stock:SMR — NuScale Power" },
  { id: "stock:DJI", label: "stock:DJI — Dow Jones Industrial Average" },
  { id: "stock:IXIC", label: "stock:IXIC — Nasdaq Composite" },
  { id: "stock:GSPC", label: "stock:GSPC — S&P 500" },
  { id: "crypto:BTC-USD", label: "crypto:BTC-USD — Bitcoin" },

  // Other FRED rate/yield series (add a matching entry to config/sources.yaml to backfill these)
  { id: "fred:DGS1MO", label: "fred:DGS1MO — 1-Month Treasury Yield" },
  { id: "fred:DGS3MO", label: "fred:DGS3MO — 3-Month Treasury Yield" },
  { id: "fred:DGS6MO", label: "fred:DGS6MO — 6-Month Treasury Yield" },
  { id: "fred:DGS1", label: "fred:DGS1 — 1-Year Treasury Yield" },
  { id: "fred:DGS5", label: "fred:DGS5 — 5-Year Treasury Yield" },
  { id: "fred:DGS7", label: "fred:DGS7 — 7-Year Treasury Yield" },
  { id: "fred:DGS20", label: "fred:DGS20 — 20-Year Treasury Yield" },
  { id: "fred:DGS30", label: "fred:DGS30 — 30-Year Treasury Yield" },
  { id: "fred:DFF", label: "fred:DFF — Federal Funds Effective Rate" },
  {
    id: "fred:FEDFUNDS",
    label: "fred:FEDFUNDS — Federal Funds Rate (monthly)",
  },
  {
    id: "fred:CPIAUCSL",
    label: "fred:CPIAUCSL — CPI, All Items (use yoy transform for inflation %)",
  },
  {
    id: "fred:CPILFESL",
    label: "fred:CPILFESL — Core CPI, Ex Food & Energy (use yoy transform for inflation %)",
  },
  {
    id: "fred:PPIFIS",
    label: "fred:PPIFIS — PPI, Final Demand (use yoy transform for inflation %)",
  },
  { id: "fred:SOFR", label: "fred:SOFR — Secured Overnight Financing Rate" },
  { id: "fred:DPRIME", label: "fred:DPRIME — Bank Prime Loan Rate" },
  {
    id: "fred:MORTGAGE30US",
    label: "fred:MORTGAGE30US — 30-Year Fixed Mortgage Rate",
  },
  {
    id: "fred:TB3MS",
    label: "fred:TB3MS — 3-Month T-Bill Secondary Market Rate",
  },
  { id: "fred:T10Y3M", label: "fred:T10Y3M — 10Y-3M Treasury Spread" },
  {
    id: "fred:DGS2 - fred:DGS3MO",
    label: "fred:DGS2 - fred:DGS3MO — 2Y-3M Treasury Spread",
  },
  {
    id: "fred:BAMLH0A0HYM2",
    label: "fred:BAMLH0A0HYM2 — ICE BofA High Yield Spread",
  },
  {
    id: "fred:DCOILWTICO",
    label: "fred:DCOILWTICO — WTI Crude Oil Price ($/barrel)",
  },
  {
    id: "fred:GASDESW",
    label: "fred:GASDESW — US Diesel Retail Price ($/gallon)",
  },
  {
    id: "fred:GASDESW * 42",
    label: "fred:GASDESW * 42 — US Diesel Retail Price ($/barrel, 42 gal)",
  },

  // Trade balances (raw series are monthly, in $ millions, goods only)
  { id: "fred:IMPCH", label: "fred:IMPCH — US Imports from China ($M)" },
  { id: "fred:EXPCH", label: "fred:EXPCH — US Exports to China ($M)" },
  {
    id: "fred:IMPCH - fred:EXPCH",
    label: "China",
  },
  { id: "fred:IMPCA", label: "fred:IMPCA — US Imports from Canada ($M)" },
  { id: "fred:EXPCA", label: "fred:EXPCA — US Exports to Canada ($M)" },
  {
    id: "fred:IMPCA - fred:EXPCA",
    label: "Canada",
  },
  { id: "fred:IMPMX", label: "fred:IMPMX — US Imports from Mexico ($M)" },
  { id: "fred:EXPMX", label: "fred:EXPMX — US Exports to Mexico ($M)" },
  {
    id: "fred:IMPMX - fred:EXPMX",
    label: "Mexico",
  },
  { id: "fred:IMPJP", label: "fred:IMPJP — US Imports from Japan ($M)" },
  { id: "fred:EXPJP", label: "fred:EXPJP — US Exports to Japan ($M)" },
  {
    id: "fred:IMPJP - fred:EXPJP",
    label: "Japan",
  },
  { id: "fred:IMP0003", label: "fred:IMP0003 — US Imports from EU ($M)" },
  { id: "fred:EXP0003", label: "fred:EXP0003 — US Exports to EU ($M)" },
  {
    id: "fred:IMP0003 - fred:EXP0003",
    label: "EU",
  },
  {
    id: "fred:BOPGIMP",
    label: "fred:BOPGIMP — Total US Imports of Goods ($M)",
  },
  {
    id: "fred:BOPGEXP",
    label: "fred:BOPGEXP — Total US Exports of Goods ($M)",
  },
  {
    id: "fred:BOPGIMP - fred:BOPGEXP",
    label: "Total US",
  },
];

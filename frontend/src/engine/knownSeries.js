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
  { id: "crypto:BTC-USD", label: "crypto:BTC-USD — Bitcoin (live)" },

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
    id: "fred:BAMLH0A0HYM2",
    label: "fred:BAMLH0A0HYM2 — ICE BofA High Yield Spread",
  },
];

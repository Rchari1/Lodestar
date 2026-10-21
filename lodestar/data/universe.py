"""The tradable universe for v1: liquid US-listed ETFs that all trade from before 2016.

A fixed ETF list avoids survivorship bias: none of these get dropped from an index.
"""

UNIVERSE: list[str] = [
    # US equity indices
    "SPY", "QQQ", "IWM", "DIA", "MDY",
    # US sectors (XLC is excluded: it only launched in 2018)
    "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY", "XLRE",
    # International equity
    "EFA", "EEM", "EWJ", "EWZ", "FXI", "VGK", "INDA",
    # Rates and credit
    "TLT", "IEF", "SHY", "LQD", "HYG", "TIP", "AGG", "EMB",
    # Commodities
    "GLD", "SLV", "USO", "DBC", "UNG",
    # Real estate
    "VNQ",
    # Style and factor
    "MTUM", "QUAL", "USMV", "IWF", "IWD",
]

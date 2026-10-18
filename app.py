from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Industrials Short Screener",
    layout="wide"
)

st.title("Industrials Short Screener")
st.write(
    "Explore potential short candidates using accruals, "
    "profitability, valuation, and financial distress indicators."
)

@st.cache_data
def load_data():
    path = Path(__file__).parent / "universe.csv"
    return pd.read_csv(path)

df = load_data()

st.sidebar.header("Screening filters")

sectors = sorted(df["sector"].dropna().unique())

selected_sectors = st.sidebar.multiselect(
    "Sectors to include",
    options=sectors,
    default=sectors
)

minimum_percentile = st.sidebar.slider(
    "Minimum accrual percentile",
    min_value=0,
    max_value=100,
    value=80,
    help="Higher values identify higher STA within the original sample."
)

use_z_filter = st.sidebar.checkbox(
    "Require Altman Z below cutoff",
    value=True
)

z_cutoff = st.sidebar.number_input(
    "Altman Z cutoff",
    min_value=0.0,
    value=1.81,
    step=0.1,
    format="%.2f"
)
st.sidebar.subheader("Additional filters")

use_gpa = st.sidebar.checkbox("Filter for low GPA")

gpa_max = st.sidebar.number_input(
    "Maximum GPA",
    value=0.20,
    step=0.01,
    format="%.3f"
)

use_bm = st.sidebar.checkbox("Filter for low positive B/M")

bm_max = st.sidebar.number_input(
    "Maximum positive B/M",
    min_value=0.0,
    value=0.30,
    step=0.01,
    format="%.3f"
)

use_snoa = st.sidebar.checkbox("Filter for high SNOA")

snoa_min = st.sidebar.number_input(
    "Minimum SNOA",
    value=0.70,
    step=0.01,
    format="%.3f"
)
# Apply every selected filter to the results
filtered = df[
    df["sector"].isin(selected_sectors)
    & df["accrual_percentile"].ge(minimum_percentile)
].copy()

if use_z_filter:
    filtered = filtered[
        filtered["altman_z"].notna()
        & filtered["altman_z"].lt(z_cutoff)
    ]
if use_gpa:
    filtered = filtered[
        filtered["gpa"].notna()
        & filtered["gpa"].le(gpa_max)
    ]

if use_bm:
    filtered = filtered[
        filtered["bm"].notna()
        & filtered["bm"].gt(0)
        & filtered["bm"].le(bm_max)
    ]

if use_snoa:
    filtered = filtered[
        filtered["snoa"].notna()
        & filtered["snoa"].ge(snoa_min)
    ]
filtered = filtered.sort_values(
    "accrual_percentile",
    ascending=False
)

left, middle, right = st.columns(3)

left.metric("Matching securities", len(filtered))
middle.metric(
    "Matching rows with complete metrics",
    int(filtered["data_status"].eq("Complete").sum())
)
right.metric(
    "Matching rows with missing metrics",
    int(filtered["data_status"].eq("Incomplete").sum())
)
# Label matches using the filters the user selected
filtered["signal"] = "Screen match"

filtered["screen_reason"] = filtered.apply(
    lambda row: (
        f"Accrual percentile {row['accrual_percentile']:.1f} "
        f"meets minimum {minimum_percentile}"
        + (
            f"; Altman Z {row['altman_z']:.2f} "
            f"is below {z_cutoff:.2f}"
            if use_z_filter else ""
        )
    ),
    axis=1
)
if use_gpa:
    filtered["screen_reason"] += f"; GPA <= {gpa_max:.3f}"

if use_bm:
    filtered["screen_reason"] += f"; 0 < B/M <= {bm_max:.3f}"

if use_snoa:
    filtered["screen_reason"] += f"; SNOA >= {snoa_min:.3f}"
filtered["equity_flag"] = filtered["bm"].apply(
    lambda value: (
        "Missing B/M" if pd.isna(value)
        else "Negative book equity" if value < 0
        else "Zero book equity" if value == 0
        else ""
    )
)
st.subheader("Screening results")

st.caption(
    "Matches are research candidates. These filters do not establish "
    "that a stock will decline or that shares are available to borrow."
)

columns = [
    "ticker", "company", "signal", "screen_reason",
    "gpa", "bm", "equity_flag", "sta", "snoa",
    "accrual_percentile", "altman_z",
    "fiscal_year_end", "market_data_date",
    "data_status", "missing_metrics"
]

if filtered.empty:
    st.info(
        "No companies meet these conditions. Lower the accrual "
        "percentile or turn off the Altman Z requirement to explore."
    )
else:
    st.dataframe(
        filtered[columns].round(4),
        hide_index=True,
        use_container_width=True
    )

st.download_button(
    "Download filtered results",
    data=filtered.to_csv(index=False).encode("utf-8"),
    file_name="filtered_results.csv",
    mime="text/csv"
)

with st.expander("How this screen works"):
    st.write(
        """
        - GPA: gross profit divided by year-end total assets.
        - B/M: book common equity divided by current market capitalization.
        - STA: net income minus operating cash flow, divided by
          year-end total assets.
        - SNOA: net operating assets divided by year-end total assets.
        - Accrual percentile: STA rank within the original sample,
          calculated using available values and average ranks for ties.
          It stays fixed when filters change.
        - Altman Z: the five-factor model using decimal ratios.
          The default distress cutoff is 1.81. Its applicability
          differs across industrial business models.
        - Market capitalization is a current snapshot; accounting
          figures come from each company's displayed fiscal year-end.
        - Missing values remain missing. A row is excluded when it
          lacks a metric required by an active filter.
        """
    )

st.caption(
    "Class project prototype. PMAN and final BUY/SELL classification "
    "have not yet been implemented."
)
st.divider()
st.subheader("Company detail")

if filtered.empty:
    st.info("Adjust the filters to select a company for analysis.")
else:
    selected_ticker = st.selectbox(
        "Select a company from the screening results",
        options=filtered["ticker"].tolist()
    )

    company_row = filtered.loc[
        filtered["ticker"] == selected_ticker
    ].iloc[0]

    st.write(f"**{company_row['company']} ({selected_ticker})**")
    st.write(company_row["screen_reason"])

    metric_names = {
        "gpa": "GPA",
        "bm": "B/M",
        "sta": "STA",
        "snoa": "SNOA",
        "altman_z": "Altman Z"
    }

    comparison = []

    for column, label in metric_names.items():
        # Compare B/M only among companies with positive book equity
        reference = df[column].dropna()

        if column == "bm":
            reference = reference[reference > 0]

        comparison.append({
            "Metric": label,
            "Company value": company_row[column],
            "Sample median": reference.median(),
            "Reference observations": len(reference)
        })

    st.dataframe(
        pd.DataFrame(comparison).round(4),
        hide_index=True,
        use_container_width=True
    )

    st.caption(
        "Medians use the full loaded sample, before sidebar filters. "
        "The B/M median includes only positive B/M values. "
        "Negative company B/M values indicate negative book equity "
        "and should be interpreted separately."
    )

    st.write(
        f"**Fiscal year-end:** {company_row['fiscal_year_end']}  \n"
        f"**Market data date:** {company_row['market_data_date']}"
    )

    if company_row["data_status"] == "Incomplete":
        st.warning(
            f"Missing metrics: {company_row['missing_metrics']}"
        )
st.divider()
st.subheader("Manage an existing short")

st.caption(
    "Enter prices manually using the same currency. "
    "Returns exclude borrowing fees, dividends owed, and trading costs."
)

position_ticker = st.selectbox(
    "Ticker you are shorting",
    options=sorted(df["ticker"].dropna().unique()),
    key="position_ticker"
)

entry_price = st.number_input(
    "Short-entry price per share",
    min_value=0.01,
    value=100.00,
    step=0.01
)

current_price = st.number_input(
    "Current price per share",
    min_value=0.01,
    value=100.00,
    step=0.01,
    help="Enter a current quote. This app does not fetch live prices."
)

shares = st.number_input(
    "Number of shares shorted",
    min_value=1,
    value=10,
    step=1
)

profit_target = st.number_input(
    "Profit target (% of entry value)",
    min_value=0.1,
    max_value=99.9,
    value=20.0,
    step=1.0
)

stop_loss = st.number_input(
    "Stop-loss (% of entry value)",
    min_value=0.1,
    value=10.0,
    step=1.0
)

evaluate_position = st.button("Evaluate short position")

if evaluate_position:
    pnl = (entry_price - current_price) * shares
    return_pct = (entry_price - current_price) / entry_price * 100

    target_price = entry_price * (1 - profit_target / 100)
    stop_price = entry_price * (1 + stop_loss / 100)

    col1, col2 = st.columns(2)
    col1.metric("Unrealized profit / loss before costs", f"{pnl:,.2f}")
    col2.metric("Return on entry value", f"{return_pct:.2f}%")

    st.write(f"**Position:** {position_ticker}")
    st.write(f"**Profit-target cover price:** {target_price:,.2f}")
    st.write(f"**Stop-loss cover price:** {stop_price:,.2f}")

    if current_price <= target_price:
        st.success(
            "BUY / COVER candidate: your selected profit target "
            "has been reached."
        )
    elif current_price >= stop_price:
        st.error(
            "BUY / COVER candidate: your selected stop-loss "
            "has been reached."
        )
    else:
        st.info(
            "Neither selected exit threshold has been reached."
        )

    st.caption(
        "This checks your entered prices against your chosen rules. "
        "It does not monitor prices or place orders. "
        "Return on entry value is not return on margin capital."
    )

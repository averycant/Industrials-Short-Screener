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
filtered["signal"] = "SELL candidate"

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
    "ticker", "company", "gpa", "bm", "sta", "snoa",
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

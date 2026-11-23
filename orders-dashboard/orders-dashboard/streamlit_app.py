"""
Daily Orders Dashboard
Pulls the last 4 days of orders from Snowflake, aggregates to day level,
and shows a day-over-day bar chart. No CSV — data is queried live.

Credentials come from Streamlit secrets ([snowflake] section),
which live in Streamlit Community Cloud settings — NEVER in this repo.
"""

import altair as alt
import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Config — edit these to match your Snowflake schema
# ---------------------------------------------------------------------------
ORDERS_TABLE = "ANALYTICS.PUBLIC.ORDER_DETAILS"   # fully-qualified table name
ORDER_ID_COL = "ORDER_ID"
ORDER_TS_COL = "ORDER_CREATED_AT"                 # timestamp of order placement
SOURCE_TZ = "UTC"                                 # timezone ORDER_TS_COL is stored in
REPORT_TZ = "Asia/Kolkata"                        # timezone to bucket days in
DAYS_BACK = 4                                     # keep small — avoids heavy scans
CACHE_TTL = "30m"                                 # how long query results are cached

st.set_page_config(page_title="Daily Orders", page_icon="📦", layout="centered")


@st.cache_resource(show_spinner=False)
def get_connection():
    """Build a Snowflake connection purely from Streamlit secrets ([snowflake] section)."""
    import snowflake.connector

    cfg = dict(st.secrets["snowflake"])
    params = {k: cfg[k] for k in ("account", "user", "role", "warehouse", "database", "schema") if cfg.get(k)}

    if cfg.get("private_key"):
        # Key-pair auth: convert the pasted PEM text into the DER bytes the connector expects
        from cryptography.hazmat.primitives import serialization

        pwd = cfg.get("private_key_passphrase") or None
        key = serialization.load_pem_private_key(
            cfg["private_key"].strip().encode(),
            password=pwd.encode() if pwd else None,
        )
        params["private_key"] = key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    elif cfg.get("password"):
        params["password"] = cfg["password"]
    else:
        raise ValueError("Add either private_key or password to the [snowflake] secrets.")

    params["client_session_keep_alive"] = True
    return snowflake.connector.connect(**params)


@st.cache_data(ttl=CACHE_TTL, show_spinner="Querying Snowflake…")
def load_daily_orders() -> pd.DataFrame:
    conn = get_connection()
    sql = f"""
        SELECT
            DATE(CONVERT_TIMEZONE('{SOURCE_TZ}', '{REPORT_TZ}', {ORDER_TS_COL})) AS ORDER_DATE,
            COUNT(DISTINCT {ORDER_ID_COL})                                       AS ORDERS
        FROM {ORDERS_TABLE}
        WHERE {ORDER_TS_COL} >= CONVERT_TIMEZONE(
                  '{REPORT_TZ}', '{SOURCE_TZ}',
                  DATEADD(day, -{DAYS_BACK - 1},
                          DATE(CONVERT_TIMEZONE('{REPORT_TZ}', CURRENT_TIMESTAMP())))::TIMESTAMP_NTZ
              )
        GROUP BY 1
        ORDER BY 1
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        df = cur.fetch_pandas_all()
    df.columns = [c.upper() for c in df.columns]
    df["ORDER_DATE"] = pd.to_datetime(df["ORDER_DATE"])
    df["DOD_CHANGE_PCT"] = df["ORDERS"].pct_change() * 100
    return df


st.title("📦 Orders — Day over Day")
st.caption(f"Last {DAYS_BACK} days · bucketed in {REPORT_TZ} · today is partial")

try:
    df = load_daily_orders()
except Exception as e:  # surface a clean message instead of a stack trace
    st.error(f"Could not load data from Snowflake: {e}")
    st.stop()

if df.empty:
    st.warning("No orders found in the selected window.")
    st.stop()

# KPI row
latest, prev = df.iloc[-1], (df.iloc[-2] if len(df) > 1 else None)
c1, c2, c3 = st.columns(3)
c1.metric("Total orders", f"{int(df['ORDERS'].sum()):,}")
c2.metric(
    f"Latest ({latest['ORDER_DATE']:%d %b})",
    f"{int(latest['ORDERS']):,}",
    f"{latest['DOD_CHANGE_PCT']:+.1f}% DoD" if prev is not None else None,
)
c3.metric("Daily average", f"{df['ORDERS'].mean():,.0f}")

# Bar chart
df["DAY"] = df["ORDER_DATE"].dt.strftime("%a %d %b")
base = alt.Chart(df).encode(
    x=alt.X("DAY:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
    y=alt.Y("ORDERS:Q", title="Orders placed"),
    tooltip=[
        alt.Tooltip("DAY:N", title="Day"),
        alt.Tooltip("ORDERS:Q", title="Orders", format=","),
        alt.Tooltip("DOD_CHANGE_PCT:Q", title="DoD %", format="+.1f"),
    ],
)
bars = base.mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color="#2563eb")
labels = base.mark_text(dy=-8).encode(text=alt.Text("ORDERS:Q", format=","))
st.altair_chart((bars + labels).properties(height=380), width="stretch")

with st.expander("Daily table"):
    st.dataframe(
        df[["ORDER_DATE", "ORDERS", "DOD_CHANGE_PCT"]].rename(
            columns={"ORDER_DATE": "Date", "ORDERS": "Orders", "DOD_CHANGE_PCT": "DoD %"}
        ),
        hide_index=True,
        column_config={
            "Date": st.column_config.DateColumn(format="DD MMM YYYY"),
            "DoD %": st.column_config.NumberColumn(format="%+.1f%%"),
        },
    )

if st.button("🔄 Refresh now"):
    st.cache_data.clear()
    st.rerun()

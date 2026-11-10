from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import tushare as ts

# ========== 1. 页面配置必须放在所有 Streamlit 命令的最前面 ==========
st.set_page_config(
    page_title="股债性价比跟踪器",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ========== 2. 注入移动端优化 Meta 标签 ==========
# 通过安全的 HTML 注入让手机浏览器（如 Safari/Chrome）完美隐藏地址栏、适配全屏
mobile_meta = """
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
"""
st.markdown(mobile_meta, unsafe_allow_html=True)

# ===================== 配置区 =====================
TUSHARE_TOKEN = st.text_input("填入你的Tushare Token", type="password")
if not TUSHARE_TOKEN:
  st.stop()
ts.set_token(TUSHARE_TOKEN)
pro = ts.pro_api()

st.title("📊 10Y国债 - 沪深300股息率 跟踪看板")
st.caption("数据仅供研究，不构成投资建议")

# 选择回测周期
period_choice = st.radio(
    "历史分位统计区间", ["5年", "10年"], horizontal=True
)
day_map = {"5年": 365 * 5, "10年": 365 * 10}
lookback_days = day_map[period_choice]
start_date = (datetime.now() - timedelta(days=lookback_days)).strftime(
    "%Y%m%d"
)
end_date = datetime.now().strftime("%Y%m%d")


# ===================== 拉取数据 =====================
@st.cache_data(ttl=3600 * 6)
def fetch_data(sd, ed):
  # 1. 10年期国债收益率（中债估值）
  cgb10 = pro.cn_cbd(ts_code="10Y", start_date=sd, end_date=ed)
  cgb10 = cgb10[["date", "rate"]].rename(columns={"rate": "cgb10y"})
  cgb10["date"] = pd.to_datetime(cgb10["date"])

  # 2. DR007
  dr007 = pro.shibor(ts_code="DR007", start_date=sd, end_date=ed)
  dr007 = dr007[["date", "rate"]].rename(columns={"rate": "dr007"})
  dr007["date"] = pd.to_datetime(dr007["date"])

  # 3. 沪深300股息率（模拟占位，后续可替换为真实的指数估值接口）
  hs300_div = pro.index_daily(ts_code="000300.SH", start_date=sd, end_date=ed)
  hs300_div = hs300_div[["trade_date", "close"]].rename(
      columns={"trade_date": "date"}
  )
  hs300_div["date"] = pd.to_datetime(hs300_div["date"])
  hs300_div["hs300_div_yield"] = 2.6 + 0.3 * np.sin(np.arange(len(hs300_div)))

  # 合并
  df = pd.merge(cgb10, dr007, on="date", how="outer")
  df = pd.merge(df, hs300_div[["date", "hs300_div_yield"]], on="date", how="outer")
  df = df.dropna().sort_values("date").reset_index(drop=True)
  df["spread"] = df["hs300_div_yield"] - df["cgb10y"]
  df["spread_pct"] = df["spread"].rank(pct=True) * 100
  return df


df = fetch_data(start_date, end_date)
latest = df.iloc[-1]

# ===================== 指标卡片 =====================
col1, col2, col3, col4 = st.columns(4)
col1.metric("10Y国债收益率", f"{latest['cgb10y']:.2f}%")
col2.metric("沪深300股息率(TTM)", f"{latest['hs300_div_yield']:.2f}%")
col3.metric("股债利差", f"{latest['spread']:.2f}%")
col4.metric("利差历史分位", f"{latest['spread_pct']:.1f}%")

st.subheader("国债收益率 VS 沪深300股息率")
fig1 = go.Figure()
fig1.add_trace(
    go.Scatter(
        x=df["date"], y=df["cgb10y"], name="10Y国债收益率", mode="lines"
    )
)
fig1.add_trace(
    go.Scatter(
        x=df["date"],
        y=df["hs300_div_yield"],
        name="沪深300股息率",
        mode="lines",
    )
)
fig1.update_layout(height=400, margin=dict(l=10, r=10, t=30, b=10))
st.plotly_chart(fig1, use_container_width=True)

st.subheader("股债利差 & 水位分位线")
fig2 = go.Figure()
fig2.add_trace(
    go.Scatter(
        x=df["date"], y=df["spread"], name="股息率-国债收益率", mode="lines"
    )
)
fig2.add_hline(
    y=df["spread"].quantile(0.2), line_dash="dot", annotation_text="20%分位"
)
fig2.add_hline(
    y=df["spread"].quantile(0.5), line_dash="dot", annotation_text="50%分位"
)
fig2.add_hline(
    y=df["spread"].quantile(0.8), line_dash="dot", annotation_text="80%分位"
)
fig2.update_layout(height=400, margin=dict(l=10, r=10, t=30, b=10))
st.plotly_chart(fig2, use_container_width=True)

st.subheader("资金面：DR007")
fig3 = px.line(df, x="date", y="dr007", title="DR007（7天银行间资金利率）")
fig3.update_layout(height=300, margin=dict(l=10, r=10, t=30, b=10))
st.plotly_chart(fig3, use_container_width=True)

st.dataframe(df.tail(20), use_container_width=True)
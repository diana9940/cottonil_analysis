import base64
import os
import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from plotly.subplots import make_subplots

from analysis import load_tables, summarize, quality_checks, quality_visuals, facts_text

NAVY, YELLOW, GOLD, INK = "#283C77", "#FCEA1A", "#F2B705", "#16224A"
RED, ORANGE, GREEN, BLUE = "#E5484D", "#F5A524", "#2FB67C", "#4C6FD1"
LEVEL_COLOR = {"high": RED, "medium": ORANGE, "info": BLUE, "ok": GREEN}
LEVEL_LABEL = {"high": "Needs attention", "medium": "Worth checking", "info": "Insight", "ok": "Healthy"}
MODEL = "claude-sonnet-5-5"
TABLES_FOLDER = "02_TABLES"   # the tables folder, placed next to app.py
API_KEY = ""                  # optional: paste a Claude API key here to enable free-text questions
HERE = Path(__file__).parent

st.set_page_config(page_title="Cottonil Analytics", page_icon="🧵", layout="wide", initial_sidebar_state="collapsed")

st.markdown(f"""
<style>
.stApp {{ background:#F4F6FB; }}
.block-container {{ padding-top:1.4rem; max-width:1250px; }}
@keyframes fadeUp {{ from {{opacity:0; transform:translateY(16px)}} to {{opacity:1; transform:none}} }}
@keyframes slide {{ to {{ background-position:-200% 0 }} }}
@keyframes pulse {{ 0%,100% {{ box-shadow:0 0 0 0 rgba(229,72,77,.45) }} 50% {{ box-shadow:0 0 0 9px rgba(229,72,77,0) }} }}
.hero {{ background:linear-gradient(120deg,{NAVY},#1d2c5c); border-radius:18px; padding:20px 30px;
        display:flex; align-items:center; gap:26px; position:relative; overflow:hidden; animation:fadeUp .7s both; }}
.hero:after {{ content:""; position:absolute; left:0; bottom:0; width:100%; height:5px;
              background:linear-gradient(90deg,{YELLOW},#fff,{YELLOW}); background-size:200% 100%; animation:slide 3s linear infinite; }}
.hero img {{ height:76px; border-radius:8px; }}
.hero h1 {{ color:#fff; margin:0; font-size:1.8rem; font-weight:800; }}
.hero p {{ color:#cfd7f4; margin:4px 0 0; }}
.note {{ background:#fff; border-left:5px solid {YELLOW}; border-radius:10px; padding:10px 16px; margin:14px 0 4px;
        color:{INK}; font-size:.92rem; box-shadow:0 2px 10px rgba(40,60,119,.07); animation:fadeUp .8s both; }}
.grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; margin:8px 0 18px; }}
.hcard {{ background:#fff; border-radius:16px; padding:18px 20px; border-top:6px solid var(--c); position:relative;
         box-shadow:0 4px 16px rgba(40,60,119,.09); animation:fadeUp .7s both; transition:transform .25s, box-shadow .25s; }}
.hcard:hover {{ transform:translateY(-5px); box-shadow:0 10px 26px rgba(40,60,119,.18); }}
.hcard .tag {{ font-size:.72rem; font-weight:700; letter-spacing:.04em; text-transform:uppercase; color:var(--c); }}
.hcard .big {{ font-size:2.2rem; font-weight:800; color:{NAVY}; line-height:1.15; margin:4px 0 2px; }}
.hcard .ttl {{ font-weight:700; color:{INK}; }}
.hcard .cap {{ color:#5b678f; font-size:.88rem; }}
.dot {{ position:absolute; top:16px; right:16px; width:11px; height:11px; border-radius:50%; background:var(--c); }}
.hcard.high .dot {{ animation:pulse 1.8s infinite; }}
.stTabs [data-baseweb="tab-list"] {{ gap:6px; }}
.stTabs [data-baseweb="tab"] {{ background:#fff; border-radius:10px 10px 0 0; padding:8px 18px; font-weight:600; }}
.stTabs [aria-selected="true"] {{ background:{NAVY}; color:#fff !important; }}
.stTabs [aria-selected="true"] p {{ color:#fff !important; }}
.stButton>button {{ border-radius:20px; border:2px solid {NAVY}; color:{NAVY}; font-weight:600; transition:all .2s; }}
.stButton>button:hover {{ background:{NAVY}; color:#fff; transform:translateY(-2px); }}
.answer {{ background:#fff; border-radius:14px; padding:16px 20px; border-left:6px solid {NAVY}; animation:fadeUp .5s both; }}
@media (max-width:800px) {{ .grid {{ grid-template-columns:1fr; }} .hero h1 {{ font-size:1.3rem; }} }}
</style>
""", unsafe_allow_html=True)


def style(fig, h=380, legend="top"):
    fig.update_layout(height=h, template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(color=INK), margin=dict(l=10, r=10, t=50, b=10), title_font_size=16,
                      legend=dict(orientation="h", x=1, xanchor="right", y=1.02, yanchor="bottom", title_text=""))
    if legend == "bottom":
        fig.update_layout(legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.05, yanchor="top", title_text=""),
                          margin=dict(l=10, r=10, t=50, b=60))
    return fig


@st.cache_data(show_spinner="Reading the tables and crunching the numbers (about a minute the first time)...")
def run(folder):
    t = load_tables(folder)
    s = summarize(t)
    q = quality_checks(t, s)
    v = quality_visuals(t, s)
    return s, q, v, facts_text(s, q)


def kpi_cards(items):
    cards = "".join(
        f'<div class="k" style="animation-delay:{i * 0.12}s"><div class="l">{lab}</div>'
        f'<div class="v" data-t="{val}" data-d="{dec}" data-p="{pre}" data-s="{suf}">0</div></div>'
        for i, (lab, val, dec, pre, suf) in enumerate(items))
    html = f"""
    <style>
      body{{margin:0;font-family:'Segoe UI',Arial,sans-serif}}
      .row{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}}
      .k{{background:linear-gradient(135deg,{NAVY},#1d2c5c);border-radius:16px;padding:18px 20px;color:#fff;
          border-bottom:5px solid {YELLOW};animation:up .7s both;transition:transform .25s}}
      .k:hover{{transform:translateY(-5px)}}
      .l{{font-size:.8rem;letter-spacing:.05em;text-transform:uppercase;color:#cfd7f4}}
      .v{{font-size:2rem;font-weight:800;margin-top:6px;color:{YELLOW}}}
      @keyframes up{{from{{opacity:0;transform:translateY(16px)}}to{{opacity:1;transform:none}}}}
      @media(max-width:700px){{.row{{grid-template-columns:1fr 1fr}}}}
    </style>
    <div class="row">{cards}</div>
    <script>
      document.querySelectorAll('.v').forEach(el=>{{
        const t=+el.dataset.t,d=+el.dataset.d,p=el.dataset.p,s=el.dataset.s,T=1400,t0=performance.now();
        const f=n=>p+n.toLocaleString('en-US',{{minimumFractionDigits:d,maximumFractionDigits:d}})+s;
        const step=now=>{{const x=Math.min((now-t0)/T,1),e=1-Math.pow(1-x,3);el.textContent=f(t*e);if(x<1)requestAnimationFrame(step)}};
        requestAnimationFrame(step);
      }});
    </script>"""
    if hasattr(st, "iframe"):
        st.iframe(html, height=115)
    else:
        components.html(html, height=115)


# ------------------------------------------------------------------- header
logo = base64.b64encode((HERE / "assets" / "logo.png").read_bytes()).decode()
st.markdown(f"""<div class="hero"><img src="data:image/png;base64,{logo}">
<div><h1>Sales &amp; Data Health Dashboard</h1>
<p>8 years of retail data · 80 branches · 24 tables</p></div></div>""", unsafe_allow_html=True)

folder = next((p for p in (HERE / TABLES_FOLDER, Path.cwd() / TABLES_FOLDER) if p.is_dir()), None)
if folder is None:
    st.error(f"The folder '{TABLES_FOLDER}' was not found. Put it next to app.py.")
    st.stop()
try:
    s, quality, vis, facts = run(str(folder))
except Exception as e:
    st.error(f"Could not read the tables: {e}")
    st.stop()

fyears = s["full_years"]
st.markdown('<div class="note">All amounts are in EGP and <b>nominal</b>: unit prices rose about 5x since 2019, '
            'so read sales growth together with units sold. Partial years are excluded.</div>', unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Overview", "Categories & Channels", "Branches", "Data Health", "Ask the Data"])

# ----------------------------------------------------------------- overview
with tab1:
    lo, hi = st.select_slider("Years", options=fyears, value=(fyears[0], fyears[-1]))
    y = s["yearly"]
    yf = y[(y["year"] >= lo) & (y["year"] <= hi) & y["full_year"]]
    kpi_cards([("Net sales (EGP)", yf["net_sales"].sum() / 1e6, 1, "", "M"),
               ("Units sold", yf["units"].sum(), 0, "", ""),
               ("Avg order value (EGP)", yf["net_sales"].sum() / yf["orders"].sum(), 0, "", ""),
               ("Gross margin", yf["margin"].sum() / yf["net_sales"].sum() * 100, 1, "", "%")])

    m = s["monthly"]
    m = m[~m["partial"] & (m["month"].dt.year >= lo) & (m["month"].dt.year <= hi)]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=m["month"], y=m["net_sales"], name="Net sales (EGP)", fill="tozeroy",
                             line=dict(color=NAVY, width=2.5), fillcolor="rgba(40,60,119,.15)"), secondary_y=False)
    fig.add_trace(go.Scatter(x=m["month"], y=m["units"], name="Units sold",
                             line=dict(color=GOLD, width=2.5)), secondary_y=True)
    fig.update_layout(title="Monthly sales vs units sold")
    fig.update_yaxes(rangemode="tozero", tickformat="~s")
    fig.update_yaxes(title_text="Net sales (EGP)", secondary_y=False)
    fig.update_yaxes(title_text="Units sold", secondary_y=True)
    st.plotly_chart(style(fig, 400), width="stretch")

    idx = vis["index"]
    idx = idx[(idx["year"] >= lo) & (idx["year"] <= hi)]
    base = idx["year"].min()
    idx = idx.assign(**{c: idx[c] / idx[c].iloc[0] * 100 for c in ["Net sales", "Units sold", "Price per unit"]})
    fig = px.line(idx.melt("year", var_name="Metric", value_name="Index"), x="year", y="Index", color="Metric",
                  markers=True, color_discrete_map={"Net sales": NAVY, "Units sold": GOLD, "Price per unit": RED},
                  title=f"Price vs volume (index, {base} = 100)")
    fig.update_xaxes(dtick=1)
    st.plotly_chart(style(fig, 360), width="stretch")
    st.caption("Sales grew far faster than units because the price of the same products kept rising.")

# ------------------------------------------------- categories and channels
with tab2:
    cy, cat, ch = s["cat_year"], s["category"], s["channel"]
    order = cat["category_en"].tolist()
    fig = px.bar(cy.sort_values("year"), x="net_line_EGP", y="category_en", animation_frame="year", orientation="h",
                 category_orders={"category_en": order}, range_x=[0, cy["net_line_EGP"].max() * 1.1],
                 color_discrete_sequence=[NAVY], hover_data={"share_pct": ":.1f"},
                 title="Net sales by category, year by year",
                 labels={"net_line_EGP": "Net sales (EGP)", "category_en": "", "share_pct": "Share of sales (%)"})
    fig.layout.updatemenus = [dict(type="buttons", direction="left", x=1, xanchor="right", y=1.1, yanchor="bottom",
                                   showactive=False, bgcolor=YELLOW, font=dict(color=INK),
                                   buttons=[dict(label="Watch it grow", method="animate",
                                                 args=[None, dict(frame=dict(duration=900), transition=dict(duration=500))])])]
    style(fig, 580)
    fig.update_layout(margin=dict(l=10, r=10, t=90, b=10))
    st.plotly_chart(fig, width="stretch")
    st.caption("Every category grows several times over, because prices rose across the board. "
               "Hover over a bar to see that each category's share of sales barely changes.")

    l, r = st.columns(2)
    c2 = cat.melt("category_en", ["sales_share_pct", "units_share_pct"], var_name="m", value_name="v")
    c2["m"] = c2["m"].map({"sales_share_pct": "Share of sales", "units_share_pct": "Share of units"})
    fig = px.bar(c2, y="category_en", x="v", color="m", barmode="group", orientation="h",
                 category_orders={"category_en": order},
                 color_discrete_map={"Share of sales": NAVY, "Share of units": GOLD},
                 title="Sales vs units share by category", labels={"v": "%", "category_en": ""})
    l.plotly_chart(style(fig, 620), width="stretch")
    fig = px.pie(ch, names="sales_channel", values="net_sales", hole=.55, title="Sales by channel",
                 color_discrete_sequence=[NAVY, GOLD, BLUE])
    fig.update_traces(textinfo="percent")
    r.plotly_chart(style(fig, 420, "bottom"), width="stretch")
    fig = px.bar(ch, x="sales_channel", y="avg_order_value", color_discrete_sequence=[NAVY],
                 title="Average order value by channel (EGP)", labels={"sales_channel": "", "avg_order_value": "EGP"})
    st.plotly_chart(style(fig, 320), width="stretch")
    big = ch.sort_values("avg_order_value").iloc[-1]
    st.caption(f"Average order value and share of total sales answer different questions: {big['sales_channel']} orders are the "
               f"largest ({big['avg_order_value']:,.0f} EGP on average) but make up only {big['orders'] / ch['orders'].sum() * 100:.0f}% of all orders.")

# ------------------------------------------------------------------ branches
with tab3:
    br = s["branch"]
    fig = px.treemap(br, path=[px.Constant("Egypt"), "governorate_ar", "branch_name_ar"], values="net_sales",
                     color="profit_before_payroll", color_continuous_scale=[[0, "#E3E8F7"], [1, NAVY]], labels={"profit_before_payroll": "Profit (EGP)"},
                     title="Branches by governorate (size = sales, color = profit before payroll)")
    st.plotly_chart(style(fig, 520), width="stretch")
    spread = (br["net_sales"].max() / br["net_sales"].min() - 1) * 100
    st.markdown(f'<div class="note">The gap between the top and bottom branch is only <b>{spread:.0f}%</b> in sales: '
                'branches perform very similarly. Profit here is before payroll (payroll data is incomplete).</div>',
                unsafe_allow_html=True)
    l, r = st.columns(2)
    top = br.head(10).iloc[::-1]
    bot = br.tail(10).iloc[::-1]
    l.plotly_chart(style(px.bar(top, x="net_sales", y="branch_name_ar", orientation="h", title="Top 10 by sales",
                                color_discrete_sequence=[NAVY], labels={"net_sales": "EGP", "branch_name_ar": ""}), 420), width="stretch")
    r.plotly_chart(style(px.bar(bot, x="net_sales", y="branch_name_ar", orientation="h", title="Bottom 10 by sales",
                                color_discrete_sequence=[GOLD], labels={"net_sales": "EGP", "branch_name_ar": ""}), 420), width="stretch")

# --------------------------------------------------------------- data health
with tab4:
    cards = "".join(
        f'<div class="hcard {q["level"]}" style="--c:{LEVEL_COLOR[q["level"]]};animation-delay:{i * 0.1}s">'
        f'<span class="dot"></span><div class="tag">{LEVEL_LABEL[q["level"]]}</div>'
        f'<div class="big">{q["metric"]}</div><div class="ttl">{q["title"]}</div><div class="cap">{q["caption"]}</div></div>'
        for i, q in enumerate(quality))
    st.markdown(f'<div class="grid">{cards}</div>', unsafe_allow_html=True)

    l, r = st.columns(2)
    pr = vis["payroll"]
    fig = px.bar(pr, x="year", y="employees", color_discrete_sequence=[NAVY], title="Employees paid per year")
    fig.add_vline(x=max(fyears) + 0.5, line_dash="dot", line_color=RED)
    fig.update_xaxes(dtick=1)
    l.plotly_chart(style(fig, 360), width="stretch")
    l.caption("Paid headcount falls while sales keep growing: payroll data is incomplete.")

    sp = vis["returns_split"]
    fig = px.pie(sp, names="group", values="count", hole=.6, title="Where the returns sit",
                 color_discrete_sequence=[GREEN, RED])
    fig.update_traces(textinfo="percent")
    r.plotly_chart(style(fig, 360, "bottom"), width="stretch")
    r.caption("Almost all returns belong to orders whose status does not say 'returned'.")

    l, r = st.columns(2)
    bd = vis["branch_dates"].sort_values("opening_date").reset_index(drop=True)
    fig = go.Figure()
    for _, row in bd.iterrows():
        fig.add_trace(go.Scatter(x=[row["first_order"], row["opening_date"]], y=[row["branch_name_ar"]] * 2,
                                 mode="lines", line=dict(color="#c5cce6", width=2), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=bd["first_order"], y=bd["branch_name_ar"], mode="markers", name="First order",
                             marker=dict(color=RED, size=7)))
    fig.add_trace(go.Scatter(x=bd["opening_date"], y=bd["branch_name_ar"], mode="markers", name="Official opening date",
                             marker=dict(color=NAVY, size=7)))
    fig.update_layout(title="First order vs official opening date, per branch", yaxis=dict(showticklabels=False))
    l.plotly_chart(style(fig, 420, "bottom"), width="stretch")
    l.caption("Every branch sells long before its opening date.")

    miss = vis["missing_pct"]
    fig = px.pie(names=["With customer ID", "No customer ID"], values=[100 - miss, miss], hole=.6,
                 title="Orders with a customer ID", color_discrete_sequence=[NAVY, ORANGE])
    fig.update_traces(textinfo="percent")
    r.plotly_chart(style(fig, 420, "bottom"), width="stretch")

# ---------------------------------------------------------------- ask the data
def answers():
    cat, yr, br, ch, m = s["category"], s["yearly"], s["branch"], s["channel"], s["monthly"]
    yr = yr[yr["full_year"]]
    a, z = yr.iloc[0], yr.iloc[-1]
    t3 = cat.head(3)
    out = {}
    out["Top categories"] = (f"**{', '.join(t3['category_en'])}** drive **{t3['sales_share_pct'].sum():.0f}%** of sales. "
                             f"{cat.sort_values('units', ascending=False).iloc[0]['category_en']} sells the most units "
                             f"({cat['units_share_pct'].max():.0f}% of units) but at a low price, so it ranks lower by value.")
    out["Is growth real?"] = (f"Between {int(a['year'])} and {int(z['year'])} net sales grew **x{z['net_sales'] / a['net_sales']:.1f}**, "
                              f"units only **x{z['units'] / a['units']:.1f}**, while the price per unit grew **x{z['avg_unit_price'] / a['avg_unit_price']:.1f}**. "
                              "Most of the growth in EGP comes from higher prices, not from selling more.")
    out["Best branches"] = (f"Top branch: **{br.iloc[0]['branch_name_ar']}** ({br.iloc[0]['net_sales'] / 1e6:.1f}M EGP). "
                            f"Lowest: **{br.iloc[-1]['branch_name_ar']}** ({br.iloc[-1]['net_sales'] / 1e6:.1f}M EGP). "
                            f"The gap is only {(br['net_sales'].max() / br['net_sales'].min() - 1) * 100:.0f}%, so branches are very similar.")
    big = ch.sort_values("avg_order_value", ascending=False).iloc[0]
    out["Channels"] = (f"{big['sales_channel']} orders average **{big['avg_order_value']:,.0f} EGP**, "
                       f"{big['avg_order_value'] / ch['avg_order_value'].min():.1f}x the smallest channel, and bring "
                       f"{big['sales_share_pct']:.0f}% of sales. Return rates are about the same in every channel "
                       f"({ch['return_rate_pct'].min():.1f}% to {ch['return_rate_pct'].max():.1f}%).")
    mm = m[~m["partial"] & m["month"].dt.year.isin(fyears)].copy()
    mm["mo"], mm["yr"] = mm["month"].dt.month, mm["month"].dt.year
    sh = (mm.pivot_table(index="mo", columns="yr", values="net_sales", aggfunc="sum")
          .pipe(lambda d: d / d.sum() * 100).mean(axis=1).sort_values(ascending=False))
    names = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun", 7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}
    out["Seasonality"] = (f"Strongest months: **{names[sh.index[0]]}** and **{names[sh.index[1]]}** "
                          f"(about {sh.iloc[0]:.1f}% and {sh.iloc[1]:.1f}% of yearly sales). Weakest: **{names[sh.index[-1]]}** ({sh.iloc[-1]:.1f}%). "
                          "The pattern repeats every year. Part of the late-year peak is the general growth inside each year.")
    rr = (ch["orders"] * ch["return_rate_pct"]).sum() / ch["orders"].sum()
    out["Returns"] = (f"About **{rr:.1f}%** of orders have a return. "
                      "The order status field shows a much lower number, so this figure comes from the returns table.")
    return out


with tab5:
    st.markdown("Pick a question. Answers are computed straight from the data.")
    ans = answers()
    cols = st.columns(4)
    for i, q in enumerate(ans):
        if cols[i % 4].button(q, key=q, width="stretch"):
            st.session_state["picked"] = q
    if "picked" in st.session_state:
        st.markdown(f'<div class="answer"><b>{st.session_state["picked"]}</b><br><br>{re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", ans[st.session_state["picked"]])}</div>',
                    unsafe_allow_html=True)

    key = API_KEY or os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        st.divider()
        q = st.text_input("Or ask your own question (English or Arabic)")
        if q:
            try:
                import anthropic
                resp = anthropic.Anthropic(api_key=key).messages.create(
                    model=MODEL, max_tokens=900,
                    system=("You are a data analyst for Cottonil, a retail apparel chain. Answer briefly, in the language of the question, "
                            "using ONLY the numbers below; if the answer is not in them, say so. Amounts are nominal EGP. "
                            "Never claim the company is profitable or loss-making after payroll, because payroll data is incomplete. "
                            "Mention data-quality issues when they affect the answer.\n\nDATA:\n" + facts),
                    messages=[{"role": "user", "content": q}])
                st.markdown("".join(b.text for b in resp.content if b.type == "text"))
            except Exception as e:
                st.error(f"Claude did not respond: {e}")
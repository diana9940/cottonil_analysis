"""Cottonil analysis: load tables, summarize, check data quality, build AI context."""
from pathlib import Path
import pandas as pd

FILES = {
    "sales_orders": ["sales_order_id", "order_date", "branch_id", "customer_id",
                     "sales_channel", "net_before_tax_EGP", "status"],
    "sales_order_items": ["sales_line_id", "sales_order_id", "order_date", "branch_id",
                          "product_id", "quantity", "net_line_EGP", "margin_EGP"],
    "products_catalog": ["product_id", "category_en"],
    "branches": ["branch_id", "branch_name_ar", "governorate_ar", "opening_date"],
    "sales_returns": ["sales_order_id", "sales_line_id", "return_quantity", "refund_amount_EGP"],
    "operating_expenses": ["expense_date", "branch_or_department_id", "amount_EGP"],
    "payroll": ["employee_id", "pay_month", "net_paid_EGP"],
    "employees": ["employee_id", "branch_id", "hire_date"],
}
DATE_COLS = {
    "sales_orders": ["order_date"], "sales_order_items": ["order_date"],
    "branches": ["opening_date"], "operating_expenses": ["expense_date"],
    "payroll": ["pay_month"], "employees": ["hire_date"],
}


def load_tables(folder):
    """Read only the needed columns from each CSV (keeps memory low)."""
    folder = Path(folder)
    tables = {}
    for name, cols in FILES.items():
        df = pd.read_csv(folder / f"{name}.csv", usecols=cols)
        for c in DATE_COLS.get(name, []):
            df[c] = pd.to_datetime(df[c])
        tables[name] = df
    return tables


def full_years(orders):
    """Years fully covered by the data (first/last year are usually partial)."""
    d0, d1 = orders["order_date"].min(), orders["order_date"].max()
    years = list(range(d0.year, d1.year + 1))
    if d0 > pd.Timestamp(d0.year, 1, 3):
        years.remove(d0.year)
    if d1 < pd.Timestamp(d1.year, 12, 28) and d1.year in years:
        years.remove(d1.year)
    return years


def summarize(t):
    o, it = t["sales_orders"], t["sales_order_items"]
    fy = full_years(o)
    it = it.merge(t["products_catalog"], on="product_id", how="left", validate="m:1")
    it["year"] = it["order_date"].dt.year
    it["month"] = it["order_date"].dt.to_period("M").dt.to_timestamp()

    # Monthly (flag the partial first/last month so charts can drop them)
    monthly = it.groupby("month").agg(net_sales=("net_line_EGP", "sum"),
                                      units=("quantity", "sum"),
                                      margin=("margin_EGP", "sum"))
    om = o.groupby(o["order_date"].dt.to_period("M").dt.to_timestamp()).size()
    monthly["orders"] = om
    d0, d1 = o["order_date"].min(), o["order_date"].max()
    monthly["partial"] = False
    if d0.day > 1:
        monthly.loc[d0.to_period("M").to_timestamp(), "partial"] = True
    if d1 != d1 + pd.offsets.MonthEnd(0):
        monthly.loc[d1.to_period("M").to_timestamp(), "partial"] = True
    monthly = monthly.reset_index()

    # Yearly
    yearly = it.groupby("year").agg(net_sales=("net_line_EGP", "sum"),
                                    units=("quantity", "sum"),
                                    margin=("margin_EGP", "sum"))
    yearly["orders"] = o.groupby(o["order_date"].dt.year).size()
    yearly["avg_order_value"] = yearly["net_sales"] / yearly["orders"]
    yearly["avg_unit_price"] = yearly["net_sales"] / yearly["units"]
    yearly["margin_pct"] = yearly["margin"] / yearly["net_sales"] * 100
    yearly["full_year"] = yearly.index.isin(fy)
    yearly = yearly.reset_index()

    itf = it[it["year"].isin(fy)]

    # Category
    cat = itf.groupby("category_en").agg(net_sales=("net_line_EGP", "sum"),
                                         units=("quantity", "sum"),
                                         margin=("margin_EGP", "sum"))
    cat["sales_share_pct"] = cat["net_sales"] / cat["net_sales"].sum() * 100
    cat["units_share_pct"] = cat["units"] / cat["units"].sum() * 100
    cat["margin_pct"] = cat["margin"] / cat["net_sales"] * 100
    cat["avg_unit_price"] = cat["net_sales"] / cat["units"]
    cat = cat.sort_values("net_sales", ascending=False).reset_index()

    cy = it[it["year"].isin(fy)].groupby(["year", "category_en"])["net_line_EGP"].sum().reset_index()
    cy["share_pct"] = cy["net_line_EGP"] / cy.groupby("year")["net_line_EGP"].transform("sum") * 100

    # Branch (before payroll: margin - branch expenses)
    exp = t["operating_expenses"]
    exp = exp[exp["branch_or_department_id"].str.startswith("BR")
              & exp["expense_date"].dt.year.isin(fy)]
    br = itf.groupby("branch_id").agg(net_sales=("net_line_EGP", "sum"),
                                      margin=("margin_EGP", "sum"))
    br["expenses"] = exp.groupby("branch_or_department_id")["amount_EGP"].sum()
    br["expenses"] = br["expenses"].fillna(0)
    br["profit_before_payroll"] = br["margin"] - br["expenses"]
    br = br.join(t["branches"].set_index("branch_id")[["branch_name_ar", "governorate_ar"]])
    br = br.sort_values("net_sales", ascending=False).reset_index()

    # Channel
    of = o[o["order_date"].dt.year.isin(fy)].copy()
    of["has_return"] = of["sales_order_id"].isin(t["sales_returns"]["sales_order_id"])
    ch = of.groupby("sales_channel").agg(orders=("sales_order_id", "count"),
                                         net_sales=("net_before_tax_EGP", "sum"),
                                         return_rate_pct=("has_return", "mean"))
    ch["return_rate_pct"] *= 100
    ch["avg_order_value"] = ch["net_sales"] / ch["orders"]
    ch["sales_share_pct"] = ch["net_sales"] / ch["net_sales"].sum() * 100
    ch = ch.reset_index()

    return {"monthly": monthly, "yearly": yearly, "category": cat,
            "branch": br, "channel": ch, "cat_year": cy, "full_years": fy}


def quality_checks(t, s):
    """Data-health cards: title, level, big metric, one-line caption."""
    o, b, r = t["sales_orders"], t["branches"], t["sales_returns"]
    out = []

    first = o.groupby("branch_id")["order_date"].min().rename("first_order")
    chk = b.merge(first, on="branch_id")
    n = int((chk["first_order"] < chk["opening_date"]).sum())
    out.append(dict(key="opening", title="Orders before branch opening", level="high" if n else "ok",
                    metric=f"{n}/{len(chk)}", caption="branches sell before their opening_date"))

    flagged = set(o.loc[o["status"] == "Partially returned", "sales_order_id"])
    not_flagged = int((~r["sales_order_id"].isin(flagged)).sum())
    share = not_flagged / max(len(r), 1) * 100
    out.append(dict(key="status", title="Order status vs returns table", level="high" if share > 20 else "ok",
                    metric=f"{share:.0f}%", caption="of returns sit on orders not flagged as returned"))

    p = t["payroll"].copy()
    p["year"] = p["pay_month"].dt.year
    hc = p.groupby("year")["employee_id"].nunique()
    fy = s["full_years"]
    last_fy = fy[-1] if fy else int(hc.index.max())
    out.append(dict(key="payroll", title="Payroll coverage", level="high" if hc.get(last_fy, 0) < 0.8 * hc.max() else "ok",
                    metric=f"{int(hc.max())} → {int(hc.get(last_fy, 0))}",
                    caption=f"employees paid: peak vs {last_fy}"))

    miss = o["customer_id"].isna().mean() * 100
    out.append(dict(key="customers", title="Orders without a customer", level="medium" if miss > 5 else "ok",
                    metric=f"{miss:.0f}%", caption="customer analysis covers the rest only"))

    m = r.merge(t["sales_order_items"][["sales_line_id", "net_line_EGP"]], on="sales_line_id", how="left", validate="1:1")
    ratio = m["refund_amount_EGP"] / m["net_line_EGP"]
    n_over = int((ratio > 1.15).sum())
    out.append(dict(key="refund", title="Refund above line value", level="medium" if n_over else "ok",
                    metric=f"{n_over:,}", caption="refunds exceed 115% of the line value"))

    y = s["yearly"]
    y = y[y["full_year"]]
    if len(y) >= 2:
        a_, z = y.iloc[0], y.iloc[-1]
        out.append(dict(key="price", title="Growth comes from price", level="info",
                        metric=f"×{z['avg_unit_price'] / a_['avg_unit_price']:.1f}",
                        caption=f"unit price {int(a_['year'])}-{int(z['year'])} (units ×{z['units'] / a_['units']:.1f})"))
    return out


def quality_visuals(t, s):
    """Small tables used to draw the data-health charts."""
    o, b, r = t["sales_orders"], t["branches"], t["sales_returns"]
    p = t["payroll"].copy()
    p["year"] = p["pay_month"].dt.year
    hc = p.groupby("year")["employee_id"].nunique().rename("employees").reset_index()
    flagged = set(o.loc[o["status"] == "Partially returned", "sales_order_id"])
    on_flag = int(r["sales_order_id"].isin(flagged).sum())
    split = pd.DataFrame({"group": ["Returns on flagged orders", "Returns on other orders"],
                          "count": [on_flag, len(r) - on_flag]})
    first = o.groupby("branch_id")["order_date"].min().rename("first_order")
    bd = b.merge(first, on="branch_id")
    y = s["yearly"]
    y = y[y["full_year"]].copy()
    base = y.iloc[0]
    idx = pd.DataFrame({"year": y["year"],
                        "Net sales": y["net_sales"] / base["net_sales"] * 100,
                        "Units sold": y["units"] / base["units"] * 100,
                        "Price per unit": y["avg_unit_price"] / base["avg_unit_price"] * 100})
    miss = float(o["customer_id"].isna().mean() * 100)
    return {"payroll": hc, "returns_split": split, "branch_dates": bd, "index": idx, "missing_pct": miss}


def facts_text(s, quality):
    """Compact text with all the numbers the AI assistant may use."""
    def f(df, n=None):
        d = (df if n is None else df.head(n)).copy()
        for c in d.select_dtypes("number").columns:
            d[c] = d[c].round(2)
        return d.to_csv(index=False)

    m = s["monthly"]
    m = m[~m["partial"]]
    br = s["branch"]
    parts = [
        "Notes: all amounts are in EGP and nominal (prices rose ~5x since 2019). "
        f"Full years: {s['full_years']}; the first and last years in the data are partial. "
        "Branch profit here = gross margin - branch operating expenses, BEFORE payroll.",
        "## Data quality findings\n" + "\n".join(f"- {q['title']}: {q['metric']} ({q['caption']})" for q in quality),
        "## سنوي\n" + f(s["yearly"]),
        "## شهري (بدون الشهور الناقصة)\n" + f(m),
        "## الفئات\n" + f(s["category"]),
        "## القنوات\n" + f(s["channel"]),
        "## الفروع (مرتبة بالمبيعات، السنين الكاملة)\n" + f(br),
    ]
    return "\n\n".join(parts)
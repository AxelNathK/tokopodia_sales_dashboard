# streamlit_app.py
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

st.set_page_config(page_title="Tokopedia Sales Dashboard (2022)", layout="wide")

# ----------------------
# Helper: load & prepare data (cached)
# ----------------------
@st.cache_data
def load_data(path: str):
    df = pd.read_excel(path)
    df.columns = df.columns.str.strip()
    # parse dates
    df['order_date'] = pd.to_datetime(df['order_date'], errors='coerce')
    if 'registered_date' in df.columns:
        df['registered_date'] = pd.to_datetime(df.get('registered_date'), errors='coerce')
    # numeric conversions
    for c in ['price','qty_ordered','before_discount','discount_amount','after_discount','cogs']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    # computed fields
    if all(col in df.columns for col in ['before_discount','cogs','qty_ordered']):
        df['net_profit'] = df['before_discount'] - (df['cogs'] * df['qty_ordered'])
    else:
        df['net_profit'] = (df.get('price',0) * df.get('qty_ordered',0)) - (df.get('cogs',0) * df.get('qty_ordered',0))
    if 'is_valid' in df.columns:
        df['is_valid'] = pd.to_numeric(df['is_valid'], errors='coerce').fillna(0).astype(int)
    # time keys
    df['year'] = df['order_date'].dt.year
    df['month'] = df['order_date'].dt.month
    df['month_name'] = df['order_date'].dt.strftime('%Y-%m')
    return df

# ----------------------
# Main
# ----------------------
st.title("Tokopedia — Sales Dashboard (2022)")
st.markdown("Interactive dashboard to monitor Value Sales, Net Profit and AOV. Use the filters in the sidebar.")

# Path to Excel (file must be in same folder or provide full path)
DEFAULT_PATH = "Copy of finalProj_df.xlsx"
excel_path = Path(DEFAULT_PATH)
if not excel_path.exists():
    st.error(f"Data file not found: {DEFAULT_PATH}. Please place the Excel file in the same folder as this app.")
    st.stop()

df = load_data(str(excel_path))

# Sidebar filters
st.sidebar.header("Filters")
years = sorted(df['year'].dropna().unique().astype(int).tolist())
default_year = 2022 if 2022 in years else (years[-1] if years else None)
selected_year = st.sidebar.selectbox("Year", options=years, index=(years.index(default_year) if default_year in years else 0))
categories = ["All"] + sorted(df['category'].dropna().unique().astype(str).tolist())
selected_category = st.sidebar.selectbox("Category", options=categories, index=0)
payments = ["All"] + sorted(df['payment_method'].dropna().unique().astype(str).tolist())
selected_payment = st.sidebar.selectbox("Payment Method", options=payments, index=0)
value_transaction = st.sidebar.selectbox("Value Transaction", options=["All","Valid","Not Valid"], index=0)

# Apply filters
df_f = df.copy()
df_f = df_f[df_f['year'] == int(selected_year)]
if selected_category != "All":
    df_f = df_f[df_f['category'].astype(str) == selected_category]
if selected_payment != "All":
    df_f = df_f[df_f['payment_method'].astype(str) == selected_payment]
if value_transaction == "Valid":
    df_f = df_f[df_f['is_valid'] == 1]
elif value_transaction == "Not Valid":
    df_f = df_f[df_f['is_valid'] == 0]

# Tabs: Dashboard (page1) and Product Analysis (page2)
tab1, tab2 = st.tabs(["Dashboard Penjualan (2022)", "Analisis Produk"])

with tab1:
    st.header("Sales Trend (Monthly)")
    # Monthly aggregation
    monthly_orders = df_f.groupby('month_name')['id'].nunique().rename('unique_orders')
    monthly_metrics = df_f.groupby('month_name').agg({'before_discount':'sum','net_profit':'sum'}).join(monthly_orders)
    monthly_metrics['AOV'] = monthly_metrics['before_discount'] / monthly_metrics['unique_orders']
    monthly_metrics = monthly_metrics.sort_index()
    if monthly_metrics.empty:
        st.info("No data available for selected filters.")
    else:
        # Scorecards for the filtered period
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Before Discount (Total)", f"{monthly_metrics['before_discount'].sum():,.0f}")
        col2.metric("After Discount (Est.)", f"{df_f['after_discount'].sum():,.0f}" if 'after_discount' in df_f.columns else "N/A")
        col3.metric("Net Profit (Total)", f"{monthly_metrics['net_profit'].sum():,.0f}")
        col4.metric("Total Quantity", f"{df_f['qty_ordered'].sum():,.0f}")
        col5.metric("Unique Orders", f"{df_f['id'].nunique():,.0f}")
        
        # Matplotlib combined plot: before_discount & net_profit with secondary axis for AOV
        fig, ax = plt.subplots(figsize=(10,4))
        x = monthly_metrics.index
        ax.plot(x, monthly_metrics['before_discount'], marker='o', label='Value Sales (before_discount)')
        ax.plot(x, monthly_metrics['net_profit'], marker='o', label='Net Profit')
        ax.set_xlabel("Month (YYYY-MM)")
        ax.set_ylabel("Value (currency)")
        ax.tick_params(axis='x', rotation=45)
        ax2 = ax.twinx()
        ax2.plot(x, monthly_metrics['AOV'], marker='s', linestyle='--', label='AOV')
        ax2.set_ylabel("AOV (currency)")
        # legends
        lines, labels = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines + lines2, labels + labels2, loc='upper left')
        st.pyplot(fig)
        
    st.markdown("**Insight & Call to Action**:")
    st.write("- Jelaskan singkat tren yang terlihat dan rekomendasi (misal: tingkatkan promosi di bulan dengan penjualan rendah).")

with tab2:
    st.header("Product-level Summary")
    # Product aggregation
    prod_agg = df_f.groupby(['sku_id','sku_name','category']).agg({
        'before_discount':'sum',
        'after_discount':'sum',
        'net_profit':'sum',
        'qty_ordered':'sum',
        'customer_id': pd.Series.nunique
    }).rename(columns={'customer_id':'unique_customers'}).reset_index()
    prod_agg = prod_agg.sort_values('before_discount', ascending=False)
    
    # Top KPI scorecards
    total_before = prod_agg['before_discount'].sum()
    total_after = prod_agg['after_discount'].sum() if 'after_discount' in prod_agg.columns else 0
    total_net = prod_agg['net_profit'].sum()
    total_qty = prod_agg['qty_ordered'].sum()
    unique_customers = df_f['customer_id'].nunique()
    aov_overall = (df_f['before_discount'].sum() / df_f['id'].nunique()) if df_f['id'].nunique()>0 else np.nan
    
    sc1, sc2, sc3, sc4, sc5 = st.columns([1,1,1,1,1])
    sc1.metric("Total Before Discount", f"{total_before:,.0f}")
    sc2.metric("Total After Discount", f"{total_after:,.0f}")
    sc3.metric("Total Net Profit", f"{total_net:,.0f}")
    sc4.metric("Total Quantity", f"{total_qty:,.0f}")
    sc5.metric("AOV (overall)", f"{aov_overall:,.2f}")
    
    st.subheader("Top Products (table)")
    st.dataframe(prod_agg[['sku_name','category','before_discount','after_discount','net_profit','qty_ordered','unique_customers']].rename(columns={
        'sku_name':'Product Name','qty_ordered':'Qty','unique_customers':'Unique Customers','before_discount':'Before Discount','after_discount':'After Discount','net_profit':'Net Profit'
    }).reset_index(drop=True), use_container_width=True)
    
    # Additional: Top categories chart
    cat_agg = prod_agg.groupby('category').agg({'before_discount':'sum'}).sort_values('before_discount', ascending=False).reset_index()
    fig2, axb = plt.subplots(figsize=(6,3))
    axb.bar(cat_agg['category'].astype(str), cat_agg['before_discount'])
    axb.set_title("Sales by Category (filtered)")
    axb.set_xticklabels(cat_agg['category'], rotation=45, ha='right')
    st.pyplot(fig2)
    
    # Bonus: mobile & tablet paid via JazzWallet
    st.subheader("Mobile & Tablet paid via JazzWallet (2022)")
    mask_cat = df_f['category'].astype(str).str.lower().str.contains('mobile|tablet')
    mask_pay = df_f['payment_method'].astype(str).str.lower().str.contains('jazz')
    mask_valid = df_f['is_valid'] == 1 if 'is_valid' in df_f.columns else True
    df_mobile_jazz = df_f[mask_cat & mask_pay & mask_valid].copy()
    if df_mobile_jazz.empty:
        st.info("No Mobile & Tablet transactions paid via JazzWallet for selected filters.")
    else:
        qty_sum = int(df_mobile_jazz['qty_ordered'].sum())
        uniq_cust = int(df_mobile_jazz['customer_id'].nunique())
        st.write(f"Total Quantity: **{qty_sum}**  \nUnique Customers: **{uniq_cust}**")
        mob_month = df_mobile_jazz.groupby('month_name').agg({'qty_ordered':'sum'}).sort_index()
        fig3, ax3 = plt.subplots(figsize=(8,3))
        ax3.bar(mob_month.index, mob_month['qty_ordered'])
        ax3.set_title("Quantity by Month (Mobile & Tablet via JazzWallet)")
        ax3.set_xticklabels(mob_month.index, rotation=45)
        st.pyplot(fig3)

st.markdown("---")
st.markdown("**Notes:** Data used is synthetic/fictitious for the exercise. This app was generated to meet the UTS Data Visualization requirements.")
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import os
import streamlit as st

st.write("FILES IN APP FOLDER:", os.listdir())

required_files = [
    "scm_order_lines.csv",
    "scm_inventory_positions.csv",
    "scm_forecast.csv",
    "scm_po_receipts.csv"
]

for file in required_files:
    if not os.path.exists(file):
        st.error(f"Missing file: {file}")
        st.stop()


st.set_page_config(layout="wide")

st.title("📦 Supply Chain Risk Dashboard")

orders = pd.read_csv("SCM_Dashboard/scm_order_lines.csv",
                     parse_dates=["order_date","ship_date","promised_delivery_date"])

inv = pd.read_csv("SCM_Dashboard/scm_inventory_positions.csv",
                  parse_dates=["date","next_po_eta"])

forecast = pd.read_csv("SCM_Dashboard/scm_forecast.csv",
                       parse_dates=["date"])

po = pd.read_csv("SCM_Dashboard/scm_po_receipts.csv",
                 parse_dates=["eta_date"])

# ---------------- KPI SECTION ----------------
orders["fill_rate"] = orders["delivered_qty"] / orders["ordered_qty"]
orders["otif"] = (orders["delivered_qty"] >= orders["ordered_qty"]) & \
                 (orders["ship_date"] <= orders["promised_delivery_date"])

col1, col2 = st.columns(2)
col1.metric("Overall Fill Rate", f"{orders['fill_rate'].mean():.1%}")
col2.metric("Average OTIF", f"{orders['otif'].mean():.1%}")

st.divider()

# ---------------- OTIF BY CARRIER ----------------
st.subheader("🚚 OTIF % by Carrier")

carrier_otif = orders.groupby("carrier")["otif"].mean().sort_values(ascending=False)

fig1, ax1 = plt.subplots()
carrier_otif.plot(kind="bar", ax=ax1)
ax1.set_title("OTIF % by Carrier")
st.pyplot(fig1, use_container_width=True)

st.divider()

# ---------------- DAYS OF SUPPLY ----------------
st.subheader("📦 Days of Supply Trend")

forecast["forecast_demand"] = forecast["forecast_demand"].replace(0, 1)
dos = inv.merge(forecast, on=["date","sku"], how="left")
dos["dos"] = dos["on_hand"] / dos["forecast_demand"]

mean_demand = forecast.groupby("sku")["forecast_demand"].mean().reset_index(name="mean_daily_demand")
dos = dos.merge(mean_demand, on="sku", how="left")
dos["critical_threshold"] = dos["safety_stock"] / dos["mean_daily_demand"]
dos["low_dos_flag"] = dos["dos"] < dos["critical_threshold"]

sku_choice = st.selectbox("Select SKU", sorted(dos["sku"].unique()))
subset = dos[dos["sku"] == sku_choice]

fig2, ax2 = plt.subplots()
for wh in subset["warehouse"].unique():
    ax2.plot(subset[subset["warehouse"]==wh]["date"],
             subset[subset["warehouse"]==wh]["dos"],
             label=wh)

ax2.axhline(1, linestyle="--", color="red")
ax2.set_title("Days of Supply Trend")
plt.legend(loc="upper right")   # Move legend to clear space
plt.grid(True, alpha=0.3)       # Light grid for readability
plt.tight_layout()     
ax2.legend()
st.pyplot(fig2, use_container_width=True)

st.divider()

# ---------------- STOCKOUT RISK ----------------
st.subheader("📉 Stockout Risk Window")

dos = dos.merge(po[["sku","eta_date","lead_time_days"]], on="sku", how="left")

dos["stockout_risk"] = (dos["dos"] < dos["lead_time_days"]) & (dos["eta_date"] > dos["date"])

risk_table = (
    dos[dos["stockout_risk"]]
    .groupby(["sku","warehouse"])
    .agg(earliest_stockout=("date","min"),
         next_po_eta=("eta_date","first"),
         min_dos=("dos","min"))
    .reset_index()
)

if not risk_table.empty:
    col1, col2 = st.columns(2)
    sku_choice = col1.selectbox("Select SKU at Risk", sorted(risk_table["sku"].unique()))
    wh_choice = col2.selectbox("Select Warehouse",
                               sorted(risk_table[risk_table["sku"]==sku_choice]["warehouse"].unique()))

    example = dos[(dos["sku"]==sku_choice) & (dos["warehouse"]==wh_choice)]

    fig3, ax3 = plt.subplots(figsize=(10,5))
    ax3.plot(example["date"], example["dos"], linewidth=2, label="Days of Supply")
    ax3.axhline(example["lead_time_days"].iloc[0], linestyle="--", color="red", label="Lead Time")

    ax3.set_title("Stockout Risk Window")
    ax3.set_xlabel("Date")
    ax3.set_ylabel("Days of Supply")
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    st.pyplot(fig3, use_container_width=True)

    # -------- Risk Severity --------
    st.subheader("🚨 Stockout Risk Summary")

    def risk_level(row):
        if row["min_dos"] < 1:
            return "🔴 High Risk"
        elif row["min_dos"] < 3:
            return "🟠 Medium Risk"
        else:
            return "🟢 Low Risk"

    risk_table["Risk Level"] = risk_table.apply(risk_level, axis=1)

    st.metric("SKU-Warehouse Pairs at Risk", risk_table.shape[0])

    st.dataframe(
        risk_table.sort_values("earliest_stockout")[[
            "sku", "warehouse", "earliest_stockout", "next_po_eta", "min_dos", "Risk Level"
        ]],
        use_container_width=True,
        height=400
    )

    st.caption("Created by Panneer☺️")

else:
    st.success("No stockout risks detected 🎉")


    

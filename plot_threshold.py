import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("/tmp/h2.csv")
df = df[df["mode"] == "hybrid"]

for d in sorted(df["distance"].unique()):
    sub = df[df["distance"] == d]
    plt.plot(sub["sigma"], sub["ler"], marker='o', label=f"d={d}")

plt.xlabel("Sigma (CV noise)")
plt.ylabel("Logical Error Rate")
plt.title("Hybrid CV-Discrete Threshold Curve")
plt.legend()
plt.grid(True)
plt.savefig("threshold_plot.png", dpi=300)

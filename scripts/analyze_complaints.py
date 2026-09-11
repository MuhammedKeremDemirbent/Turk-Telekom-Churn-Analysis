import polars as pl
import json
from pathlib import Path

df = pl.read_parquet('data/model_cache/customer_complaints_features.parquet')

# En çok şikayet alınan kategoriler
category_counts = (
    df.group_by("problem_category")
    .agg(
        pl.len().alias("count"),
        pl.col("customer_id").n_unique().alias("unique_customers"),
        pl.col("chat_message_count").mean().alias("avg_chat_messages")
    )
    .sort("count", descending=True)
    .head(10)
)

print("Kategoriler:")
for row in category_counts.iter_rows(named=True):
    print(f"  {row['problem_category']}: {row['count']} şikayet, {row['unique_customers']} müşteri")

# En çok şikayet eden müşteriler (top şikayet sayısı dağılımı)
customer_complaint_totals = (
    df.group_by("customer_id")
    .agg(pl.len().alias("total_complaints"))
    .sort("total_complaints", descending=True)
)
print(f"\nToplam şikayetçi müşteri: {customer_complaint_totals.height}")
print(f"En fazla şikayet: {customer_complaint_totals['total_complaints'].max()}")
print(f"Ortalama şikayet: {customer_complaint_totals['total_complaints'].mean():.2f}")

# Alt kategoriler
subcat_counts = (
    df.group_by(["problem_category", "problem_subcategory"])
    .agg(pl.len().alias("count"))
    .sort("count", descending=True)
    .head(15)
)
print("\nAlt kategoriler (top 15):")
for row in subcat_counts.iter_rows(named=True):
    print(f"  {row['problem_category']} / {row['problem_subcategory']}: {row['count']}")

# JSON için veri hazırla
result = {
    "categories": category_counts["problem_category"].to_list(),
    "counts": category_counts["count"].to_list(),
    "unique_customers": category_counts["unique_customers"].to_list(),
}
print("\nJSON verisi hazır")
print(json.dumps(result, ensure_ascii=False, indent=2)[:500])

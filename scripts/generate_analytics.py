import json
from pathlib import Path
import polars as pl
import numpy as np

DATA_DIR = Path(r"C:\Users\kerem\Desktop\capsstone\data")
CACHE_DIR = DATA_DIR / "model_cache"

def main():
    print("1. Parquet verileri yükleniyor...")
    spending_df = pl.read_parquet(CACHE_DIR / "customer_spending.parquet")

    # month_index hesaplama
    spending_lf = (
        spending_df
        .with_columns(
            (
                pl.col("billing_year_month")
                .str.slice(0, 4)
                .cast(pl.Int32) * 12
                +
                pl.col("billing_year_month")
                .str.slice(4, 2)
                .cast(pl.Int32)
            ).alias("month_index")
        )
        .sort(["customer_id", "month_index"])
        .with_columns(
            pl.col("month_index")
            .diff()
            .over("customer_id")
            .alias("month_difference")
        )
    )

    print("2. Aylık Aktif Müşteri ve Değişim Oranları hesaplanıyor...")
    monthly_customer_change = (
        spending_lf
        .group_by("billing_year_month")
        .agg(
            pl.col("customer_id")
            .n_unique()
            .alias("customer_count")
        )
        .sort("billing_year_month")
        .with_columns(
            pl.col("customer_count")
            .shift(1)
            .alias("previous_customer_count")
        )
        .with_columns([
            (
                (
                    pl.col("customer_count")
                    / pl.col("previous_customer_count")
                ) - 1
            ).mul(100).alias("change_percent"),
        ])
    )

    # Convert to python list
    billing_months = monthly_customer_change["billing_year_month"].to_list()
    # Format months as YYYY-MM
    formatted_months = [f"{m[:4]}-{m[4:]}" for m in billing_months]
    customer_counts = monthly_customer_change["customer_count"].to_list()
    change_rates = monthly_customer_change["change_percent"].to_list()
    # Handle first None
    if len(change_rates) > 0:
        change_rates[0] = 0.0
    change_rates = [round(float(r), 2) for r in change_rates]

    print("3. Finansal Profil ve Kaybedilen Müşteri tespiti yapılıyor...")
    dataset_bounds = (
        spending_lf
        .select(
            pl.col("month_index").min().alias("first_month_index"),
            pl.col("month_index").max().alias("last_month_index"),
        )
        .row(0, named=True)
    )
    last_month_index = dataset_bounds["last_month_index"]

    customer_finance = (
        spending_lf
        .group_by("customer_id")
        .agg([
            pl.col("month_index").min().alias("first_active_month_index"),
            pl.col("month_index").max().alias("last_active_month_index"),
            pl.col("billing_year_month").min().alias("first_active_month"),
            pl.col("billing_year_month").max().alias("last_active_month"),
            pl.col("billing_year_month").n_unique().alias("active_month_count"),
            (pl.col("month_difference") > 1).sum().alias("return_count"),
            pl.col("bill_amount").sum().alias("historical_total_paid"),
            pl.col("bill_amount").mean().alias("lifetime_average_bill"),
            pl.col("bill_amount").median().alias("lifetime_median_bill"),
            pl.col("bill_amount").sort_by("month_index").last().alias("last_bill"),
            pl.col("bill_amount").sort_by("month_index").tail(3).mean().alias("last_3_month_average_bill"),
        ])
    )

    lost_customers = (
        customer_finance
        .filter(pl.col("last_active_month_index") < last_month_index)
        .with_columns(
            (last_month_index - pl.col("last_active_month_index")).alias("lost_month_count")
        )
        .with_columns([
            (pl.col("last_3_month_average_bill") * pl.col("lost_month_count")).alias("total_estimated_revenue_loss"),
            pl.when(pl.col("return_count") == 0)
            .then(pl.lit("Doğrudan ayrılan"))
            .when(pl.col("return_count") == 1)
            .then(pl.lit("Bir kez dönüp ayrılan"))
            .otherwise(pl.lit("Birden fazla dönüp ayrılan"))
            .alias("customer_segment_tr"),
        ])
    )

    print("4. Segmentlere Göre Kayıp verisi hesaplanıyor...")
    segment_revenue_summary = (
        lost_customers
        .group_by("customer_segment_tr")
        .agg([
            pl.len().alias("lost_customer_count"),
            pl.col("last_3_month_average_bill").mean().alias("average_bill_before_departure"),
            pl.col("total_estimated_revenue_loss").sum().alias("total_estimated_revenue_loss"),
        ])
        .sort("total_estimated_revenue_loss") # Ascending order for horizontal chart
    )

    segments = segment_revenue_summary["customer_segment_tr"].to_list()
    segment_lost_counts = segment_revenue_summary["lost_customer_count"].to_list()
    segment_avg_bills = [round(float(x), 2) for x in segment_revenue_summary["average_bill_before_departure"].to_list()]
    segment_rev_losses = [round(float(x), 2) for x in segment_revenue_summary["total_estimated_revenue_loss"].to_list()]

    print("5. Kohortlara Göre Kayıp ve Gelir Kaybı hesaplanıyor...")
    monthly_departure_summary = (
        lost_customers
        .group_by("last_active_month")
        .agg([
            pl.len().alias("lost_customer_count"),
            pl.col("total_estimated_revenue_loss").sum().alias("total_estimated_revenue_loss"),
        ])
        .sort("last_active_month")
    )

    cohort_months = monthly_departure_summary["last_active_month"].to_list()
    formatted_cohort_months = [f"{m[:4]}-{m[4:]}" for m in cohort_months]
    cohort_lost_counts = monthly_departure_summary["lost_customer_count"].to_list()
    cohort_revenue_losses = [round(float(x), 2) for x in monthly_departure_summary["total_estimated_revenue_loss"].to_list()]

    # Save to JSON cache
    analytics_data = {
        "monthly_active": {
            "months": formatted_months,
            "counts": customer_counts,
            "rates": change_rates
        },
        "segment_loss": {
            "segments": segments,
            "counts": segment_lost_counts,
            "avg_bills": segment_avg_bills,
            "rev_losses": segment_rev_losses
        },
        "cohort_loss": {
            "months": formatted_cohort_months,
            "counts": cohort_lost_counts,
            "rev_losses": cohort_revenue_losses
        }
    }

    output_path = CACHE_DIR / "dashboard_analytics.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(analytics_data, f, ensure_ascii=False)

    print(f"Başarılı! Analitik verileri başarıyla kaydedildi: {output_path.name}")

if __name__ == "__main__":
    main()

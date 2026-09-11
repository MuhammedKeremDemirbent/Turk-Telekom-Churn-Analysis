import polars as pl
import json
from pathlib import Path

ANALYTICS_PATH = Path("data/model_cache/dashboard_analytics.json")
data = json.loads(ANALYTICS_PATH.read_text(encoding="utf-8"))

df = pl.read_parquet('data/model_cache/customer_complaints_features.parquet')

# Türkçe kategori adları
CAT_LABELS = {
    "billing": "Fatura",
    "data": "Veri Kullanımı",
    "coverage": "Sinyal/Kapsama",
    "voice": "Ses/Arama",
    "connectivity": "Bağlantı",
    "speed": "İnternet Hızı",
    "sim_device": "SIM/Cihaz",
    "equipment": "Ekipman",
    "roaming": "Roaming",
    "installation": "Kurulum"
}

category_counts = (
    df.group_by("problem_category")
    .agg(
        pl.len().alias("count"),
        pl.col("customer_id").n_unique().alias("unique_customers"),
    )
    .sort("count", descending=True)
    .head(10)
)

cats_en = category_counts["problem_category"].to_list()
cats_tr = [CAT_LABELS.get(c, c) for c in cats_en]

data["complaint_categories"] = {
    "labels_en": cats_en,
    "labels_tr": cats_tr,
    "counts": category_counts["count"].to_list(),
    "unique_customers": category_counts["unique_customers"].to_list(),
}

ANALYTICS_PATH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
print("dashboard_analytics.json guncellendi!")
print("Kategoriler:", cats_tr)

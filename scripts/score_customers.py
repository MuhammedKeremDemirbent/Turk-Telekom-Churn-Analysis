"""
Müşteri Churn Risk Skorlama Scripti
Bu script, model_cache içerisindeki Parquet dosyalarından yararlanarak 
churn tahmin modelini eğitir ve tüm aktif müşteriler (202509 snapshot) için 
churn olasılık skorlarını db.sqlite3 veritabanına yazar.
"""

from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd
import polars as pl

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.linear_model import LogisticRegression

# Sabitler
DATA_DIR = Path(r"C:\Users\kerem\Desktop\capsstone\data")
CACHE_DIR = DATA_DIR / "model_cache"
DB_PATH = Path(r"C:\Users\kerem\Desktop\capsstone\db.sqlite3")

SPENDING_CACHE = CACHE_DIR / "customer_spending.parquet"
COMPLAINT_CACHE = CACHE_DIR / "customer_complaints_features.parquet"
CUSTOMER_CACHE = CACHE_DIR / "customer.parquet"

OBSERVATION_MONTHS = 6
CHURN_HORIZON_MONTHS = 3
RANDOM_STATE = 42

def month_to_index(year_month: str) -> int:
    year = int(year_month[:4])
    month = int(year_month[4:])
    return year * 12 + month

# Parquet veri okuma (LazyFrame)
spending_lf = pl.scan_parquet(SPENDING_CACHE).with_columns(
    (
        pl.col("billing_year_month").str.slice(0, 4).cast(pl.Int32) * 12
        + pl.col("billing_year_month").str.slice(4, 2).cast(pl.Int32)
    ).alias("month_index")
)

complaints_lf = pl.scan_parquet(COMPLAINT_CACHE).with_columns(
    (
        pl.col("billing_year_month").str.slice(0, 4).cast(pl.Int32) * 12
        + pl.col("billing_year_month").str.slice(4, 2).cast(pl.Int32)
    ).alias("month_index")
)

customers_lf = pl.scan_parquet(CUSTOMER_CACHE)

def build_churn_snapshot(snapshot_month: str, include_label: bool = True) -> pl.DataFrame:
    snapshot_index = month_to_index(snapshot_month)
    observation_start = snapshot_index - OBSERVATION_MONTHS + 1
    snapshot_year = int(snapshot_month[:4])

    # Aktif müşteriler
    eligible_lf = (
        spending_lf
        .filter(pl.col("month_index") == snapshot_index)
        .group_by("customer_id")
        .agg(
            pl.col("bill_amount").last().alias("current_bill"),
            pl.col("data_usage").last().alias("current_data_usage"),
        )
    )

    # Son 6 aylık davranış
    spending_features_lf = (
        spending_lf
        .filter(pl.col("month_index").is_between(observation_start, snapshot_index))
        .group_by("customer_id")
        .agg(
            pl.col("bill_amount").mean().alias("bill_mean_6m"),
            pl.col("bill_amount").std().alias("bill_std_6m"),
            pl.col("bill_amount").filter(pl.col("month_index") >= snapshot_index - 2).mean().alias("bill_mean_3m"),
            pl.col("data_usage").mean().alias("usage_mean_6m"),
            pl.col("data_usage").std().alias("usage_std_6m"),
            pl.col("data_usage").filter(pl.col("month_index") >= snapshot_index - 2).mean().alias("usage_mean_3m"),
            pl.col("bill_amount").filter(pl.col("month_index") == snapshot_index - 1).first().alias("previous_bill"),
            pl.col("data_usage").filter(pl.col("month_index") == snapshot_index - 1).first().alias("previous_data_usage"),
            pl.col("month_index").n_unique().alias("active_months_6m"),
        )
    )

    # Şikayet davranışı
    complaint_features_lf = (
        complaints_lf
        .filter(pl.col("month_index").is_between(observation_start, snapshot_index))
        .group_by("customer_id")
        .agg(
            pl.len().alias("complaint_count_6m"),
            pl.col("billing_year_month").filter(pl.col("month_index") >= snapshot_index - 2).count().alias("complaint_count_3m"),
            pl.col("problem_category").n_unique().alias("unique_problem_categories_6m"),
            pl.col("chat_message_count").sum().alias("chat_message_count_6m"),
        )
    )

    snapshot_lf = (
        eligible_lf
        .join(spending_features_lf, on="customer_id", how="left")
        .join(complaint_features_lf, on="customer_id", how="left")
        .join(customers_lf, on="customer_id", how="left")
        .with_columns(
            pl.col("complaint_count_6m", "complaint_count_3m", "unique_problem_categories_6m", "chat_message_count_6m").fill_null(0),
            (OBSERVATION_MONTHS - pl.col("active_months_6m")).alias("inactive_months_6m"),
            (pl.col("current_bill") - pl.col("previous_bill")).alias("bill_change_1m"),
            (pl.col("current_data_usage") - pl.col("previous_data_usage")).alias("usage_change_1m"),
            (snapshot_year - pl.col("birth_year")).alias("age"),
            pl.lit(snapshot_month).alias("snapshot_month"),
        )
    )

    if include_label:
        future_activity_lf = (
            spending_lf
            .filter(pl.col("month_index").is_between(snapshot_index + 1, snapshot_index + CHURN_HORIZON_MONTHS))
            .group_by("customer_id")
            .agg(pl.col("month_index").n_unique().alias("future_active_months"))
        )

        snapshot_lf = (
            snapshot_lf
            .join(future_activity_lf, on="customer_id", how="left")
            .with_columns(pl.col("future_active_months").fill_null(0))
            .with_columns((pl.col("future_active_months") == 0).cast(pl.Int8).alias("churn"))
            .drop("future_active_months")
        )

    return snapshot_lf.collect(engine="streaming")

def main():
    print("1. Veriler yükleniyor ve snapshot'lar oluşturuluyor...")
    
    # Model eğitim verileri
    train_snapshots = ["202312", "202403", "202406", "202412"]
    train_dfs = []
    for s in train_snapshots:
        print(f"   Eğitim snapshot'ı çekiliyor: {s}")
        train_dfs.append(build_churn_snapshot(s, include_label=True))
    train_df = pl.concat(train_dfs)
    
    # Hedef tahmin ayımız (202509 - En son veri)
    target_snapshot = "202509"
    print(f"   Hedef tahmin snapshot'ı çekiliyor (tüm müşteriler): {target_snapshot}")
    target_df = build_churn_snapshot(target_snapshot, include_label=False)
    
    print(f"   Test veri kümesi çekiliyor (etiketlerle): {target_snapshot}")
    test_df = build_churn_snapshot(target_snapshot, include_label=True)

    # Pandas formatına dönüştürme
    NUMERIC_FEATURES = [
        "current_bill", "current_data_usage", "previous_bill", "previous_data_usage",
        "bill_mean_3m", "bill_mean_6m", "bill_std_6m", "usage_mean_3m", "usage_mean_6m",
        "usage_std_6m", "active_months_6m", "inactive_months_6m", "bill_change_1m",
        "usage_change_1m", "complaint_count_3m", "complaint_count_6m",
        "unique_problem_categories_6m", "chat_message_count_6m", "age",
    ]
    CATEGORICAL_FEATURES = ["city"]
    
    X_train = pd.DataFrame(train_df.select(NUMERIC_FEATURES + CATEGORICAL_FEATURES).to_dict(as_series=False))
    y_train = train_df.get_column("churn").to_numpy().ravel()
    
    X_target = pd.DataFrame(target_df.select(NUMERIC_FEATURES + CATEGORICAL_FEATURES).to_dict(as_series=False))
    target_ids = target_df.get_column("customer_id").to_numpy().ravel()

    print("2. Model hattı kuruluyor ve eğitiliyor (Logistic Regression - Balanced)...")
    numeric_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])

    categorical_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("one_hot", OneHotEncoder(handle_unknown="ignore", sparse_output=True)),
    ])

    preprocessor = ColumnTransformer([
        ("numeric", numeric_pipeline, NUMERIC_FEATURES),
        ("categorical", categorical_pipeline, CATEGORICAL_FEATURES),
    ])

    model_pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", LogisticRegression(class_weight="balanced", random_state=RANDOM_STATE, max_iter=1000)),
    ])

    model_pipeline.fit(X_train, y_train)
    print("   Model başarıyla eğitildi.")

    print("3. Aktif müşteriler için churn risk skorları tahmin ediliyor...")
    churn_probabilities = model_pipeline.predict_proba(X_target)[:, 1]

    # Risk gruplarına ayırma
    # >= 0.70 -> Yüksek
    # >= 0.40 -> Orta
    # < 0.40 -> Düşük
    risk_groups = []
    for prob in churn_probabilities:
        if prob >= 0.70:
            risk_groups.append("Yüksek")
        elif prob >= 0.40:
            risk_groups.append("Orta")
        else:
            risk_groups.append("Düşük")

    scoring_results = pd.DataFrame({
        "customer_id": target_ids,
        "churn_probability": churn_probabilities,
        "churn_risk_group": risk_groups
    })

    print(f"4. Skorlar SQLite veritabanına ({DB_PATH.name}) kaydediliyor...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Tabloyu oluşturma
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customer_churn (
        customer_id INTEGER PRIMARY KEY,
        churn_probability REAL,
        churn_risk_group TEXT
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_customer_churn_id ON customer_churn (customer_id)")
    
    # Eski kayıtları temizleme
    cursor.execute("DELETE FROM customer_churn")
    conn.commit()

    # Bulk insert
    records = scoring_results.values.tolist()
    cursor.executemany("INSERT INTO customer_churn VALUES (?, ?, ?)", records)
    conn.commit()
    conn.close()

    print(f"Başarılı! Toplam {len(records)} aktif müşteri için churn risk skorları veritabanına kaydedildi.")

    # 5. Model Değerlendirme Eğrilerini Hesaplama ve Kaydetme
    print("5. Model performans değerlendirme eğrileri hesaplanıyor...")
    from sklearn.metrics import roc_curve, precision_recall_curve
    from sklearn.calibration import calibration_curve
    import json
    
    X_test = pd.DataFrame(test_df.select(NUMERIC_FEATURES + CATEGORICAL_FEATURES).to_dict(as_series=False))
    y_test = test_df.get_column("churn").to_numpy().ravel()
    test_scores = model_pipeline.predict_proba(X_test)[:, 1]
    
    # ROC
    fpr, tpr, _ = roc_curve(y_test, test_scores)
    step_roc = max(1, len(fpr) // 50)
    roc_data = {
        "fpr": [round(float(x), 4) for x in fpr[::step_roc].tolist()],
        "tpr": [round(float(x), 4) for x in tpr[::step_roc].tolist()]
    }
    if len(roc_data["fpr"]) > 0 and roc_data["fpr"][-1] != 1.0:
        roc_data["fpr"].append(1.0)
        roc_data["tpr"].append(1.0)
        
    # PR
    precision, recall, _ = precision_recall_curve(y_test, test_scores)
    step_pr = max(1, len(precision) // 50)
    pr_data = {
        "precision": [round(float(x), 4) for x in precision[::step_pr].tolist()],
        "recall": [round(float(x), 4) for x in recall[::step_pr].tolist()],
        "baseline": round(float(y_test.mean()), 4)
    }
    
    # Calibration
    observed_rate, predicted_rate = calibration_curve(y_test, test_scores, n_bins=10, strategy="quantile")
    cal_data = {
        "observed": [round(float(x), 4) for x in observed_rate.tolist()],
        "predicted": [round(float(x), 4) for x in predicted_rate.tolist()]
    }
    
    curves_data = {
        "roc": roc_data,
        "pr": pr_data,
        "calibration": cal_data
    }
    
    with open(CACHE_DIR / "evaluation_curves.json", "w", encoding="utf-8") as f:
        json.dump(curves_data, f)
    print("   Değerlendirme eğrileri başarıyla kaydedildi (evaluation_curves.json).")

if __name__ == "__main__":
    main()

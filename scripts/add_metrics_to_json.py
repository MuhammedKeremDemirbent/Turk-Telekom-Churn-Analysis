import json
from pathlib import Path

CURVES_PATH = Path("data/model_cache/evaluation_curves.json")

data = json.loads(CURVES_PATH.read_text(encoding="utf-8"))

# --- Model Metrikleri (Test seti: 202509 snapshot, 81.204 müşteri) ---
data["model_metrics"] = {
    # Olasılık metrikleri
    "pr_auc": 0.081228,         # Average Precision (PR-AUC)
    "roc_auc": 0.680579,        # ROC-AUC
    "brier_score": 0.219979,    # Brier Score (düşük = iyi)
    "log_loss": 0.638209,       # Log-Loss (düşük = iyi)
    "prevalence": 0.037917,     # Test seti churn oranı (%3.79)

    # Sıralama / hedefleme metrikleri (Top-K)
    "topk": [
        {
            "k_percent": 1,
            "selected": 813,
            "true_churn": 129,
            "precision": 0.158672,
            "recall": 0.041897,
            "lift": 4.184725,
            "revenue_capture": 0.037524
        },
        {
            "k_percent": 5,
            "selected": 4061,
            "true_churn": 456,
            "precision": 0.112288,
            "recall": 0.148100,
            "lift": 2.961417,
            "revenue_capture": 0.138234
        },
        {
            "k_percent": 10,
            "selected": 8121,
            "true_churn": 810,
            "precision": 0.099741,
            "recall": 0.263072,
            "lift": 2.630530,
            "revenue_capture": 0.248358
        },
        {
            "k_percent": 20,
            "selected": 16241,
            "true_churn": 1265,
            "precision": 0.077889,
            "recall": 0.410848,
            "lift": 2.054213,
            "revenue_capture": 0.387554
        }
    ],

    # Metodoloji açıklaması
    "methodology": {
        "approach": "Aylık Snapshot Tabanlı Churn Tahmini",
        "observation_window": "6 ay (son 6 aya ait finansal & şikayet davranışı)",
        "churn_horizon": "3 ay (snapshot sonrası 3 ay içinde hiç aktif olmayan = churn)",
        "model": "Logistic Regression (class_weight=balanced)",
        "train_snapshots": ["Aralık 2023", "Mart 2024", "Haziran 2024"],
        "validation_snapshot": "Aralık 2024",
        "test_snapshot": "Eylül 2025",
        "features": [
            "Son 6 ay ortalama fatura (bill_mean_6m)",
            "Son 3 ay ortalama fatura (bill_mean_3m)",
            "Fatura standart sapması (bill_std_6m)",
            "Son 6 ay veri kullanımı (usage_mean_6m)",
            "Son 3 ay veri kullanımı (usage_mean_3m)",
            "Aylık fatura değişimi (bill_change_1m)",
            "Aylık kullanım değişimi (usage_change_1m)",
            "Son 6 ayda aktif ay sayısı (active_months_6m)",
            "Son 6 ay şikayet sayısı (complaint_count_6m)",
            "Son 3 ay şikayet sayısı (complaint_count_3m)",
            "Şikayet kategori çeşitliliği",
            "Destek mesajı sayısı (chat_message_count_6m)",
            "Yaş (age)",
            "Şehir (city)"
        ]
    }
}

CURVES_PATH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
print("evaluation_curves.json guncellendi!")
print(f"Anahtar listesi: {list(data.keys())}")

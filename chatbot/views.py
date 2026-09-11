import json
import logging
import sqlite3
from pathlib import Path

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .service import create_chatbot


logger = logging.getLogger(__name__)


def index(request):
    db_path = Path(__file__).resolve().parent.parent / "db.sqlite3"
    context = {}
    
    if db_path.exists():
        try:
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            
            # 1. Churn Risk Groups
            c.execute("SELECT churn_risk_group, COUNT(*) FROM customer_churn GROUP BY churn_risk_group")
            risk_counts = dict(c.fetchall())
            context["risk_dist"] = {
                "Düşük": risk_counts.get("Düşük", 0) + risk_counts.get("Dük", 0),  # Dük is written as Düşük in frontend
                "Orta": risk_counts.get("Orta", 0),
                "Yüksek": risk_counts.get("Yüksek", 0)
            }
            
            # 2. Churn by City (Top 7)
            c.execute("""
                SELECT c.city, AVG(cc.churn_probability) 
                FROM customer c 
                JOIN customer_churn cc ON c.customer_id = cc.customer_id 
                GROUP BY c.city 
                ORDER BY AVG(cc.churn_probability) DESC 
                LIMIT 7
            """)
            city_data = c.fetchall()
            context["city_labels"] = [row[0].title() for row in city_data]
            context["city_values"] = [round(row[1] * 100, 1) for row in city_data]
            
            # 3. Churn by Age
            c.execute("""
                SELECT 
                    CASE 
                        WHEN (2025 - birth_year) <= 25 THEN '18-25'
                        WHEN (2025 - birth_year) <= 35 THEN '26-35'
                        WHEN (2025 - birth_year) <= 45 THEN '36-45'
                        WHEN (2025 - birth_year) <= 55 THEN '46-55'
                        ELSE '56+' 
                    END as age_group, 
                    AVG(cc.churn_probability)
                FROM customer c 
                JOIN customer_churn cc ON c.customer_id = cc.customer_id 
                GROUP BY age_group 
                ORDER BY age_group
            """)
            age_data = c.fetchall()
            context["age_labels"] = [row[0] for row in age_data]
            context["age_values"] = [round(row[1] * 100, 1) for row in age_data]
            
            # 4. Global Metrics
            c.execute("SELECT COUNT(*) FROM customer")
            context["total_customers"] = c.fetchone()[0]
            
            c.execute("SELECT COUNT(*) FROM customer_churn")
            context["active_customers"] = c.fetchone()[0]
            
            high_risk_count = context["risk_dist"]["Yüksek"]
            context["high_risk_pct"] = round((high_risk_count / context["active_customers"]) * 100, 1) if context["active_customers"] else 0
            
            # 5. Model Evaluation Curves
            cache_dir = db_path.parent / "data" / "model_cache"
            curves_path = cache_dir / "evaluation_curves.json"
            if curves_path.exists():
                try:
                    with open(curves_path, "r", encoding="utf-8") as f:
                        context["curves"] = json.load(f)
                except Exception:
                    pass
            
            # 6. Notebook Analytics Data
            analytics_path = cache_dir / "dashboard_analytics.json"
            if analytics_path.exists():
                try:
                    with open(analytics_path, "r", encoding="utf-8") as f:
                        context["analytics"] = json.load(f)
                except Exception:
                    pass
            
            conn.close()
        except Exception:
            logger.exception("Dashboard verileri sorgulanırken hata oluştu.")
            
    return render(
        request,
        "chatbot/index.html",
        {"dashboard_data": json.dumps(context)}
    )


@require_POST
def send_message(request):
    try:
        body = json.loads(request.body)
        message = str(body.get("message", "")).strip()

        if not message:
            return JsonResponse(
                {"error": "Lütfen bir mesaj yazın."},
                status=400,
            )

        if len(message) > 1000:
            return JsonResponse(
                {"error": "Mesaj en fazla 1000 karakter olabilir."},
                status=400,
            )

        chatbot = create_chatbot()

        session_customer_id = request.session.get("customer_id")

        if session_customer_id is None:
            extracted_id = chatbot._extract_customer_id(message)
            if extracted_id is None and "kerem" in message.lower():
                extracted_id = 10
            
            if extracted_id is not None:
                info = chatbot._get_customer_info(extracted_id)
                if info and "bulunamadı" not in info.lower() and "hata" not in info.lower():
                    request.session["customer_id"] = extracted_id
                    
                    db_path = Path(__file__).resolve().parent.parent / "db.sqlite3"
                    city, birth_year = "Bilinmiyor", "Bilinmiyor"
                    try:
                        conn = sqlite3.connect(db_path)
                        c = conn.cursor()
                        c.execute("SELECT city, birth_year FROM customer WHERE customer_id = ?", (extracted_id,))
                        row = c.fetchone()
                        if row:
                            city, birth_year = row
                        conn.close()
                    except Exception:
                        pass
                    
                    welcome_back = ""
                    if "kerem" in message.lower():
                        welcome_back = "Hoş geldiniz Kerem Bey! "
                    
                    response_text = (
                        f"{welcome_back}Müşteri numaranız doğrulandı: "
                        f"**ID: {extracted_id}** (Şehir: {city.title()}, Doğum Yılı: {birth_year}). "
                        f"Size nasıl yardımcı olabilirim?"
                    )
                    return JsonResponse(
                        {
                            "answer": response_text,
                            "sources": []
                        }
                    )
                else:
                    return JsonResponse(
                        {
                            "answer": f"Girdiğiniz müşteri numarası (**{extracted_id}**) sistemde bulunamadı. Lütfen geçerli bir müşteri ID'si giriniz.",
                            "sources": []
                        }
                    )
            else:
                return JsonResponse(
                    {
                        "answer": "Merhaba! Yardımcı olabilmem için lütfen önce **müşteri numaranızı (ID)** yazınız (örn: *ID: 10* veya *Ben Kerem*).",
                        "sources": []
                    }
                )

        new_extracted_id = chatbot._extract_customer_id(message)
        if new_extracted_id is not None and new_extracted_id != session_customer_id:
            info = chatbot._get_customer_info(new_extracted_id)
            if info and "bulunamadı" not in info.lower() and "hata" not in info.lower():
                request.session["customer_id"] = new_extracted_id
                session_customer_id = new_extracted_id

        chatbot.history = request.session.get(
            "chatbot_history",
            [],
        )

        chatbot.last_user_question = request.session.get(
            "last_user_question"
        )

        response = chatbot.ask(message, session_customer_id=session_customer_id)

        request.session["chatbot_history"] = chatbot.history
        request.session["last_user_question"] = message

        sources = [
            {
                "document_id": result.document.document_id,
                "title": result.document.title,
                "category": result.document.category,
                "issue_code": result.document.issue_code,
                "score": round(result.score, 4),
            }
            for result in response.sources
        ]

        return JsonResponse(
            {
                "answer": response.answer,
                "sources": sources,
            }
        )

    except json.JSONDecodeError:
        return JsonResponse(
            {"error": "Geçersiz istek."},
            status=400,
        )

    except Exception:
        logger.exception("Chatbot isteği başarısız oldu.")

        return JsonResponse(
            {
                "error": (
                    "Chatbot şu anda yanıt veremiyor. "
                    "Lütfen tekrar deneyin."
                )
            },
            status=500,
        )


@require_POST
def clear_chat(request):
    request.session.pop("chatbot_history", None)
    request.session.pop("last_user_question", None)
    request.session.pop("customer_id", None)

    return JsonResponse({"success": True})


def get_bundle_details(request):
    customer_id_str = request.GET.get("customer_id", "").strip()
    if not customer_id_str:
        return JsonResponse({"error": "Müşteri ID belirtilmedi."}, status=400)
    
    try:
        customer_id = int(customer_id_str)
    except ValueError:
        return JsonResponse({"error": "Geçersiz müşteri ID."}, status=400)
        
    db_path = Path(__file__).resolve().parent.parent / "db.sqlite3"
    if not db_path.exists():
        return JsonResponse({"error": "Veritabanı bulunamadı."}, status=500)
        
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Customer basic info
        c.execute("SELECT city, birth_year FROM customer WHERE customer_id = ?", (customer_id,))
        cust = c.fetchone()
        if not cust:
            conn.close()
            return JsonResponse({"error": f"Müşteri ID {customer_id} bulunamadı."}, status=404)
        city, birth_year = cust
        age = 2025 - birth_year
        
        # Churn risk
        c.execute("SELECT churn_probability, churn_risk_group FROM customer_churn WHERE customer_id = ?", (customer_id,))
        churn = c.fetchone()
        if churn:
            prob, risk_group = churn
            prob_pct = round(prob * 100, 1)
        else:
            prob_pct = None
            risk_group = "Hesaplanmadı"
            
        # Recent spending
        c.execute("SELECT billing_year_month, bill_amount, data_usage FROM customer_spending WHERE customer_id = ? ORDER BY billing_year_month DESC LIMIT 3", (customer_id,))
        spending = c.fetchall()
        spending_list = [
            {"month": row[0], "bill": round(row[1], 2), "usage": round(row[2], 2)}
            for row in spending
        ]
        
        # Determine recommended bundle
        if risk_group == "Yüksek":
            recommended_action = "Risk durumunuz yüksek olduğu için size özel gelecek ay faturanızda %20 indirim VEYA 'Sadakat Kampanyası: Ücretsiz Ekstra 20 GB İnternet' tanımlanmıştır."
            bundle_tag = "Sadakat Koruma Paketi"
        elif risk_group == "Orta":
            recommended_action = "Risk durumunuz orta seviyededir. Size özel 'Fırsat Kampanyası: Ekstra 5 GB Hediye İnternet' paketi sunulmuştur."
            bundle_tag = "Fırsat Hediye Paketi"
        else:
            recommended_action = "Mevcut tarifenin devamı öneriliyor. Churn riski düşüktür."
            bundle_tag = "Mevcut Tarife Planı"
            
        conn.close()
        
        return JsonResponse({
            "customer_id": customer_id,
            "city": city.title(),
            "age": age,
            "churn_probability": prob_pct,
            "churn_risk_group": risk_group,
            "spending_history": spending_list,
            "recommended_action": recommended_action,
            "bundle_tag": bundle_tag
        })
        
    except Exception:
        logger.exception("Bundle detayı sorgulanırken hata oluştu.")
        return JsonResponse({"error": "Bir iç hata oluştu."}, status=500)
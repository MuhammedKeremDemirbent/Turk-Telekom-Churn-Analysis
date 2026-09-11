from dataclasses import dataclass
import re
import sqlite3
from pathlib import Path

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from .models import SearchResult
from .vector_store import FaissStore


SYSTEM_PROMPT = """
Sen bir telekom müşteri destek asistanısın.

Kurallar:
- Müşterinin profili, harcamaları, internet kullanımı veya kayıp (churn) riski ile ilgili sorular için yalnızca MÜŞTERİ BİLGİLERİ bölümündeki bilgileri kullan.
- Genel sorunlar ve çözüm adımları için yalnızca KAYNAKLAR bölümündeki bilgileri kullan.
- Kendi bilgini veya tahminlerini ekleme.
- Eğer müşterinin Kayıp (Churn) Riski "Yüksek Risk Grubu" ise, onlara özel olarak gelecek ay faturalarında %20 indirim veya "Sadakat Kampanyası: Ücretsiz Ekstra 20 GB İnternet" teklif et. (Düşük veya Orta risk grubundaki müşterilere bu teklifi yapma).
- Kaynaklarda veya müşteri bilgilerinde cevap yoksa:
  "Bu konuda kaynaklarda yeterli bilgi bulamadım." de.
- Çözüm adımlarını numaralı ve anlaşılır şekilde yaz.
- Kısa ve doğrudan cevap ver.
- Türkçe cevap ver.
- Cevabın sonunda hiçbir şekilde kaynak belirtme (örn. "Kaynaklar: DOC..." veya benzeri hiçbir kaynak/doküman kodu yazma). Sadece doğrudan cevabı ver.
""".strip()


@dataclass(frozen=True)
class ChatResponse:
    answer: str
    sources: list[SearchResult]


class RAGChatbot:
    def __init__(
        self,
        client: OpenAI,
        store: FaissStore,
        chat_model: str,
        top_k: int = 3,
        min_score: float = 0.35,
        score_margin: float = 0.08,
    ) -> None:
        self.client = client
        self.store = store
        self.chat_model = chat_model
        self.top_k = top_k
        self.min_score = min_score
        self.score_margin = score_margin

        self.history: list[ChatCompletionMessageParam] = []
        self.last_user_question: str | None = None

    def _create_search_query(self, question: str) -> str:
        """
        Takip sorularında önceki kullanıcı sorusunu da retrieval
        sorgusuna ekler.
        """
        if self.last_user_question is None:
            return question

        return (
            f"Önceki soru: {self.last_user_question}\n"
            f"Yeni soru: {question}"
        )

    def retrieve(
        self,
        question: str,
    ) -> list[SearchResult]:
        search_query = self._create_search_query(question)

        # Aynı sorun türüne ait çok sayıda benzer doküman
        # bulunduğu için daha fazla aday getiriyoruz.
        candidates = self.store.search(
            query=search_query,
            top_k=max(self.top_k * 10, 20),
        )

        if not candidates:
            return []

        best_score = candidates[0].score

        minimum_allowed_score = max(
            self.min_score,
            best_score - self.score_margin,
        )

        selected_results: list[SearchResult] = []
        used_issue_codes: set[str] = set()

        for result in candidates:
            if result.score < minimum_allowed_score:
                continue

            issue_code = (
                result.document.issue_code
                or result.document.document_id
            )

            # Aynı sorun türünü yalnızca bir defa ekle.
            if issue_code in used_issue_codes:
                continue

            used_issue_codes.add(issue_code)
            selected_results.append(result)

            if len(selected_results) >= self.top_k:
                break

        return selected_results

    @staticmethod
    def _format_sources(
        results: list[SearchResult],
    ) -> str:
        source_blocks: list[str] = []

        for result in results:
            document = result.document

            source_block = (
                f"[KAYNAK: {document.document_id}]\n"
                f"Başlık: {document.title}\n"
                f"Kategori: {document.category}\n"
                f"Sorun kodu: {document.issue_code}\n"
                f"Benzerlik skoru: {result.score:.4f}\n\n"
                f"{document.content}"
            )

            source_blocks.append(source_block)

        return "\n\n---\n\n".join(source_blocks)

    def _extract_customer_id(self, text: str) -> int | None:
        patterns = [
            r'(?:customer[-_\s]*id|müsteri[-_\s]*id|müşteri[-_\s]*id|id[-_\s]*si|id[-_\s]*’si|id[-_\s]*\'si|id|müsteri|müşteri)\s*[:=]?\s*(\d+)',
            r'\b(\d+)\s*(?:id|numaralı|nolu)\b'
        ]
        text_lower = text.lower()
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                return int(match.group(1))
        
        # Fallback
        numbers = re.findall(r'\b\d+\b', text_lower)
        # Yıl belirtmek için kullanılan 4 basamaklı sayıları (19xx ve 20xx) hariç tut
        valid_numbers = [num for num in numbers if not (len(num) == 4 and (num.startswith("19") or num.startswith("20")))]
        if len(valid_numbers) == 1 and any(w in text_lower for w in ['id', 'müşteri', 'müsteri', 'customer', 'harcama', 'fatura', 'gb']):
            return int(valid_numbers[0])
        return None

    def _get_customer_info(self, customer_id: int) -> str | None:
        db_path = Path(__file__).resolve().parent.parent.parent / "db.sqlite3"
        if not db_path.exists():
            return None

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Query customer info
            cursor.execute("SELECT city, birth_year FROM customer WHERE customer_id = ?", (customer_id,))
            cust_row = cursor.fetchone()
            if not cust_row:
                conn.close()
                return f"Müşteri ID: {customer_id} bulunamadı."

            city, birth_year = cust_row

            # Query churn risk if available
            churn_str = "Kayıp (Churn) Riski: Hesaplanmadı (Müşteri son dönemde aktif değil veya zaten ayrılmış olabilir)"
            try:
                cursor.execute("SELECT churn_probability, churn_risk_group FROM customer_churn WHERE customer_id = ?", (customer_id,))
                churn_row = cursor.fetchone()
                if churn_row:
                    churn_prob, churn_risk = churn_row
                    churn_str = f"Kayıp (Churn) Riski: %{churn_prob*100:.1f} ({churn_risk} Risk Grubu)"
            except Exception:
                pass

            # Query spending history
            cursor.execute(
                "SELECT billing_year_month, bill_amount, data_usage FROM customer_spending WHERE customer_id = ? ORDER BY billing_year_month",
                (customer_id,)
            )
            spending_rows = cursor.fetchall()

            months_map = {
                "01": "Ocak", "02": "Şubat", "03": "Mart", "04": "Nisan",
                "05": "Mayıs", "06": "Haziran", "07": "Temmuz", "08": "Ağustos",
                "09": "Eylül", "10": "Ekim", "11": "Kasım", "12": "Aralık"
            }

            spending_lines = []
            for year_month, amount, usage in spending_rows:
                year = year_month[:4]
                month_code = year_month[4:]
                month_name = months_map.get(month_code, month_code)
                spending_lines.append(
                    f"- {month_name} {year}: Fatura Tutarı: {amount:.2f} Dolar, İnternet Kullanımı: {usage:.2f} GB"
                )

            spending_str = "\n".join(spending_lines) if spending_lines else "Harcama kaydı bulunamadı."
            conn.close()

            return (
                f"[MÜŞTERİ BİLGİLERİ (CUSTOMER ID: {customer_id})]\n"
                f"Müşteri ID: {customer_id}\n"
                f"Bulunduğu Şehir: {city.title()}\n"
                f"Doğum Yılı: {birth_year}\n"
                f"{churn_str}\n\n"
                f"[MÜŞTERİ HARCAMA VE KULLANIM DETAYLARI]\n"
                f"{spending_str}"
            )
        except Exception as e:
            return f"Müşteri verileri çekilirken bir hata oluştu: {str(e)}"

    def ask(
        self,
        question: str,
        session_customer_id: int | None = None,
    ) -> ChatResponse:
        question = question.strip()

        if not question:
            return ChatResponse(
                answer="Lütfen bir soru yazın.",
                sources=[],
            )

        customer_id = self._extract_customer_id(question)
        if customer_id is None:
            if session_customer_id is not None:
                customer_id = session_customer_id
            elif "kerem" in question.lower():
                customer_id = 10
        customer_info = self._get_customer_info(customer_id) if customer_id is not None else None

        results = self.retrieve(question)

        if not results and not customer_info:
            return ChatResponse(
                answer=(
                    "Bu konuda kaynaklarda yeterli bilgi bulamadım."
                ),
                sources=[],
            )

        formatted_sources = self._format_sources(results)

        grounded_question_parts = []
        if customer_info:
            grounded_question_parts.append(customer_info)
        
        if formatted_sources:
            grounded_question_parts.append(f"KAYNAKLAR:\n{formatted_sources}")

        grounded_question_parts.append(f"KULLANICI SORUSU:\n{question}")
        grounded_question = "\n\n---\n\n".join(grounded_question_parts)

        messages: list[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            *self.history[-6:],
            {
                "role": "user",
                "content": grounded_question,
            },
        ]

        response = self.client.chat.completions.create(
            model=self.chat_model,
            messages=messages,
            temperature=0.1,
            max_tokens=800,
            extra_body={
                "chat_template_kwargs": {
                    "enable_thinking": False,
                }
            },
        )

        answer = (
            response.choices[0].message.content or ""
        ).strip()

        if not answer:
            answer = (
                "Bu konuda kaynaklarda yeterli bilgi bulamadım."
            )

        self.history.extend(
            [
                {
                    "role": "user",
                    "content": question,
                },
                {
                    "role": "assistant",
                    "content": answer,
                },
            ]
        )

        self.last_user_question = question

        return ChatResponse(
            answer=answer,
            sources=results,
        )

    def reset(self) -> None:
        self.history.clear()
        self.last_user_question = None
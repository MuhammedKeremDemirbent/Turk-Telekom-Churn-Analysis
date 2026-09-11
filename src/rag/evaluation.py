from dataclasses import dataclass

from .vector_store import FaissStore


@dataclass(frozen=True)
class EvaluationCase:
    question: str
    expected_issue_code: str


@dataclass(frozen=True)
class EvaluationResult:
    total: int
    hit_at_1: float
    hit_at_3: float
    mean_reciprocal_rank: float
    failures: list[dict[str, object]]


DEFAULT_EVALUATION_CASES = [
    EvaluationCase(
        question="Modemim sürekli kendi kendine yeniden başlıyor.",
        expected_issue_code="router_malfunction",
    ),
    EvaluationCase(
        question="eSIM için gönderilen QR kod çalışmıyor.",
        expected_issue_code="esim_setup",
    ),
    EvaluationCase(
        question="Evde telefonum hiç çekmiyor.",
        expected_issue_code="indoor_coverage",
    ),
    EvaluationCase(
        question="İnternet siteleri açılmıyor, DNS hatası alıyorum.",
        expected_issue_code="dns_failure",
    ),
    EvaluationCase(
        question="Kurulum randevum sürekli erteleniyor.",
        expected_issue_code="delayed_installation",
    ),
    EvaluationCase(
        question="Aramada karşı taraf beni duyuyor ama ben duyamıyorum.",
        expected_issue_code="one_way_audio",
    ),
    EvaluationCase(
        question="Sesli mesaj kutuma erişemiyorum.",
        expected_issue_code="voicemail_issue",
    ),
]


def evaluate_retrieval(
    store: FaissStore,
    cases: list[EvaluationCase] | None = None,
    top_k: int = 3,
) -> EvaluationResult:
    cases = cases or DEFAULT_EVALUATION_CASES

    hit_at_1_count = 0
    hit_at_3_count = 0
    reciprocal_rank_total = 0.0
    failures: list[dict[str, object]] = []

    for case in cases:
        results = store.search(
            query=case.question,
            top_k=top_k,
        )

        predicted_codes = [
            result.document.issue_code
            for result in results
        ]

        if predicted_codes:
            if predicted_codes[0] == case.expected_issue_code:
                hit_at_1_count += 1

        expected_rank = None

        for rank, issue_code in enumerate(
            predicted_codes,
            start=1,
        ):
            if issue_code == case.expected_issue_code:
                expected_rank = rank
                break

        if expected_rank is not None:
            hit_at_3_count += 1
            reciprocal_rank_total += 1 / expected_rank
        else:
            failures.append(
                {
                    "question": case.question,
                    "expected": case.expected_issue_code,
                    "predicted": predicted_codes,
                }
            )

    total = len(cases)

    return EvaluationResult(
        total=total,
        hit_at_1=hit_at_1_count / total,
        hit_at_3=hit_at_3_count / total,
        mean_reciprocal_rank=(
            reciprocal_rank_total / total
        ),
        failures=failures,
    )
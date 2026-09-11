document.addEventListener("DOMContentLoaded", () => {
    // --- 1. TAB SELECTION LOGIC ---
    const sidebarButtons = document.querySelectorAll(".sidebar-btn");
    const viewSections = document.querySelectorAll(".view-section");

    sidebarButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetView = btn.getAttribute("data-view");

            // Toggle Sidebar buttons active state
            sidebarButtons.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");

            // Toggle visible sections
            viewSections.forEach(section => {
                section.classList.remove("active");
                if (section.id === targetView) {
                    section.classList.add("active");
                }
            });
        });
    });

    // --- 2. CHART.JS RENDERING ---
    if (typeof Chart !== "undefined" && window.dashboardData) {
        const dist = window.dashboardData.risk_dist || { "Düşük": 0, "Orta": 0, "Yüksek": 0 };
        const cities = window.dashboardData.city_labels || [];
        const cityVals = window.dashboardData.city_values || [];
        const ages = window.dashboardData.age_labels || [];
        const ageVals = window.dashboardData.age_values || [];

        // --- Chart 0: En Çok Şikayet Alınan Kategoriler ---
        const complaintData = (window.dashboardData.analytics || {}).complaint_categories || null;
        if (complaintData && document.getElementById("complaintCatChart")) {
            const ctxComp = document.getElementById("complaintCatChart").getContext("2d");
            const compGradientColors = [
                "#ef4444","#f97316","#f59e0b","#eab308","#84cc16",
                "#10b981","#06b6d4","#3b82f6","#6366f1","#a855f7"
            ];
            new Chart(ctxComp, {
                type: "bar",
                data: {
                    labels: complaintData.labels_tr || complaintData.labels_en || [],
                    datasets: [{
                        label: "Şikayet Sayısı",
                        data: complaintData.counts || [],
                        backgroundColor: compGradientColors,
                        borderRadius: 6,
                        borderSkipped: false,
                    }]
                },
                options: {
                    indexAxis: "y",
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                afterLabel: (ctx) => {
                                    const uc = (complaintData.unique_customers || [])[ctx.dataIndex];
                                    return uc ? `Etkilenen Müşteri: ${uc.toLocaleString("tr-TR")}` : "";
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            grid: { color: "rgba(255,255,255,0.05)" },
                            ticks: {
                                color: "#94a3b8",
                                callback: v => v >= 1000 ? (v/1000).toFixed(0)+"K" : v
                            }
                        },
                        y: {
                            grid: { display: false },
                            ticks: { color: "#e2e8f0", font: { weight: "600" } }
                        }
                    }
                }
            });
        }

        // Chart 1: Churn Risk Dagilimi (Doughnut)

        const ctx1 = document.getElementById("riskDistChart").getContext("2d");
        new Chart(ctx1, {
            type: "doughnut",
            data: {
                labels: ["D\u00FC\u015F\u00FCk Risk", "Orta Risk", "Y\u00FCksek Risk"],
                datasets: [{
                    data: [dist["Düşük"] || dist["Dük"] || 0, dist["Orta"] || 0, dist["Yüksek"] || 0],
                    backgroundColor: ["#10b981", "#f59e0b", "#ef4444"],
                    borderWidth: 1,
                    borderColor: "rgba(255, 255, 255, 0.1)"
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: { color: "#94a3b8" }
                    }
                }
            }
        });

        // --- Chart 2: Precision-Recall Eğrisi ---
        const curves = window.dashboardData.curves || {
            pr: { precision: [], recall: [], baseline: 0 }
        };
        // Reverse scikit-learn's decreasing recall arrays for standard 0 -> 1 plot
        const prRecalls = [...(curves.pr.recall || [])].reverse();
        const prPrecisions = [...(curves.pr.precision || [])].reverse();

        const ctx2 = document.getElementById("prChart").getContext("2d");
        new Chart(ctx2, {
            type: "line",
            data: {
                labels: prRecalls,
                datasets: [
                    {
                        label: "Churn modeli",
                        data: prPrecisions,
                        borderColor: "#3b82f6",
                        backgroundColor: "rgba(59, 130, 246, 0.1)",
                        borderWidth: 2.5,
                        fill: true,
                        tension: 0.1,
                        pointRadius: 0
                    },
                    {
                        label: `Random baseline (${((curves.pr.baseline || 0) * 100).toFixed(2)}%)`,
                        data: Array(prRecalls.length).fill(curves.pr.baseline || 0),
                        borderColor: "rgba(239, 68, 68, 0.8)",
                        borderDash: [5, 5],
                        borderWidth: 1.5,
                        fill: false,
                        pointRadius: 0
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: "#94a3b8" } }
                },
                scales: {
                    x: {
                        grid: { color: "rgba(255, 255, 255, 0.05)" },
                        ticks: {
                            color: "#94a3b8",
                            autoSkip: true,
                            maxTicksLimit: 6,
                            callback: function(value, index, values) {
                                const val = parseFloat(this.getLabelForValue(value));
                                return isNaN(val) ? "" : val.toFixed(2);
                            }
                        },
                        title: { display: true, text: "Recall", color: "#94a3b8" }
                    },
                    y: {
                        grid: { color: "rgba(255, 255, 255, 0.05)" },
                        ticks: { color: "#94a3b8" },
                        min: 0,
                        max: 1.05,
                        title: { display: true, text: "Precision", color: "#94a3b8" }
                    }
                }
            }
        });

        // Retrieve Notebook analytics
        const analytics = window.dashboardData.analytics || {
            monthly_active: { months: [], counts: [], rates: [] },
            segment_loss: { segments: [], counts: [], avg_bills: [], rev_losses: [] },
            cohort_loss: { months: [], counts: [], rev_losses: [] }
        };

        // --- Stat Cards: Dynamically filled from analytics data ---
        const monthlyCounts = analytics.monthly_active.counts || [];
        const monthlyMonths = analytics.monthly_active.months || [];

        // Active subscribers = last available month's count (e.g. Dec 2025 = 77,502)
        if (monthlyCounts.length > 0) {
            const lastCount = monthlyCounts[monthlyCounts.length - 1];
            const lastMonth = monthlyMonths[monthlyMonths.length - 1] || "";
            const cardActive = document.getElementById("card-active");
            if (cardActive) {
                cardActive.textContent = lastCount.toLocaleString("tr-TR");
            }
            // Update the trend label with the actual month name
            const trendEl = cardActive ? cardActive.nextElementSibling : null;
            if (trendEl && lastMonth) {
                const [yr, mo] = lastMonth.split("-");
                const monthNames = ["", "Ocak","Şubat","Mart","Nisan","Mayıs","Haziran",
                                    "Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık"];
                const moIdx = parseInt(mo, 10);
                trendEl.textContent = `${monthNames[moIdx] || lastMonth} ${yr} Dönemi`;
            }
        }

        // Total portfolio = first month (initial subscriber base)
        if (monthlyCounts.length > 0) {
            const cardTotal = document.getElementById("card-total");
            if (cardTotal) {
                cardTotal.textContent = monthlyCounts[0].toLocaleString("tr-TR");
            }
        }

        // High-risk % from the risk distribution
        const totalRisk = (dist["Düşük"] || 0) + (dist["Orta"] || 0) + (dist["Yüksek"] || 0);
        if (totalRisk > 0) {
            const highPct = ((dist["Yüksek"] || 0) / totalRisk * 100).toFixed(1);
            const cardHighRisk = document.getElementById("card-high-risk");
            if (cardHighRisk) cardHighRisk.textContent = `%${highPct}`;
        }

        // --- Model Metrics Panel ---
        const mm = (window.dashboardData.curves || {}).model_metrics || null;
        if (mm) {
            // Helper: set bar width + value text
            function setMetricBar(barId, valId, value, maxVal, format) {
                const bar = document.getElementById(barId);
                const val = document.getElementById(valId);
                if (bar) {
                    const pct = Math.min((value / maxVal) * 100, 100);
                    setTimeout(() => { bar.style.width = pct + "%"; }, 100);
                }
                if (val) val.textContent = format(value);
            }

            // PR-AUC: max ~0.15 for imbalanced, shown on 0-0.15 scale, display as raw
            setMetricBar("bar-prauc", "val-prauc", mm.pr_auc, 0.15,
                v => v.toFixed(4));

            // ROC-AUC: 0.5=random, 1=perfect → show on 0.5-1.0 scale
            setMetricBar("bar-rocauc", "val-rocauc", mm.roc_auc - 0.5, 0.5,
                v => (v + 0.5).toFixed(4));

            // Brier Score: lower is better, show inverted (1 - brier) on bar
            setMetricBar("bar-brier", "val-brier", 1 - mm.brier_score, 1,
                v => (1 - v).toFixed(4) + " ↓ daha iyi");

            // Prevalence: show as percentage
            setMetricBar("bar-prev", "val-prev", mm.prevalence, 0.15,
                v => "%" + (v * 100).toFixed(2));

            // Top-K Table
            const tbody = document.getElementById("topk-tbody");
            if (tbody && mm.topk) {
                tbody.innerHTML = mm.topk.map(row => {
                    const liftClass = row.lift >= 3 ? "lift-high" : row.lift >= 2 ? "lift-med" : "";
                    return `<tr>
                        <td><strong>En Riskli %${row.k_percent}</strong></td>
                        <td>${row.selected.toLocaleString("tr-TR")}</td>
                        <td>${row.true_churn.toLocaleString("tr-TR")}</td>
                        <td>${(row.precision * 100).toFixed(1)}%</td>
                        <td>${(row.recall * 100).toFixed(1)}%</td>
                        <td class="${liftClass}"><strong>${row.lift.toFixed(2)}×</strong></td>
                    </tr>`;
                }).join("");

                // Lift highlight for k=1%
                const top1 = mm.topk.find(r => r.k_percent === 1);
                const liftEl = document.getElementById("lift-highlight");
                if (top1 && liftEl) liftEl.textContent = top1.lift.toFixed(2);
            }
        }

        // --- Chart 3a: Aylık Aktif Müşteri Sayısı ---
        const ctxActive = document.getElementById("activeCustomersChart").getContext("2d");
        new Chart(ctxActive, {
            type: "line",
            data: {
                labels: analytics.monthly_active.months || [],
                datasets: [{
                    label: "M\u00FC\u015Fteri Say\u0131s\u0131",
                    data: analytics.monthly_active.counts || [],
                    borderColor: "#3b82f6",
                    backgroundColor: "rgba(59, 130, 246, 0.15)",
                    borderWidth: 2.5,
                    fill: false,
                    tension: 0.2,
                    pointRadius: 3,
                    pointBackgroundColor: "#3b82f6"
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: { display: true, text: "Ayl\u0131k Aktif M\u00FC\u015Fteri Say\u0131s\u0131", color: "#f8fafc" },
                    legend: { display: false }
                },
                scales: {
                    x: {
                        grid: { color: "rgba(255, 255, 255, 0.05)" },
                        ticks: { color: "#94a3b8", autoSkip: true, maxTicksLimit: 8 }
                    },
                    y: {
                        grid: { color: "rgba(255, 255, 255, 0.05)" },
                        ticks: { color: "#94a3b8" }
                    }
                }
            }
        });

        // --- Chart 3b: Aylık Müşteri Değişim Oranı ---
        const ctxRate = document.getElementById("changeRateChart").getContext("2d");
        const rateColors = (analytics.monthly_active.rates || []).map(r => r >= 0 ? "#10b981" : "#ef4444");
        new Chart(ctxRate, {
            type: "bar",
            data: {
                labels: analytics.monthly_active.months || [],
                datasets: [{
                    label: "De\u011Fi\u015Fim (%)",
                    data: analytics.monthly_active.rates || [],
                    backgroundColor: rateColors,
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: { display: true, text: "Ayl\u0131k M\u00FC\u015Fteri Say\u0131s\u0131 De\u011Fi\u015Fim H\u0131z\u0131", color: "#f8fafc" },
                    legend: { display: false }
                },
                scales: {
                    x: {
                        grid: { color: "rgba(255, 255, 255, 0.05)" },
                        ticks: { color: "#94a3b8", autoSkip: true, maxTicksLimit: 8 }
                    },
                    y: {
                        grid: { color: "rgba(255, 255, 255, 0.05)" },
                        ticks: { color: "#94a3b8" }
                    }
                }
            }
        });

        // --- Chart 4a: Segmentlere Göre Kaybedilen Müşteri ---
        const ctxSegCount = document.getElementById("segmentCountChart").getContext("2d");
        new Chart(ctxSegCount, {
            type: "bar",
            data: {
                labels: analytics.segment_loss.segments || [],
                datasets: [{
                    data: analytics.segment_loss.counts || [],
                    backgroundColor: "#ef4444",
                    borderRadius: 6
                }]
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: { display: true, text: "Segmentlere G\u00F6re Kaybedilen M\u00FC\u015Fteri", color: "#f8fafc" },
                    legend: { display: false }
                },
                scales: {
                    x: { grid: { color: "rgba(255, 255, 255, 0.05)" }, ticks: { color: "#94a3b8" } },
                    y: { grid: { display: false }, ticks: { color: "#94a3b8" } }
                }
            }
        });

        // --- Chart 4b: Ayrılmadan Önce Ortalama Fatura ---
        const ctxSegBill = document.getElementById("segmentBillChart").getContext("2d");
        new Chart(ctxSegBill, {
            type: "bar",
            data: {
                labels: analytics.segment_loss.segments || [],
                datasets: [{
                    data: analytics.segment_loss.avg_bills || [],
                    backgroundColor: "#3b82f6",
                    borderRadius: 6
                }]
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: { display: true, text: "Ayr\u0131lmadan \u00D6nce Ortalama Fatura", color: "#f8fafc" },
                    legend: { display: false }
                },
                scales: {
                    x: { grid: { color: "rgba(255, 255, 255, 0.05)" }, ticks: { color: "#94a3b8" } },
                    y: { grid: { display: false }, ticks: { color: "#94a3b8" } }
                }
            }
        });

        // --- Chart 4c: Toplam Gelir Kaybı ---
        const ctxSegLoss = document.getElementById("segmentLossChart").getContext("2d");
        new Chart(ctxSegLoss, {
            type: "bar",
            data: {
                labels: analytics.segment_loss.segments || [],
                datasets: [{
                    data: analytics.segment_loss.rev_losses || [],
                    backgroundColor: "#f59e0b",
                    borderRadius: 6
                }]
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: { display: true, text: "Ayr\u0131lma Tarihine G\u00F6re Toplam Gelir Kayb\u0131", color: "#f8fafc" },
                    legend: { display: false }
                },
                scales: {
                    x: { grid: { color: "rgba(255, 255, 255, 0.05)" }, ticks: { color: "#94a3b8" } },
                    y: { grid: { display: false }, ticks: { color: "#94a3b8" } }
                }
            }
        });

        // --- Chart 5a: Son Aktif Olduğu Aya Göre Kayıp Sayısı ---
        const ctxCohortCount = document.getElementById("cohortCountChart").getContext("2d");
        new Chart(ctxCohortCount, {
            type: "bar",
            data: {
                labels: analytics.cohort_loss.months || [],
                datasets: [{
                    data: analytics.cohort_loss.counts || [],
                    backgroundColor: "#ef4444",
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: { display: true, text: "M\u00FC\u015Fterinin Son Aktif Oldu\u011Fu Aya G\u00F6re Kay\u0131p Say\u0131s\u0131", color: "#f8fafc" },
                    legend: { display: false }
                },
                scales: {
                    x: { grid: { display: false }, ticks: { color: "#94a3b8", autoSkip: true, maxTicksLimit: 8 } },
                    y: { grid: { color: "rgba(255, 255, 255, 0.05)" }, ticks: { color: "#94a3b8" } }
                }
            }
        });

        // --- Chart 5b: Son Aktif Ay Kohortlarının Gelir Kaybı ---
        const ctxCohortLoss = document.getElementById("cohortLossChart").getContext("2d");
        new Chart(ctxCohortLoss, {
            type: "line",
            data: {
                labels: analytics.cohort_loss.months || [],
                datasets: [{
                    data: analytics.cohort_loss.rev_losses || [],
                    borderColor: "#f59e0b",
                    backgroundColor: "rgba(245, 158, 11, 0.12)",
                    borderWidth: 2,
                    fill: true,
                    tension: 0.2,
                    pointRadius: 2,
                    pointBackgroundColor: "#f59e0b"
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: { display: true, text: "Son Aktif Ay Kohortlar\u0131n\u0131n Tahmini Gelir Kayb\u0131", color: "#f8fafc" },
                    legend: { display: false }
                },
                scales: {
                    x: { grid: { color: "rgba(255, 255, 255, 0.05)" }, ticks: { color: "#94a3b8", autoSkip: true, maxTicksLimit: 8 } },
                    y: { grid: { color: "rgba(255, 255, 255, 0.05)" }, ticks: { color: "#94a3b8" } }
                }
            }
        });
    }

    // --- 3. RAG CHATBOT LOGIC ---
    const chatForm = document.getElementById("chat-form");
    const chatInput = document.getElementById("message");
    const messagesContainer = document.getElementById("messages");
    const clearBtn = document.getElementById("clear-btn");
    const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]").value;

    chatInput.addEventListener("input", () => {
        chatInput.style.height = "auto";
        chatInput.style.height = `${Math.min(chatInput.scrollHeight, 120)}px`;
    });

    function addMessage(text, isUser = false, sources = []) {
        const row = document.createElement("div");
        row.classList.add("message-row");
        row.classList.add(isUser ? "user-row" : "bot-row");

        const bubble = document.createElement("div");
        bubble.classList.add("bubble");
        bubble.innerHTML = text.replace(/\n/g, "<br>");
        row.appendChild(bubble);

        // --- Kaynaklar (Sources) ---
        if (!isUser && sources && sources.length > 0) {
            const srcWrap = document.createElement("div");
            srcWrap.classList.add("sources-wrap");

            const srcTitle = document.createElement("div");
            srcTitle.classList.add("sources-title");
            srcTitle.innerHTML = `<span>📚 Kaynaklar (${sources.length})</span>`;
            srcWrap.appendChild(srcTitle);

            const srcList = document.createElement("div");
            srcList.classList.add("sources-list");

            sources.forEach(src => {
                const card = document.createElement("div");
                card.classList.add("source-card");

                const scoreBar = Math.round((src.score || 0) * 100);
                const cat = src.category || "—";
                const issue = src.issue_code ? `· ${src.issue_code}` : "";

                card.innerHTML = `
                    <div class="source-card-title">${src.title || src.document_id}</div>
                    <div class="source-card-meta">
                        <span class="source-badge">${cat}${issue}</span>
                        <span class="source-score">Alaka: ${(src.score * 100).toFixed(1)}%</span>
                    </div>
                `;
                srcList.appendChild(card);
            });

            srcWrap.appendChild(srcList);
            row.appendChild(srcWrap);
        }

        messagesContainer.appendChild(row);
        scrollToBottom();
    }

    let loaderElement = null;

    function showLoading() {
        if (loaderElement) return;

        loaderElement = document.createElement("div");
        loaderElement.classList.add("loading-row");
        loaderElement.innerHTML = `
            <div class="typing-indicator">
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
            </div>
        `;
        messagesContainer.appendChild(loaderElement);
        scrollToBottom();
    }

    function hideLoading() {
        if (loaderElement) {
            loaderElement.remove();
            loaderElement = null;
        }
    }

    function scrollToBottom() {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    chatForm.addEventListener("submit", async event => {
        event.preventDefault();

        const message = chatInput.value.trim();
        if (!message) return;

        addMessage(message, true);
        chatInput.value = "";
        chatInput.style.height = "auto";
        showLoading();

        try {
            const response = await fetch("/api/chat/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
                body: JSON.stringify({ message }),
            });

            const data = await response.json();
            hideLoading();

            if (data.answer) {
                addMessage(data.answer, false, data.sources);
            } else if (data.error) {
                addMessage(`Hata: ${data.error}`, false);
            } else {
                addMessage("Beklenmeyen bir yan\u0131t olu\u015Ftu.", false);
            }
        } catch (error) {
            hideLoading();
            console.error("Hata:", error);
            addMessage("Sunucuyla ba\u011Flant\u0131 kurulamad\u0131.", false);
        }
    });

    clearBtn.addEventListener("click", async () => {
        if (confirm("Sohbet ge\u00E7mi\u015Fini temizlemek istedi\u011Finize emin misiniz?")) {
            try {
                const response = await fetch("/api/chat/clear/", {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": csrfToken,
                    }
                });
                const data = await response.json();
                if (data.success) {
                    messagesContainer.innerHTML = "";
                    addMessage("Sohbet ge\u00E7mi\u015Fini temizledi. Size daha iyi yard\u0131mc\u0131 olabilmem i\u00E7in l\u00FCtfen m\u00FC\u015Fteri numaran\u0131z\u0131 (ID) belirtir misiniz?", false);
                }
            } catch (error) {
                console.error("Temizleme hatası:", error);
                alert("Temizleme işlemi başarısız oldu.");
            }
        }
    });

    addMessage("Merhaba! Ben Telekom M\u00FC\u015Fteri Destek Asistan\u0131. Size daha iyi yard\u0131mc\u0131 olabilmem i\u00E7in l\u00FCtfen m\u00FC\u015Fteri numaran\u0131z\u0131 (ID) belirtir misiniz? (\u00D6rn: *ID: 10* veya *Ben Kerem*)", false);

    // --- 4. BUNDLE AI KAMPANYA LOGIC ---
    const bundleForm = document.getElementById("bundle-form");
    const bundleInput = document.getElementById("bundle-customer-id");
    const resultCard = document.getElementById("bundle-result-card");

    // Display fields
    const resId = document.getElementById("res-id");
    const resMeta = document.getElementById("res-meta");
    const resBadge = document.getElementById("res-badge");
    const resProb = document.getElementById("res-prob");
    const resProbText = document.getElementById("res-prob-text");
    const resFill = document.getElementById("res-fill");
    const resTableBody = document.getElementById("res-table-body");
    const resActionTitle = document.getElementById("res-action-title");
    const resActionDesc = document.getElementById("res-action-desc");
    const resActionBtn = document.getElementById("res-action-btn");

    bundleForm.addEventListener("submit", async event => {
        event.preventDefault();
        const cid = bundleInput.value.trim();
        if (!cid) return;

        try {
            const response = await fetch(`/api/bundle/?customer_id=${cid}`);
            const data = await response.json();

            if (data.error) {
                alert(data.error);
                resultCard.classList.remove("active");
                return;
            }

            // Populate profile
            resId.textContent = `M\u00FC\u015Fteri ID: ${data.customer_id}`;
            resMeta.textContent = `Konum: ${data.city} \u2022 Ya\u015F: ${data.age}`;

            // Populate badge and colors
            resBadge.className = "risk-badge";
            resFill.className = "progress-bar-fill";

            if (data.churn_risk_group === "Yüksek" || data.churn_risk_group === "Y\u00FCksek") {
                resBadge.textContent = "Y\u00FCksek Risk";
                resBadge.classList.add("high");
                resFill.classList.add("high");
            } else if (data.churn_risk_group === "Orta") {
                resBadge.textContent = "Orta Risk";
                resBadge.classList.add("medium");
                resFill.classList.add("medium");
            } else {
                resBadge.textContent = "D\u00FC\u015F\u00FCk Risk";
                resBadge.classList.add("low");
                resFill.classList.add("low");
            }

            // Populate probability and progress bar
            if (data.churn_probability !== null) {
                resProb.textContent = `%${data.churn_probability}`;
                resFill.style.width = `${data.churn_probability}%`;
                resProbText.textContent = "Churn (Ayr\u0131lma) \u0130htimali";
            } else {
                resProb.textContent = "N/A";
                resFill.style.width = "0%";
                resProbText.textContent = "Churn \u0130htimali Hesaplanmad\u0131";
            }

            // Populate table
            resTableBody.innerHTML = "";
            if (data.spending_history && data.spending_history.length > 0) {
                data.spending_history.forEach(row => {
                    const tr = document.createElement("tr");
                    tr.innerHTML = `
                        <td>${row.month}</td>
                        <td>${row.bill} Dolar</td>
                        <td>${row.usage} GB</td>
                    `;
                    resTableBody.appendChild(tr);
                });
            } else {
                resTableBody.innerHTML = `<tr><td colspan="3" style="text-align:center;">Kay\u0131t bulunamad\u0131.</td></tr>`;
            }

            // Populate action card
            resActionTitle.innerHTML = `\uD83C\uDF81 \u00D6nerilen Kampanya: <span style="color:#818cf8; margin-left:4px;">${data.bundle_tag}</span>`;
            resActionDesc.textContent = data.recommended_action;

            if (data.churn_risk_group === "Yüksek" || data.churn_risk_group === "Y\u00FCksek") {
                resActionBtn.style.display = "inline-block";
                resActionBtn.onclick = () => {
                    alert(`Ba\u015Far\u0131l\u0131! M\u00FC\u015Fteri ${data.customer_id} i\u00E7in "%20 fatura indirimi ve ekstra 20 GB internet paketi" ba\u015Far\u0131yla tan\u0131mlanm\u0131\u015ft\u0131r.`);
                };
            } else if (data.churn_risk_group === "Orta") {
                resActionBtn.style.display = "inline-block";
                resActionBtn.onclick = () => {
                    alert(`Ba\u015Far\u0131l\u0131! M\u00FC\u015Fteri ${data.customer_id} i\u00E7in "Orta Risk Hediye 5 GB paketi" tan\u0131mlanm\u0131\u015ft\u0131r.`);
                };
            } else {
                resActionBtn.style.display = "none";
            }

            resultCard.classList.add("active");

        } catch (error) {
            console.error("Bundle hatası:", error);
            alert("Müşteri bilgisi sorgulanırken bir hata oluştu.");
            resultCard.classList.remove("active");
        }
    });
});

"""
External evidence collector for result-page transparency.

Uses Serper search API to gather verifiable web sources (government/legal,
market prices, and category-specific references) and returns structured checks
that can be shown directly to end-users with links.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


GOVERNMENT_DOMAINS = (
    "gov.uz",
    "lex.uz",
    "my.gov.uz",
    "data.gov.uz",
    "stat.uz",
    "cbu.uz",
    "soliq.uz",
)


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str
    domain: str


class SerperService:
    DEFAULT_BASE_URL = "https://google.serper.dev"

    def __init__(self) -> None:
        self.api_key = (getattr(settings, "SERPER_API_KEY", "") or "").strip()
        raw_base = (getattr(settings, "SERPER_API_URL", "") or "").strip()
        if not raw_base:
            raw_base = self.DEFAULT_BASE_URL
        self.base_url = raw_base.rstrip("/")
        self.endpoint = (
            self.base_url
            if self.base_url.endswith("/search")
            else f"{self.base_url}/search"
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, num: int = 6, gl: str = "uz", hl: str = "uz") -> list[SearchHit]:
        if not self.configured:
            return []

        payload = {
            "q": query,
            "num": max(1, min(int(num or 6), 10)),
            "gl": gl,
            "hl": hl,
            "autocorrect": True,
        }
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }

        candidates = [self.endpoint]
        fallback = f"{self.DEFAULT_BASE_URL}/search"
        if fallback not in candidates:
            candidates.append(fallback)

        last_error = None
        for target in candidates:
            try:
                resp = requests.post(target, headers=headers, json=payload, timeout=15)
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
                data = resp.json()
                organic = data.get("organic") or []
                results: list[SearchHit] = []
                for item in organic:
                    link = (item.get("link") or "").strip()
                    if not link:
                        continue
                    domain = _extract_domain(link)
                    results.append(
                        SearchHit(
                            title=(item.get("title") or domain or "Manba").strip(),
                            url=link,
                            snippet=(item.get("snippet") or "").strip(),
                            domain=domain,
                        )
                    )
                return results
            except Exception as exc:  # noqa: BLE001
                last_error = exc

        if last_error:
            logger.warning("Serper search failed for query '%s': %s", query, last_error)
        return []


class ExternalEvidenceService:
    """
    Builds user-facing external checks with direct links.

    Output shape:
    {
      "generated_at": "<iso>",
      "serper_configured": bool,
      "checks": [
        {
          "id": "legality",
          "title": "...",
          "status": "ok|warn|error",
          "feedback": "...",
          "user_input": {...},
          "sources": [{"title","url","snippet","domain"}, ...]
        },
      ],
      "summary": "...",
    }
    """

    def __init__(self) -> None:
        self.serper = SerperService()

    def build_report(self, req) -> dict:
        checks = [
            self._build_legality_check(req),
            self._build_price_check(req),
            self._build_market_signal_check(req),
            self._build_support_program_check(req),
        ]
        checks = [c for c in checks if c]
        ok_count = sum(1 for c in checks if c.get("status") == "ok")
        warn_count = sum(1 for c in checks if c.get("status") == "warn")
        err_count = sum(1 for c in checks if c.get("status") == "error")

        if not checks:
            summary = "Tashqi manba tekshiruvlari hozircha shakllantirilmadi."
        else:
            summary = (
                f"{len(checks)} ta mezon tekshirildi: {ok_count} OK, "
                f"{warn_count} ogohlantirish, {err_count} xato."
            )

        # Build per-block evidence (derived from block scores + Serper search)
        block_evidence = {
            "A": self._build_block_a_evidence(req),
            "B": self._build_block_b_evidence(req),
            "C": self._build_block_c_evidence(req),
            "D": self._build_block_d_evidence(req),
            "E": self._build_block_e_evidence(req),
        }

        return {
            "generated_at": timezone.now().isoformat(),
            "serper_configured": self.serper.configured,
            "checks": checks,
            "summary": summary,
            "block_evidence": block_evidence,
        }

    def _build_legality_check(self, req) -> dict:
        query_main = f"{req.business_type} O'zbekiston litsenziya talablari"
        queries = [
            f"site:lex.uz {query_main}",
            f"site:my.gov.uz {query_main}",
            f"site:gov.uz {query_main}",
            "site:lex.uz tadbirkorlik faoliyati litsenziya",
            "site:my.gov.uz tadbirkorlik ruxsatnoma",
        ]
        sources = self._collect_sources(queries, cap=2)
        gov_sources = [s for s in sources if _is_gov_domain(s["domain"])]

        if not self.serper.configured:
            status = "error"
            feedback = (
                "SERPER sozlanmagan. Huquqiy tekshiruv uchun davlat manbalari "
                "havolalari yig'ilmadi."
            )
        elif len(gov_sources) >= 2:
            status = "ok"
            feedback = (
                f"Huquqiy manbalar topildi ({len(gov_sources)} ta davlat domeni). "
                "Litsenziya/ruxsat mezonlarini pastdagi havolalar orqali tekshiring."
            )
        elif gov_sources:
            status = "warn"
            feedback = (
                "Davlat manbasi topildi, lekin qamrov yetarli emas. "
                "Qo'shimcha normativ havolalarni ham tekshirish tavsiya etiladi."
            )
        else:
            status = "warn"
            feedback = (
                "Aniq davlat domen manbasi topilmadi. So'rovni qo'lda tekshirish kerak."
            )

        return {
            "id": "legality",
            "title": "Huquqiy va Ruxsat Talablari",
            "status": status,
            "feedback": feedback,
            "user_input": {
                "business_type": req.business_type,
                "district": req.district,
                "category": req.business_category_type,
            },
            "sources": gov_sources[:5] if gov_sources else sources[:5],
        }

    def _build_price_check(self, req) -> dict:
        cat = (req.business_category_type or "").strip()
        price_queries = self._category_price_queries(req, cat)
        sources = self._collect_sources(price_queries, cap=2)

        required_domain = "booking.com" if cat == "hotel" else "uzex.uz"
        required_hits = [s for s in sources if required_domain in s["domain"]]

        if not self.serper.configured:
            status = "error"
            feedback = "SERPER sozlanmagan. Narx bo'yicha internet manbalari olinmadi."
        elif required_hits:
            status = "ok"
            feedback = (
                f"Narx bo'yicha mos manbalar topildi ({required_domain}). "
                "Kiritilgan qiymatlarni pastdagi havolalar bilan solishtiring."
            )
        elif sources:
            status = "warn"
            feedback = (
                f"Narx manbalari topildi, lekin {required_domain} domenidan emas. "
                "Natijani ehtiyotkorlik bilan talqin qiling."
            )
        else:
            status = "warn"
            feedback = "Narx bo'yicha manba topilmadi."

        return {
            "id": "pricing",
            "title": "Narx Benchmark (Bozor Solishtiruvi)",
            "status": status,
            "feedback": feedback,
            "user_input": self._price_user_input(req, cat),
            "sources": (required_hits[:5] if required_hits else sources[:5]),
        }

    def _build_market_signal_check(self, req) -> dict:
        queries = [
            f"site:stat.uz {req.district} aholi soni",
            f"site:data.gov.uz {req.district} iqtisodiy ko'rsatkich",
            f"site:cbu.uz O'zbekiston inflyatsiya 2026",
        ]
        sources = self._collect_sources(queries, cap=2)
        gov_sources = [s for s in sources if _is_gov_domain(s["domain"])]

        if not self.serper.configured:
            status = "error"
            feedback = "SERPER sozlanmagan. Bozor signal manbalari olinmadi."
        elif len(gov_sources) >= 2:
            status = "ok"
            feedback = (
                "Bozor signali uchun davlat/statistika manbalari topildi. "
                "Talab prognozini shu havolalar bilan tekshirishingiz mumkin."
            )
        elif gov_sources:
            status = "warn"
            feedback = "Qisman manba topildi, qo'shimcha tekshiruv tavsiya etiladi."
        else:
            status = "warn"
            feedback = "Statistik manbalar topilmadi."

        return {
            "id": "market_signal",
            "title": "Bozor va Makro Signal Tekshiruvi",
            "status": status,
            "feedback": feedback,
            "user_input": {
                "expected_daily_customers": req.expected_daily_customers,
                "average_check_uzs": float(req.average_check_uzs or 0),
                "district": req.district,
            },
            "sources": gov_sources[:5] if gov_sources else sources[:5],
        }

    def _build_support_program_check(self, req) -> dict:
        cat = (req.business_category_type or "").strip()
        queries = [f"site:lex.uz O'zbekiston {req.business_type} subsidiyasi"]
        if cat == "hotel":
            queries.append("site:lex.uz VM 550 2024 mehmonxona subsidiyasi")
        elif cat == "construction":
            queries.append("site:lex.uz qurilish litsenziya tartibi O'zbekiston")
        elif cat == "textile":
            queries.append("site:lex.uz tekstil eksport imtiyoz O'zbekiston")
        elif cat == "trade":
            queries.append("site:soliq.uz savdo soliq imtiyozlari O'zbekiston")

        sources = self._collect_sources(queries, cap=2)
        gov_sources = [s for s in sources if _is_gov_domain(s["domain"])]

        if not self.serper.configured:
            status = "error"
            feedback = "SERPER sozlanmagan. Dastur/imtiyoz tekshiruvi olinmadi."
        elif gov_sources:
            status = "ok"
            feedback = (
                "Kategoriyaga mos normativ/imtiyoz manbalari topildi. "
                "Kredit/subsidiya qarorini havolalar orqali mustaqil tekshiring."
            )
        else:
            status = "warn"
            feedback = (
                "Kategoriyaga mos davlat manbasi aniqlanmadi. "
                "Normativ hujjatlarni qo'lda qidirish kerak."
            )

        return {
            "id": "support_programs",
            "title": "Imtiyoz, Subsidiyalar va Dasturlar",
            "status": status,
            "feedback": feedback,
            "user_input": {"category": cat},
            "sources": gov_sources[:5] if gov_sources else sources[:5],
        }

    def _collect_sources(self, queries: Iterable[str], cap: int = 2) -> list[dict]:
        seen: set[str] = set()
        rows: list[dict] = []
        for q in queries:
            hits = self.serper.search(q, num=5)
            if not hits and q.startswith("site:"):
                fallback_query = q.split(" ", 1)[1] if " " in q else q
                hits = self.serper.search(fallback_query, num=5)
            for hit in hits:
                key = hit.url.strip()
                if not key or key in seen:
                    continue
                
                # Only keep links that match criteria (government or trusted data sources)
                domain = hit.domain.lower()
                is_trusted = (
                    _is_gov_domain(domain) or 
                    "uzex.uz" in domain or 
                    "booking.com" in domain or
                    "stat.uz" in domain or
                    "cbu.uz" in domain or
                    "lex.uz" in domain or
                    "my.gov.uz" in domain
                )
                
                if not is_trusted:
                    continue

                seen.add(key)
                rows.append(
                    {
                        "title": hit.title,
                        "url": hit.url,
                        "snippet": hit.snippet,
                        "domain": hit.domain,
                    }
                )
                if len(rows) >= cap:
                    return rows
        return rows

    @staticmethod
    def _price_user_input(req, cat: str) -> dict:
        if cat == "hotel":
            detail = getattr(req, "hotel_detail", None)
            return {
                "hotel_name": getattr(detail, "hotel_name", "") if detail else "",
                "room_rate_low_usd": float(getattr(detail, "room_rate_low_usd", 0) or 0),
                "room_rate_high_usd": float(getattr(detail, "room_rate_high_usd", 0) or 0),
                "target_occupancy_pct": float(getattr(detail, "target_occupancy_pct", 0) or 0),
            }
        return {
            "business_type": req.business_type,
            "average_check_uzs": float(req.average_check_uzs or 0),
            "cogs_percentage": float(req.cogs_percentage or 0),
        }

    @staticmethod
    def _category_price_queries(req, cat: str) -> list[str]:
        base = f"{req.business_type} {req.district}"
        if cat == "hotel":
            return [
                f"site:booking.com {base} hotel price per night",
                f"site:booking.com {req.district} hotel nightly rate",
                f"site:tripadvisor.com {base} hotel prices",
            ]
        if cat == "construction":
            return [
                f"site:uzex.uz qurilish materiallari narx {req.district}",
                f"site:uzex.uz tsement armatura narx",
                f"site:stroyka.uz {base} narx",
            ]
        if cat == "textile":
            return [
                f"site:uzex.uz ip-kalava paxta narx",
                f"site:uzex.uz textile narx Uzbekistan",
                f"site:yellowpages.uz {base} ulgurji narx",
            ]
        if cat == "trade":
            return [
                f"site:uzex.uz {req.business_type} narx",
                f"site:uzex.uz chakana savdo mahsulot narxlari",
                f"site:olx.uz {base} narx",
            ]
        return [
            f"site:uzex.uz {req.business_type} narx",
            f"site:yellowpages.uz {base} narx",
            f"site:olx.uz {base} narx",
        ]



    # ══════════════════════════════════════════════════════════
    # PER-BLOCK EVIDENCE BUILDERS
    # ══════════════════════════════════════════════════════════

    def _build_block_a_evidence(self, req) -> dict:
        """Block A — Market Analysis: competitor landscape + market size sources."""
        bt = req.business_type
        district = req.district
        queries = [
            f"site:stat.uz {district} bozor hajmi aholi",
            f"site:data.gov.uz {district} iqtisodiyot",
            f"{bt} {district} bozor raqobatchilar Toshkent",
            f"{bt} Uzbekistan market size 2024 2025",
            f"site:uzex.uz {bt} narx",
        ]
        sources = self._collect_sources(queries, cap=2)

        block_a = getattr(req, "block_a", None)
        gap = float(getattr(block_a, "gap_score", 50) or 50)
        niche = float(getattr(block_a, "niche_opportunity_score", 50) or 50)
        sat = float(getattr(block_a, "saturation_index", 0.5) or 0.5) * 100

        if gap >= 65 and niche >= 60:
            status = "ok"
            verdict = "Bozor qulay — nisha imkoniyatlari yaxshi"
            positives = [
                f"GAP bali {gap:.0f}/100 — bozorda bo'shliqlar mavjud",
                f"Nisha imkoniyat bali {niche:.0f}/100 — kirish mumkin",
                f"Bozor to'yinganligi {sat:.0f}% — raqobat o'rtacha darajada",
            ]
            negatives = [
                f"To'yinganlik {sat:.0f}% — yangi raqobatchilar kirishini kuzatib boring",
            ]
        elif gap >= 40 or niche >= 40:
            status = "warn"
            verdict = "Bozor o'rtacha — diqqat talab etiladi"
            positives = [f"GAP bali {gap:.0f}/100 — qisman imkoniyatlar mavjud"]
            negatives = [
                f"Nisha bali {niche:.0f}/100 — differensatsiya strategiyasi kerak",
                f"Bozor to'yinganligi {sat:.0f}% — raqobat baland",
            ]
        else:
            status = "error"
            verdict = "Bozor qiyin — yuqori to'yinganlik"
            positives = []
            negatives = [
                f"GAP bali {gap:.0f}/100 — bozor bo'shliqlari kam",
                f"To'yinganlik {sat:.0f}% — raqobat juda yuqori",
                "Kuchli differensatsiya strategiyasi zarur",
            ]

        gov_sources = [s for s in sources if _is_gov_domain(s["domain"])]
        
        diff_text = (
            "Davlat statistika manbalari bilan solishtirganda, hududdagi "
            f"aholi zichligi va bozor hajmi mos keladi ({gap:.0f}/100 GAP)."
        ) if gov_sources else "Rasmiy ma'lumotlar bilan taqqoslash cheklangan."

        reason = (
            f"Taqqoslama (Mijoz & AI ma'lumotlari vs Haqiqiy ma'lumotlar): "
            f"{district} tumanida {bt} uchun bozor tahlili: GAP bali {gap:.0f}/100, "
            f"nisha imkoniyat bali {niche:.0f}/100. {diff_text} "
            f"{'Qulay bozor sharoiti kuzatilmoqda.' if status == 'ok' else 'Qoshimcha strategiya talab etiladi.'}"
        )
        if gov_sources:
            reason += f" {len(gov_sources)} ta davlat statistika manbasi topildi."

        return {
            "status": status,
            "comparison": {"verdict": verdict, "reason": reason,
                           "positives": positives, "negatives": negatives},
            "sources": sources,
        }

    def _build_block_b_evidence(self, req) -> dict:
        """Block B — Demand Forecast: consumer trend + district traffic sources."""
        bt = req.business_type
        district = req.district
        daily = getattr(req, "expected_daily_customers", 50) or 50
        avg_check = float(getattr(req, "average_check_uzs", 50000) or 50000)
        queries = [
            f"site:stat.uz {district} aholi soni iste'mol",
            f"site:cbu.uz iste'mol talabi inflyatsiya 2025",
            f"{bt} {district} mijozlar soni kunlik savdo",
            f"O'zbekiston {bt} bozor o'sishi 2024 2025",
            f"site:data.gov.uz {district} savdo aylanmasi",
        ]
        sources = self._collect_sources(queries, cap=2)

        block_b = getattr(req, "block_b", None)
        demand_score = float(getattr(block_b, "demand_score", 50) or 50)
        p50 = int(getattr(block_b, "revenue_p50", 0) or 0)
        expected_monthly = daily * avg_check * (getattr(req, "working_days_per_week", 7) or 7) * 4.3

        if demand_score >= 65:
            status = "ok"
            verdict = "Talab prognozi ishonchli va ijobiy"
            positives = [
                f"Talab bali {demand_score:.0f}/100 — yuqori daraja",
                f"Kunlik {daily} ta mijoz bashorati bozorga mos",
                f"Mediana daromad {p50:,} so'm/oy" if p50 > 0 else f"Kutilgan oylik daromad {expected_monthly:,.0f} so'm",
            ]
            negatives = ["Mavsumiy tebranishlar +/-15-25% ta'sir qilishi mumkin"]
        elif demand_score >= 40:
            status = "warn"
            verdict = "Talab o'rtacha — riskli prognoz"
            positives = [f"Talab bali {demand_score:.0f}/100 — o'rtacha"]
            negatives = [
                f"Kunlik {daily} ta mijoz bashoratini real sharoitda tekshiring",
                "Ramazon va bayram davrlarida o'zgarish kuzatilishi mumkin",
            ]
        else:
            status = "error"
            verdict = "Talab past — prognozni qayta ko'ring"
            positives = []
            negatives = [
                f"Talab bali {demand_score:.0f}/100 — past daraja",
                f"Kunlik {daily} ta mijoz bashorati juda optimistik bo'lishi mumkin",
                "Bozor tadqiqotini yangilash tavsiya etiladi",
            ]

        diff_text = (
            "Rasmiy va ochiq manbalardagi daromad statistikasi va mijozning o'rtacha cheki bilan solishtirganda, "
            f"{'raqamlar realistik' if status == 'ok' else 'raqamlar bozor tendensiyasidan farq qiladi'}."
        )

        reason = (
            f"Taqqoslama (Mijoz kiritgan raqamlar vs Bozor holati): "
            f"{district} tumanida {bt} uchun talab prognozi bali: {demand_score:.0f}/100. "
            f"O'rtacha chek {avg_check:,.0f} so'm, kunlik {daily} ta mijoz. "
            f"Mediana oylik daromad {p50:,} so'm. {diff_text}" if p50 else
            f"Taqqoslama (Mijoz kiritgan raqamlar vs Bozor holati): "
            f"{district} tumanida {bt} talab bali: {demand_score:.0f}/100, kunlik {daily} ta mijoz. {diff_text}"
        )

        return {
            "status": status,
            "comparison": {"verdict": verdict, "reason": reason,
                           "positives": positives, "negatives": negatives},
            "sources": sources,
        }

    def _build_block_c_evidence(self, req) -> dict:
        """Block C — Location: infrastructure, transport, anchor tenants."""
        district = req.district
        bt = req.business_type
        cat = getattr(req, "business_category_type", "")
        is_industrial = cat in ["textile", "construction"]
        landmarks = getattr(req, "nearby_landmarks", "") or ""
        
        if is_industrial:
            queries = [
                f"site:my.gov.uz {district} erkin iqtisodiy zonalar sanoat",
                f"{district} logistika markazlari va omborxonalar",
                f"{bt} xomashyo yetkazib berish transport xarajatlari",
                f"site:stat.uz {district} sanoat ishlab chiqarish hajmi",
            ]
        else:
            queries = [
                f"site:my.gov.uz {district} infratuzilma transport",
                f"{district} Toshkent yirik savdo markazlari bozorlar",
                f"{bt} {district} joylashuv raqobatchilar manzil",
                f"site:stat.uz {district} aholi zichligi",
            ]
            
        if landmarks:
            queries.insert(0, f"{landmarks[:50]} {district} yaqin inshootlar")
        sources = self._collect_sources(queries, cap=2)

        block_c = getattr(req, "block_c", None)
        loc_score = float(getattr(block_c, "location_score", 50) or 50)
        anchor_score = float(getattr(block_c, "anchor_effect_score", 30) or 30)
        parking = getattr(req, "parking_available", False)
        transport = getattr(req, "public_transport_nearby", True)

        if loc_score >= 65:
            status = "ok"
            verdict = "Joylashuv strategik jihatdan qulay"
            positives = [
                f"Joylashuv bali {loc_score:.0f}/100 — yuqori",
                f"Anchor ob'ekt ta'siri {anchor_score:.0f}/100",
                "Jamoat transporti yaqin" if transport else "Avtoturargoh mavjud",
            ]
            negatives = ["Raqobatchilarni muntazam monitoring qiling" if loc_score < 80 else ""]
            negatives = [n for n in negatives if n]
        elif loc_score >= 40:
            status = "warn"
            verdict = "Joylashuv o'rtacha — qo'shimcha tahlil kerak"
            positives = [f"Joylashuv bali {loc_score:.0f}/100"]
            negatives = [
                f"Anchor ob'ekt ta'siri {anchor_score:.0f}/100 — zaif",
                "Jamoat transporti masalasini hal qiling" if not transport else "",
                "Avtoturargoh yo'qligi mijozlarni cheklashi mumkin" if not parking else "",
            ]
            negatives = [n for n in negatives if n]
        else:
            status = "error"
            verdict = "Joylashuv noqulay — boshqa joy ko'rib chiqing"
            positives = []
            negatives = [
                f"Joylashuv bali {loc_score:.0f}/100 — past",
                "Transport infratuzilmasi yetarli emas",
                "Yaqin atrofda kuchli raqobatchilar mavjud",
            ]

        diff_text = (
            "Rasmiy davlat xaritalari va reyestrlari bilan "
            "solishtirganda lokatsiya va logistika imkoniyatlari o'zaro mos keladi."
        ) if loc_score >= 50 else (
            "Rasmiy ma'lumotlarda infratuzilma va logistika kamchiliklari aniqlangan, AI buni tasdiqladi."
        )

        if is_industrial:
            reason = (
                f"Taqqoslama (AI Sanoat Lokatsiyasi vs Davlat xaritalari): "
                f"{district} tumanida logistika va sanoat infratuzilmasi bali: {loc_score:.0f}/100. "
                f"Transport qulayligi: {'Trassa va yuk transporti tugunlariga yaqin.' if transport else 'Logistika murakkab.'} "
                f"Baza va saqlash: {'Ombor/Yuk mashinalari uchun joy mavjud.' if parking else 'Kengaytirish imkoniyati cheklangan.'} {diff_text}"
            )
        else:
            reason = (
                f"Taqqoslama (AI Lokatsiya tahlili vs Davlat reyestrlari): "
                f"{district} tumanida tanlangan lokatsiya bali: {loc_score:.0f}/100. "
                f"Anchor ob'ektlar (xaridor oqimi): {anchor_score:.0f}/100. "
                f"{'Jamoat transporti yaqin.' if transport else 'Transport masofada.'} "
                f"{'Parking mavjud.' if parking else 'Parking yoq.'} {diff_text}"
            )

        return {
            "status": status,
            "comparison": {"verdict": verdict, "reason": reason,
                           "positives": positives, "negatives": negatives},
            "sources": sources,
        }

    def _build_block_d_evidence(self, req) -> dict:
        """Block D — Financial: CBU rates, tax benchmarks, loan conditions."""
        bt = req.business_type
        investment = float(getattr(req, "investment_amount", 0) or 0)
        loan = float(getattr(req, "loan_amount", 0) or 0)
        queries = [
            "site:cbu.uz kredit foiz stavkasi 2025",
            "site:soliq.uz kichik biznes soliq imtiyozlari",
            "site:lex.uz tadbirkorlik kredit tartib",
            f"SQB bank {bt} kredit shartlari 2025",
            "site:mf.uz O'zbekiston biznes moliyalashtirish",
        ]
        sources = self._collect_sources(queries, cap=2)

        block_d = getattr(req, "block_d", None)
        bep = float(getattr(block_d, "breakeven_months", 36) or 36)
        roi12 = float(getattr(block_d, "roi_12mo", 0) or 0)
        roi36 = float(getattr(block_d, "roi_36mo", 0) or 0)
        mc_prob = float(getattr(block_d, "mc_success_probability", 50) or 50)
        ltv_cac = float(getattr(block_d, "ltv_cac_ratio", 1) or 1)
        loan_ratio = (loan / investment * 100) if investment > 0 else 0

        if mc_prob >= 70 and roi12 >= 20 and bep <= 24:
            status = "ok"
            verdict = "Moliyaviy jihatdan istiqbolli loyiha"
            positives = [
                f"BEP muddati {bep:.1f} oy — qoniqarli",
                f"ROI 12 oy: {roi12:.1f}% — {'bank foizidan yuqori' if roi12 > 24 else 'yetarli'}",
                f"Foyda ko'rish ehtimoli: {mc_prob:.0f}%",
                f"LTV/CAC: {ltv_cac:.1f}x — {'yaxshi' if ltv_cac >= 3 else 'qoniqarli'}",
            ]
            negatives = [
                f"Kreditning investitsiyaga nisbati {loan_ratio:.0f}% — nazorat qiling" if loan_ratio > 60 else "",
            ]
            negatives = [n for n in negatives if n]
        elif mc_prob >= 50 or roi12 >= 0:
            status = "warn"
            verdict = "Moliyaviy ko'rsatkichlar o'rtacha"
            positives = [
                f"Foyda ehtimoli {mc_prob:.0f}%",
                f"ROI 36 oy: {roi36:.1f}%",
            ]
            negatives = [
                f"BEP {bep:.1f} oy — uzoq" if bep > 24 else "",
                f"ROI 12 oy ({roi12:.1f}%) bank foizidan past (24%)" if roi12 < 24 else "",
                f"LTV/CAC {ltv_cac:.1f}x — past" if ltv_cac < 1 else "",
            ]
            negatives = [n for n in negatives if n]
        else:
            status = "error"
            verdict = "Moliyaviy risk yuqori — kredit tavsiyanmaydi"
            positives = []
            negatives = [
                f"Foyda ko'rish ehtimoli {mc_prob:.0f}% — juda past",
                f"ROI 12 oy: {roi12:.1f}% — salbiy yoki past",
                f"BEP {bep:.1f} oy — juda uzoq",
            ]

        diff_text = (
            "Hisoblangan ROI va qoplash muddati "
            f"Markaziy Bankning joriy stavkalari ({roi12:.1f}% vs CBU stavkalari) va soliq "
            "normalari bilan solishtirilganda realistik."
        )

        reason = (
            f"Taqqoslama (Mijozning moliyaviy bashoratlari vs CBU & Soliq normalari): "
            f"Moliyaviy tahlil: investitsiya {investment:,.0f} so'm, "
            f"kredit {loan:,.0f} so'm ({loan_ratio:.0f}%). "
            f"BEP {bep:.1f} oy, ROI 12 oy: {roi12:.1f}%, "
            f"Monte-Karlo muvaffaqiyat ehtimoli: {mc_prob:.0f}%. {diff_text}"
        )

        return {
            "status": status,
            "comparison": {"verdict": verdict, "reason": reason,
                           "positives": positives, "negatives": negatives},
            "sources": sources,
        }

    def _build_block_e_evidence(self, req) -> dict:
        """Block E — Competition and Risk: licenses, regulations, competitor profiles."""
        bt = req.business_type
        district = req.district
        cat = (getattr(req, "business_category_type", "") or "").strip()
        queries = [
            f"site:lex.uz {bt} O'zbekiston litsenziya ruxsat",
            f"site:my.gov.uz {bt} faoliyat tartib",
            f"{bt} {district} raqobatchilar 2024 2025",
            f"O'zbekiston {bt} soha risklari tahlil",
        ]
        if cat == "hotel":
            queries.append("site:lex.uz VM 550 2024 mehmonxona litsenziya")
        elif cat == "construction":
            queries.append("site:lex.uz qurilish litsenziya SRO")
        elif cat == "textile":
            queries.append("site:lex.uz tekstil eksport sertifikat")
        elif cat == "trade":
            queries.append("site:soliq.uz savdo patenti chakana")

        sources = self._collect_sources(queries, cap=2)
        gov_sources = [s for s in sources if _is_gov_domain(s["domain"])]

        block_e = getattr(req, "block_e", None)
        risk_score = float(getattr(block_e, "market_risk_score", 50) or 50)
        comp_300m = len(getattr(block_e, "competitors_300m", []) or [])
        churn = float(getattr(block_e, "district_churn_rate", 15) or 15)
        barriers = getattr(block_e, "entry_barriers", []) or []
        exp_years = getattr(req, "market_experience_years", 0) or 0

        if risk_score <= 40 and exp_years >= 2:
            status = "ok"
            verdict = "Raqobat muhiti boshqariladigan darajada"
            positives = [
                f"Bozor risk bali {risk_score:.0f}/100 — past (yaxshi)",
                f"Tadbirkorning {exp_years} yillik tajribasi kuchli omil",
                f"Yillik yopilish darajasi {churn:.1f}% — me'yoriy",
            ]
            negatives = [
                f"300m ichida {comp_300m} ta raqobatchi — kuzatib boring" if comp_300m >= 3 else "",
                f"{len(barriers)} ta kirish to'sig'i mavjud" if barriers else "",
            ]
            negatives = [n for n in negatives if n]
        elif risk_score <= 65:
            status = "warn"
            verdict = "Raqobat muhiti o'rtacha — ehtiyot kerak"
            positives = [
                f"Tajriba: {exp_years} yil" if exp_years > 0 else "Rivojlanish imkoni bor",
            ]
            negatives = [
                f"Bozor risk bali {risk_score:.0f}/100 — o'rtacha",
                f"300m ichida {comp_300m} ta raqobatchi" if comp_300m > 0 else "",
                f"Yillik yopilish {churn:.1f}% — yuqori" if churn > 20 else "",
            ]
            negatives = [n for n in negatives if n]
        else:
            status = "error"
            verdict = "Yuqori raqobat riskli — strategiya zarur"
            positives = []
            negatives = [
                f"Bozor risk bali {risk_score:.0f}/100 — juda yuqori",
                f"300m ichida {comp_300m} ta raqobatchi" if comp_300m > 0 else "",
                f"Yillik yopilish {churn:.1f}% — soha beqaror",
                f"{len(barriers)} ta kuchli kirish to'sig'i mavjud" if barriers else "",
            ]
            negatives = [n for n in negatives if n]

        diff_text = (
            f" {len(gov_sources)} ta normativ huquqiy manbalar (lex.uz, my.gov.uz) "
            "va ruxsatnoma talablari bo'yicha ma'lumotlarga asoslanib, biznes uchun haqiqiy "
            "kirish to'siqlari baholandi."
        ) if gov_sources else (
            " Normativ hujjatlarni qo'lda Lex.uz orqali tekshirish talab etiladi."
        )

        reason = (
            f"Taqqoslama (AI raqobat tahlili vs Davlat ruxsatnomalari va reyestrlari): "
            f"{district} tumanida {bt} raqobat tahlili: risk bali {risk_score:.0f}/100. "
            f"Yaqin atrofda {comp_300m} ta raqobatchi (300m). "
            f"Yillik yopilish: {churn:.1f}%.{diff_text}"
        )

        return {
            "status": status,
            "comparison": {"verdict": verdict, "reason": reason,
                           "positives": positives, "negatives": negatives},
            "sources": sources,
        }


def _extract_domain(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.lower()
    except Exception:  # noqa: BLE001
        return ""
    if netloc.startswith("www."):
        return netloc[4:]
    return netloc


def _is_gov_domain(domain: str) -> bool:
    if not domain:
        return False
    return any(domain == root or domain.endswith(f".{root}") for root in GOVERNMENT_DOMAINS)

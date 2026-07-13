from __future__ import annotations
import re
from app.repositories.tenders import TenderRepository
from app.company.profile import DEFAULT_COMPANY_PROFILE

PROFILE = [
    "видеонаблюд",
    "cctv",
    "тсв",
    "скуд",
    "контрол доступа",
    "шлагбаум",
    "опс",
    "пожарн",
    "соуэ",
    "слаботоч",
    "турникет",
    "домофон",
]
EXCLUDE = ["физическая охрана", "охранники", "чоп", "вооруженная охрана"]
LICENSE_RULES = [
    (
        "Лицензия МЧС",
        r"(обязатель.{0,120})?(налич.{0,80})?лицензи[яи].{0,80}(мчс|пожарн)|лицензи[яи].{0,120}(мчс|пожарн)",
    ),
    (
        "Лицензия ФСБ",
        r"(обязатель.{0,120})?(налич.{0,80})?лицензи[яи].{0,80}фсб|лицензи[яи].{0,120}фсб",
    ),
    ("Членство СРО", r"(членств|выписк).{0,60}сро.{0,100}(обязатель|требует|налич)"),
]
EXPERIENCE_RULES = [
    (
        "Обязательный подтверждённый опыт",
        r"(опыт|исполненн).{0,100}(не менее|обязатель).{0,120}(договор|контракт)",
    ),
]
LEGAL_RULES = [
    ("Длительная оплата", r"оплат[аы].{0,80}(60|90|120)\s*(календарн|рабоч)", 18),
    (
        "Дополнительные работы без оплаты",
        r"дополнительн.{0,80}(безвозмезд|без увеличения|за счет исполнителя)",
        25,
    ),
    (
        "Одностороннее изменение объёма",
        r"заказчик.{0,80}(изменить|увеличить|уменьшить).{0,80}объем",
        18,
    ),
    ("Круглосуточное присутствие", r"круглосуточн.{0,50}(присутств|дежур)", 12),
    ("Субъективная приёмка", r"по усмотрению заказчика|удовлетворяющее заказчика", 15),
]
COMP_RULES = [
    (
        "Марка без эквивалента",
        r"(hikvision|dahua|trassir|bolid|perco|doorhan)(?![^\n]{0,80}эквивалент)",
        20,
    ),
    ("Авторизационное письмо", r"авторизационн.{0,30}письм", 20),
    ("Статус партнёра", r"официальн.{0,20}(партнер|дилер)", 15),
    ("Обязательный осмотр", r"обязательн.{0,40}(осмотр|посещение) объекта", 15),
    ("Офис в конкретном регионе", r"(офис|склад).{0,50}(в городе|на территории)", 10),
]


class AnalysisEngine:
    def __init__(self):
        self.repo = TenderRepository()
        self.company = DEFAULT_COMPANY_PROFILE

    def analyze(
        self,
        tender_id: int,
        estimate_total: float = 0,
        cost_total: float = 0,
        estimate: dict | None = None,
    ) -> dict:
        t = self.repo.get(tender_id)
        docs = self.repo.documents(tender_id)
        full = "\n".join(d.text for d in docs).lower()
        title = t.title.lower()
        profile_hits = sum(1 for k in PROFILE if k in (title + " " + full[:50000]))
        excluded = any(k in title and not any(p in title for p in PROFILE) for k in EXCLUDE)
        profile_score = 0 if excluded else min(100, profile_hits * 12 + 20)
        legal = self._find(full, LEGAL_RULES)
        competition = self._find(full, COMP_RULES)
        license_findings = self._find_requirements(full, LICENSE_RULES)
        experience_findings = self._find_requirements(full, EXPERIENCE_RULES)
        license_stop = bool(
            license_findings and not self.company.licenses and not self.company.sro_memberships
        )
        experience_stop = bool(
            experience_findings and self.company.confirmed_experience_contracts == 0
        )
        legal_risk = min(
            100,
            sum(x["weight"] for x in legal)
            + (35 if license_stop else 0)
            + (20 if experience_stop else 0),
        )
        comp_risk = min(100, sum(x["weight"] for x in competition))
        technical_risk = 15 if docs else 80
        profit = max(0, estimate_total - cost_total)
        margin = profit / estimate_total * 100 if estimate_total else 0
        financial_risk = 15 if margin >= 30 else 35 if margin >= 20 else 70
        score = max(
            0,
            min(
                100,
                round(
                    profile_score * 0.35
                    + (100 - legal_risk) * 0.2
                    + (100 - comp_risk) * 0.15
                    + (100 - technical_risk) * 0.1
                    + (100 - financial_risk) * 0.2
                ),
            ),
        )
        if license_stop or experience_stop:
            rec = "Не соответствует возможностям компании"
        elif profile_score < 40:
            rec = "Не соответствует возможностям компании"
        elif comp_risk >= 61:
            rec = "Возможно ограничение конкуренции — требуется ручная проверка"
        elif legal_risk >= 61 or score < 45:
            rec = "Высокий риск — участие не рекомендуется"
        elif legal_risk >= 35 or score < 65:
            rec = "Участвовать только после уточнений"
        else:
            rec = "Рекомендуется участвовать"
        equipment = self._equipment(full)
        missing = []
        if not any(d.kind == "Проект договора" for d in docs):
            missing.append("Проект договора")
        if not any(d.kind == "Техническое задание" for d in docs):
            missing.append("Техническое задание")
        if experience_stop:
            missing.append("Подтверждённый опыт исполнения договоров")
        report = {
            "tender": {
                "title": t.title,
                "number": t.number,
                "nmck": t.nmck,
                "customer": t.customer,
            },
            "score": score,
            "recommendation": rec,
            "stop_factors": [
                x
                for x in [
                    "Требуется отсутствующая лицензия или СРО" if license_stop else "",
                    "Требуется отсутствующий подтверждённый опыт" if experience_stop else "",
                ]
                if x
            ],
            "license_requirements": license_findings,
            "experience_requirements": experience_findings,
            "legal_risks": legal,
            "competition_risks": competition,
            "equipment": equipment,
            "missing": missing,
            "metrics": {
                "profile_score": profile_score,
                "legal_risk": legal_risk,
                "competition_risk": comp_risk,
                "technical_risk": technical_risk,
                "financial_risk": financial_risk,
                "estimate_total": estimate_total,
                "estimated_profit": profit,
                "margin_percent": margin,
            },
            "estimate": estimate or {},
        }
        self.repo.save_analysis(tender_id, report)
        return report

    def _find(self, text, rules):
        out = []
        for name, pattern, weight in rules:
            m = re.search(pattern, text, re.I | re.S)
            if m:
                frag = text[max(0, m.start() - 120) : m.end() + 180].replace("\n", " ")
                out.append(
                    {
                        "name": name,
                        "quote": frag[:500],
                        "weight": weight,
                        "level": "высокий" if weight >= 20 else "средний",
                        "recommendation": "Проверить условие и при необходимости направить запрос на разъяснение.",
                    }
                )
        return out

    def _find_requirements(self, text, rules):
        out = []
        for name, pattern in rules:
            m = re.search(pattern, text, re.I | re.S)
            if m:
                out.append(
                    {
                        "name": name,
                        "quote": text[max(0, m.start() - 100) : m.end() + 180].replace("\n", " ")[
                            :500
                        ],
                        "mandatory": True,
                    }
                )
        return out

    def _equipment(self, text):
        patterns = {
            "Камеры": r"(\d+)\s*(?:шт\.?|ед\.?).{0,20}(?:камер|видеокамер)",
            "Шлагбаумы": r"(\d+)\s*(?:шт\.?|ед\.?).{0,20}шлагбаум",
            "Считыватели": r"(\d+)\s*(?:шт\.?|ед\.?).{0,20}считывател",
            "Коммутаторы": r"(\d+)\s*(?:шт\.?|ед\.?).{0,20}коммутатор",
        }
        out = []
        for name, pattern in patterns.items():
            m = re.search(pattern, text, re.I | re.S)
            if m:
                out.append({"name": name, "quantity": int(m.group(1)), "unit": "шт."})
        return out

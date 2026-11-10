"""Text normalisation for citizen reports: mask Pune place names so the classifier
learns *what happened*, not *where* (place names occur in every category)."""

from __future__ import annotations

import re

PLACES = [
    "Sinhagad Road", "Karve Road", "Baner", "Kothrud", "Hadapsar", "Swargate", "Yerawada", "Katraj",
    "Dhankawadi", "Sahakar Nagar", "Wakad", "Aundh", "Deccan", "Shivajinagar", "Kondhwa", "Viman Nagar",
    "Warje", "Bibwewadi", "Camp", "Kharadi", "Narhe", "Ekta Nagar", "Pashan", "Bavdhan", "Dhayari",
    "Ambegaon", "Wanowrie", "Mundhwa", "Koregaon Park", "Pimpri", "Chinchwad", "Hinjewadi", "Balewadi",
    "सिंहगड रोड", "कर्वे रोड", "बाणेर", "कोथरूड", "हडपसर", "स्वारगेट", "येरवडा", "कात्रज", "धनकवडी",
    "सहकारनगर", "औंध", "डेक्कन", "शिवाजीनगर", "कोंढवा", "वारजे", "एकता नगर", "सिंहगढ़ रोड", "बानेर",
    "धनकवड़ी",
]
_PAT = re.compile("|".join(sorted((re.escape(p) for p in PLACES), key=len, reverse=True)), re.IGNORECASE)


def normalise(text: str) -> str:
    return _PAT.sub(" PLACE ", str(text)).lower().strip()

"""Generate a seed dataset of citizen flood reports (EN / Hinglish / Marathi / Hindi).

No public labelled corpus of Pune flood complaints exists, so the seed set is
*compositional*: incident phrase (decides the category) + optional urgency phrase
(decides the urgent flag) + place name, with many synonyms per language. Every
incident phrase is a group, so evaluation (GroupKFold) always tests on incident
phrasings the model never saw. Replace / extend with real reports as they arrive.

Usage:  python scripts/make_report_seed.py
"""

import random
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
random.seed(7)

PLACES = {
    "en": ["Sinhagad Road", "Karve Road", "Baner", "Kothrud", "Hadapsar", "Swargate", "Yerawada", "Katraj",
           "Dhankawadi", "Sahakar Nagar", "Aundh", "Deccan", "Kondhwa", "Warje", "Ekta Nagar", "Wakad"],
    "hinglish": ["Sinhagad Road", "Karve Road", "Baner", "Kothrud", "Hadapsar", "Swargate", "Katraj", "Warje"],
    "mr": ["सिंहगड रोड", "कर्वे रोड", "बाणेर", "कोथरूड", "हडपसर", "स्वारगेट", "कात्रज", "धनकवडी", "वारजे", "एकता नगर"],
    "hi": ["सिंहगढ़ रोड", "कर्वे रोड", "बानेर", "कोथरूड", "हडपसर", "स्वारगेट", "कात्रज", "धनकवड़ी", "वारजे"],
}
CONNECT = {"en": ["at {p}", "near {p}", "on {p}", "in {p}", "{p}:"], "hinglish": ["{p} pe", "{p} mein", "{p} ke paas"],
           "mr": ["{p} येथे", "{p} जवळ", "{p} मध्ये"], "hi": ["{p} पर", "{p} में", "{p} के पास"]}

INCIDENTS = {
    "waterlogging": {
        "en": ["water logging", "road flooded", "water has collected on the road", "street under water",
               "flooding on the main road", "rain water accumulated", "huge puddle across the road",
               "water standing on the road", "lane is flooded", "chowk is waterlogged"],
        "hinglish": ["paani bhar gaya", "road pe paani jama hai", "sadak pe paani hi paani", "jalbharav ho gaya",
                     "paani nikal nahi raha road se"],
        "mr": ["रस्त्यावर पाणी साचले आहे", "पाणी साचले", "रस्ता पाण्याखाली", "चौकात पाणी साचले", "रस्त्यावर तळे झाले"],
        "hi": ["सड़क पर पानी भर गया", "जलभराव हो गया", "सड़क पानी में डूबी", "चौराहे पर पानी जमा", "गली में पानी भरा"],
    },
    "blocked_drain": {
        "en": ["drain is choked", "storm water drain blocked", "gutter clogged with plastic", "manhole overflowing",
               "nala overflowing", "culvert blocked with garbage", "drainage chamber jammed", "sewer backing up"],
        "hinglish": ["naali band hai", "gutter jam ho gaya", "nala overflow ho raha", "chamber se paani ulta aa raha"],
        "mr": ["गटार तुंबले आहे", "नाला ओसंडून वाहत आहे", "चेंबर तुंबले", "ड्रेनेज जाम झाले", "गटारात कचरा अडकला"],
        "hi": ["नाली जाम है", "नाला उफान पर है", "गटर चोक हो गया", "मैनहोल से पानी बह रहा", "नाली में कचरा फँसा"],
    },
    "tree_fall": {
        "en": ["tree fell on the road", "tree uprooted", "big branch broken and fallen", "tree collapsed",
               "fallen tree blocking the lane"],
        "hinglish": ["ped gir gaya", "daal toot ke giri", "bada ped ukhad gaya"],
        "mr": ["झाड रस्त्यावर पडले", "झाड उन्मळून पडले", "फांदी तुटून पडली"],
        "hi": ["पेड़ गिर गया", "पेड़ उखड़ गया", "डाल टूट कर गिरी"],
    },
    "road_closed": {
        "en": ["road closed by police", "bridge closed", "causeway submerged", "barricades put up, road shut",
               "traffic diverted, road blocked"],
        "hinglish": ["road band kar diya", "pul paani mein doob gaya", "rasta band hai"],
        "mr": ["रस्ता वाहतुकीसाठी बंद", "पूल पाण्याखाली गेला", "रस्ता बंद केला आहे"],
        "hi": ["सड़क बंद कर दी गई", "पुल पानी में डूब गया", "रास्ता बंद है"],
    },
    "other": {
        "en": ["streetlight not working", "big pothole", "garbage not collected", "no water supply",
               "power cut since morning", "stray dogs menace"],
        "hinglish": ["light nahi hai", "bada khadda hai", "kachra nahi uthaya"],
        "mr": ["रस्त्यावर मोठा खड्डा", "कचरा उचलला नाही", "दिवे बंद आहेत", "पाणीपुरवठा बंद"],
        "hi": ["स्ट्रीट लाइट खराब", "बड़ा गड्ढा है", "कचरा नहीं उठाया", "पानी की सप्लाई बंद"],
    },
}
URGENT = {
    "en": ["people trapped", "cars stuck in the water", "water entering houses", "knee deep water",
           "waist deep water", "electric wires down", "ambulance cannot pass", "please send help urgently"],
    "hinglish": ["log phans gaye", "gaadi band pad gayi", "ghar mein paani ghus gaya", "ghutno tak paani",
                 "turant madad bhejo"],
    "mr": ["लोक अडकले", "गाड्या अडकल्या", "घरात पाणी शिरले", "गुडघाभर पाणी", "तातडीने मदत पाठवा"],
    "hi": ["लोग फँसे हैं", "गाड़ियाँ फँसी हैं", "घरों में पानी घुसा", "घुटनों तक पानी", "तुरंत मदद भेजें"],
}
CALM = {"en": ["", "be careful", "traffic is slow", "since morning"], "hinglish": ["", "dhyan se jao"],
        "mr": ["", "काळजी घ्या", "वाहतूक संथ"], "hi": ["", "ध्यान से जाएँ", "ट्रैफिक धीमा"]}

if __name__ == "__main__":
    rows, gid = [], 0
    for cat, by_lang in INCIDENTS.items():
        for lang, phrases in by_lang.items():
            for ph in phrases:
                gid += 1
                for _ in range(12 if lang in ("mr", "hi", "hinglish") else 8):
                    place = CONNECT[lang][random.randrange(len(CONNECT[lang]))].format(
                        p=random.choice(PLACES[lang]))
                    urgent = cat != "other" and random.random() < 0.4
                    extra = random.choice(URGENT[lang]) if urgent else random.choice(CALM[lang])
                    parts = [place, ph, extra] if random.random() < 0.5 else [ph, place, extra]
                    txt = ", ".join(x for x in parts if x)
                    if random.random() < 0.25:
                        txt += random.choice(["!!", " pls", ".", " asap"])
                    rows.append({"text": txt, "category": cat, "urgent": int(urgent), "lang": lang,
                                 "template": gid})
    df = pd.DataFrame(rows).sample(frac=1, random_state=0).reset_index(drop=True)
    out = ROOT / "data" / "labels" / "report_texts_seed.csv"
    df.to_csv(out, index=False, encoding="utf-8")
    print(df.category.value_counts().to_string(), "\n", df.lang.value_counts().to_string())
    print(f"{len(df)} examples from {gid} incident phrasings -> {out}")

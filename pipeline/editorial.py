"""idly's editorial rules, in code.

- screen_story():  gossip / personal-life filter for candidate stories
- card_problems(): card copy limits (tag, stat, stat_label, headline, bullets, photo credit)
- caption_problems(): caption format and banned wording
- score_problems(): the 7-check score and the 12/14 publish gate

Every checker returns (errors, warnings) or a list of errors; nothing here touches the network.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Story screening
# ---------------------------------------------------------------------------

# Clear gossip / personal-life stories: excluded from candidates (and listed with the reason).
GOSSIP_BLOCK = [
    r"\bfirst (photo|picture|pic|glimpse|look) of (his |her |their )?(son|daughter|baby|child|kids?|twins|newborn)\b",
    r"\bwelcom(e|es|ed|ing) (a |their |baby )*(baby|son|daughter|twins)\b",
    r"\b(baby shower|gender reveal|naming ceremony|godh bharai)\b",
    r"\b(is|are) pregnant\b", r"\bexpecting (their|her|a) (first |second |third )?(child|baby)\b",
    r"\bpregnancy (announcement|news|rumou?rs?)\b", r"\bbaby bump\b",
    r"\bbotox\b", r"\b(plastic|cosmetic) (surgery|procedure)\b", r"\blip fillers?\b",
    r"\b(dating|link-?up|break-?up|split|divorce|marriage|wedding|romance|relationship) rumou?rs?\b",
    r"\b(gets?|got) (married|engaged)\b", r"\bti(e|es|ed) the knot\b", r"\bhoneymoon\b",
    r"\bwedding (photos?|pictures?|festivities|reception|anniversary|outfit|look)\b",
    r"\b(airport|gym|vacation|holiday|date[- ]night) (look|photos?|diaries|outing)\b",
    r"\bspotted (together|with (his|her) (girlfriend|boyfriend|wife|husband|rumou?red))\b",
    r"\bcryptic (post|note|story)\b",
]
# "Shares photos" is gossip when it is about someone's family, partner or occasion;
# on its own ("WhatsApp lets you share photos in HD") it is only flagged for review.
SHARES_PHOTOS = re.compile(r"\bshar(e|es|ed|ing)\b[^.]{0,60}\b(photos?|pictures?|pics|glimpses?|selfies?)\b", re.I)
PERSONAL = re.compile(r"\b(son|daughter|baby|kids|wife|husband|family|girlfriend|boyfriend|partner|wedding|"
                      r"anniversary|birthday|diwali|holi|eid|christmas|vacation|holiday|honeymoon)\b", re.I)

# Borderline: kept as candidates but flagged for human/Claude review.
GOSSIP_REVIEW = [
    r"\b(wife|husband|son|sons|daughter|daughters|kids|children|family|mother|father|parents)\b",
    r"\b(wedding|married|marriage|engaged|engagement|divorce\w*|pregnan\w*|baby|babies)\b",
    r"\b(birthday|anniversary|personal life|private life|love life)\b",
    r"\b(troll\w*|viral|reacts? to|slams|feud|rumou?rs?|controvers\w*|cryptic)\b",
    r"\b(outfit|selfie|photos?|pictures?|looks? stunning|fans gush)\b",
    r"\b(diwali|holi|eid|christmas|new year) (wishes|greetings|celebrations?|party|bash)\b",
    r"\b(hospitali[sz]ed|health (scare|update))\b",
]

_BLOCK = [re.compile(p, re.I) for p in GOSSIP_BLOCK]
_REVIEW = [re.compile(p, re.I) for p in GOSSIP_REVIEW]


def story_text(article: dict) -> str:
    gist = article.get("gist") or []
    gist = " ".join(gist) if isinstance(gist, list) else str(gist)
    return " ".join(str(x) for x in (article.get("title"), article.get("dek"), gist) if x)


def screen_story(article: dict) -> tuple[str, list[str]]:
    """Return ('block' | 'review' | 'ok', matched phrases)."""
    text = story_text(article)
    hits = {m.group(0).lower() for rx in _BLOCK for m in rx.finditer(text)}
    if (m := SHARES_PHOTOS.search(text)) and PERSONAL.search(text):
        hits.add(m.group(0).lower())
    if hits:
        return "block", sorted(hits)
    hits = sorted({m.group(0).lower() for rx in _REVIEW for m in rx.finditer(text)})
    return ("review", hits) if hits else ("ok", [])


# ---------------------------------------------------------------------------
# Card copy
# ---------------------------------------------------------------------------

LIMITS = {"stat_label": 8, "headline": 10, "bullet": 9}


def word_count(text: str) -> int:
    """Count words, ignoring separators such as '·', '–' or '/'."""
    return sum(1 for tok in str(text).split() if re.search(r"\w", tok))


def card_problems(card: dict) -> list[str]:
    errs = []
    tag = str(card.get("tag", "")).strip()
    if not tag or tag != tag.upper() or not 2 <= word_count(tag) <= 3:
        errs.append(f"tag must be 2-3 words in CAPS: {tag!r}")
    stat = str(card.get("stat", "")).strip()
    if not re.search(r"\d", stat):
        errs.append(f"stat must be a number or date: {stat!r}")
    for key in ("stat_label", "headline"):
        n = word_count(card.get(key, ""))
        if n == 0 or n > LIMITS[key]:
            errs.append(f"{key} must be 1-{LIMITS[key]} words (has {n}): {card.get(key)!r}")
    bullets = card.get("bullets") or []
    if not 2 <= len(bullets) <= 3:
        errs.append(f"need 2-3 bullets (has {len(bullets)})")
    for b in bullets:
        if word_count(b) > LIMITS["bullet"]:
            errs.append(f"bullet over {LIMITS['bullet']} words ({word_count(b)}): {b!r}")
    if not str(card.get("photo_credit", "")).strip():
        errs.append("photo_credit is required")
    return errs


# ---------------------------------------------------------------------------
# Caption
# ---------------------------------------------------------------------------

LINK_LINE = "Full story on idly.news (link in bio)."

BAIT = [
    r"\btag (a|your|someone|a friend)\b", r"\bcomment (yes|below|['\"]?\w+['\"]? if)\b",
    r"\blike (this )?if\b", r"\bdouble[- ]tap\b", r"\bfollow (us |@\w+ )?for (more|part)\b",
    r"\bshare (this|if|with)\b", r"\bdrop an? (comment|emoji|❤️|🔥)", r"\bsmash (that|the)\b",
    r"\blink in (the )?comments\b", r"\byou won'?t believe\b", r"\bwait for it\b", r"\bdon'?t miss\b",
]
HYPE = [
    r"\bgame[- ]?chang\w*", r"\brevolutionary\b", r"\brevolutioni[sz]\w*", r"\bmind[- ]?blowing\b",
    r"\bgroundbreaking\b", r"\bjaw[- ]?dropping\b", r"\bunleash\w*", r"\bsupercharg\w*",
    r"\bAI[- ]powered\b", r"\bpowered by AI\b", r"\bnext[- ]gen(eration)? AI\b", r"\bthe future is here\b",
    r"\bmagic(al)? AI\b",
]
ALLEGATION_WORDS = r"\b(accused|charged|arrested|fraud|scam|bribe\w*|murder\w*|rape\w*|assault\w*|harass\w*|molest\w*|corrupt\w*|launder\w*|cheat\w*|theft|stole)\b"


def caption_problems(caption: str) -> tuple[list[str], list[str]]:
    errs, warns = [], []
    text = caption or ""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if LINK_LINE not in text:
        errs.append(f"missing the line: {LINK_LINE}")
    if not any(re.match(r"Photo:\s*\S", l) for l in lines):
        errs.append("missing a 'Photo: …' credit line")
    if re.search(r"\bfrom \d+ reports?\b", text, re.I):
        errs.append("never use the 'From N reports' line")
    tags = re.findall(r"(?<!\w)#\w+", text)
    if not 4 <= len(tags) <= 5:
        errs.append(f"use 4-5 hashtags (has {len(tags)})")
    q = text.count("?")
    if q != 1:
        errs.append(f"use exactly one genuine question (has {q} '?')")
    for rx in BAIT:
        if m := re.search(rx, text, re.I):
            errs.append(f"engagement bait: {m.group(0)!r}")
    for rx in HYPE:
        if m := re.search(rx, text, re.I):
            errs.append(f"hype wording: {m.group(0)!r}")
    if len(text) > 2200:
        errs.append(f"caption is {len(text)} chars (Instagram max 2200)")
    if len(re.findall(r"(?<!\w)@\w+", text)) > 20:
        errs.append("more than 20 @mentions")
    if re.search(ALLEGATION_WORDS, text, re.I) and not re.search(r"\balleg\w*", text, re.I):
        warns.append("mentions a charge/crime without 'alleged': check unproven claims are marked")
    return errs, warns


# ---------------------------------------------------------------------------
# The 7-check score and the publish gate
# ---------------------------------------------------------------------------

SCORE_KEYS = ("hook", "read", "send", "keep", "reply", "original", "alone")
SCORE_MAX = 2 * len(SCORE_KEYS)   # 14
GATE = 12


def score_total(score: dict | None) -> int:
    try:
        return sum(int(score[k]) for k in SCORE_KEYS)
    except (TypeError, KeyError, ValueError):
        return 0


def score_problems(score: dict | None) -> list[str]:
    """Structural problems with a score object (missing checks, bad values, wrong total, no notes)."""
    if not isinstance(score, dict):
        return ["missing score object"]
    errs = []
    for k in SCORE_KEYS:
        if score.get(k) not in (0, 1, 2):
            errs.append(f"score.{k} must be 0, 1 or 2 (got {score.get(k)!r})")
    if not errs and score.get("total") != score_total(score):
        errs.append(f"score.total is {score.get('total')!r} but the checks add up to {score_total(score)}")
    if not str(score.get("notes", "")).strip():
        errs.append("score.notes is required (one line per weak check)")
    return errs


def passes_gate(score: dict | None) -> bool:
    return not score_problems(score) and score_total(score) >= GATE


def gate_message(score: dict | None) -> str:
    problems = score_problems(score)
    if problems:
        return "invalid score: " + "; ".join(problems)
    return f"score {score_total(score)}/{SCORE_MAX} (gate {GATE})"


def post_problems(caption: str, score: dict | None) -> tuple[list[str], list[str]]:
    """Caption checks plus the cross-checks between the caption and the score."""
    errs, warns = caption_problems(caption)
    if isinstance(score, dict) and score.get("send") == 2 and not re.search(r"\bsend this to\b", caption or "", re.I):
        errs.append("score.send is 2 but the caption has no 'Send this to …' line naming who")
    return errs, warns

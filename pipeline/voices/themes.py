"""Keyword themes (English, Tamil, Tamil in Latin script). A post can carry several. No stance is inferred."""
from __future__ import annotations

import re

THEMES: dict[str, tuple[str, list[str]]] = {
    'power': ('Power cuts and electricity bills', [
        'power cut', 'powercut', 'current cut', 'load shedding', 'eb bill', 'tneb', 'tangedco', 'tnpdcl', 'electricity',
        'free units', 'மின்வெட்டு', 'மின்சார', 'மின் கட்டண', 'கரண்ட்', 'minsaram', 'current illa']),
    'prices': ('Prices and cost of living', [
        'price rise', 'price hike', 'inflation', 'cost of living', 'aavin', 'milk price', 'vilaivasi', 'vilai',
        'விலைவாசி', 'விலை உயர்', 'விலையேற்ற', 'ஆவின்', 'பால் விலை']),
    'water': ('Rain, flooding and drinking water', [
        'waterlog', 'water log', 'flood', 'storm water', 'stormwater', 'rain water', 'drainage', 'drinking water',
        'மழைநீர்', 'வெள்ள', 'தண்ணீர்', 'வடிகால்', 'குடிநீர்', 'mazhai']),
    'law_order': ('Law and order, safety', [
        'law and order', 'law & order', 'murder', 'rowdy', 'rowdies', 'crime', 'women safety', "women's safety", 'harass',
        'custodial', 'lock-up', 'lockup', 'சட்டம் ஒழுங்கு', 'சட்டம்-ஒழுங்கு', 'கொலை', 'ரவுடி', 'பாதுகாப்பு', 'பாலியல்']),
    'drugs': ('Drugs', ['ganja', 'drug', 'narcotic', 'கஞ்சா', 'போதை']),
    'women_aid': ('Rs 2,500 for women and other cash promises', [
        '2500', '2,500', 'urimai thogai', 'urimai thokai', 'magalir', 'lpg cylinder', 'free cylinder',
        'உரிமைத் தொகை', 'உரிமை தொகை', 'மகளிர் உரிமை', 'சிலிண்டர்']),
    'promises': ('Promises kept or broken', [
        'promise', 'manifesto', 'vaakuruthi', 'vakkuruthi', 'loan waiver', 'வாக்குறுதி', 'தேர்தல் அறிக்கை', 'கடன் தள்ளுபடி']),
    'liquor': ('TASMAC and liquor', ['tasmac', 'liquor', 'wine shop', 'டாஸ்மாக்', 'மதுக்கடை', 'மதுபான', 'மது விலை']),
    'jobs': ('Jobs', ['unemploy', 'job', 'velai', 'tnpsc', 'internship', 'வேலைவாய்ப்பு', 'வேலை இல்ல', 'வேலையில்ல']),
    'corruption': ('Corruption and bribes', [
        'corrupt', 'bribe', 'lanjam', 'commission', 'scam', 'ஊழல்', 'லஞ்ச', 'கமிஷன்']),
    'roads_transport': ('Roads, buses, metro', [
        'pothole', 'road', 'bus fare', 'omni bus', 'mtc', 'metro', 'traffic', 'flyover', 'சாலை', 'பேருந்து', 'மெட்ரோ']),
    'health': ('Hospitals and medicine', [
        'hospital', 'doctor', 'medicine shortage', ' gh ', 'phc', 'மருத்துவமனை', 'மருத்துவ', 'மருந்து']),
    'education': ('Schools, colleges, NEET', [
        'school', 'college', 'neet', 'teacher', 'fee structure', 'breakfast scheme', 'பள்ளி', 'கல்வி', 'நீட்', 'ஆசிரியர்']),
    'farmers': ('Farmers', ['farmer', 'paddy', 'sugarcane', 'procurement', 'delta', 'விவசாயி', 'நெல்', 'கரும்பு']),
    'investment': ('Investment and industry', [
        'investment', 'mou', 'factory', 'investor', 'data centre', 'data center', 'parandur', 'முதலீடு', 'தொழிற்சாலை']),
    'debt': ('State debt and finances', ['debt', 'white paper', 'treasury', 'borrow', 'கடன் சுமை', 'வெள்ளை அறிக்கை', 'கஜானா']),
    'arrests': ('Arrests of opponents, vendetta', [
        'arrest', 'vendetta', 'revenge politics', 'dvac', 'raid', 'கைது', 'பழிவாங்க', 'ரெய்டு']),
    'access': ('Access to the CM and ministers', [
        'press meet', 'press conference', 'not meeting', 'work from home', 'panaiyur', 'secretariat',
        'பத்திரிகையாளர் சந்திப்பு', 'செய்தியாளர் சந்திப்பு', 'தலைமைச் செயலக']),
    'caste_religion': ('Caste and religion', [
        'caste', 'dalit', 'honour killing', 'temple', 'church', 'mosque', 'minorit', 'hindu', 'christian', 'muslim',
        'சாதி', 'ஜாதி', 'தலித்', 'கோயில்', 'ஆணவக் கொலை', 'சிறுபான்மை']),
    'centre': ('Centre v state, Governor, language', [
        'centre', 'central government', 'union government', 'governor', 'delimitation', 'hindi', 'nep', 'gst share',
        'bjp', 'modi', 'மத்திய அரசு', 'ஒன்றிய அரசு', 'ஆளுநர்', 'இந்தி', 'தொகுதி மறுவரையறை']),
    'experience': ('Inexperience, "give him time"', [
        'inexperience', 'no experience', 'experience', 'give him time', 'give time', 'six months', '6 months',
        'reel', 'actor', 'fan club', 'அனுபவ', 'அவகாச', 'ஆறு மாத', 'நடிகர்']),
}

_TAMIL = re.compile(r'[஀-௿]')
_TANGLISH = re.compile(r'\b(illa|iruk+u|panra|panna|pannu|enna|namma|romba|thaan|dhan|seri|sollu|vaazhga|thalaiva|'
                       r'aatchi|makkal|arasu|thambi|anna|nalla|kedaiyadhu|venum|vendam|epdi|yen|ipo|inga)\b', re.I)


def language(text: str) -> str:
    letters = sum(ch.isalpha() for ch in text) or 1
    if len(_TAMIL.findall(text)) / letters > 0.3:
        return 'ta'
    return 'ta-latn' if len(_TANGLISH.findall(text)) >= 2 else 'en'


def tag(text: str, extra: dict | None = None) -> list[str]:
    low = f' {text.lower()} '
    found = [key for key, (_, words) in THEMES.items() if any(w in low for w in words)]
    for key, words in (extra or {}).items():
        if key not in found and any(w.lower() in low for w in words):
            found.append(key)
    return found


def label(key: str, extra_labels: dict | None = None) -> str:
    if key in THEMES:
        return THEMES[key][0]
    return (extra_labels or {}).get(key, key.replace('_', ' ').title())

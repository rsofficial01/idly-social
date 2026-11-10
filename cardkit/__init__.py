"""cardkit: renders idly's 1080x1350 Instagram news cards.

    from cardkit import render_cards
    render_cards(cards, '/path/out')                   # classic: photo band + stat + headline + bullets
    render_cards(posts, '/path/out', template='hype')  # hype: full-bleed photo cover + detail slides
    # see cardkit/render.py for the card and post dict formats
"""
from .render import (render_cards, render_cards_async, card_html, credit_line_text,  # noqa: F401
                     hype_cover_html, hype_detail_html)

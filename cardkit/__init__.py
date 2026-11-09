"""cardkit: renders idly's 1080x1350 Instagram news cards (photo band + stat + headline + bullets).

    from cardkit import render_cards
    render_cards(cards, '/path/out')   # see cardkit/render.py for the card dict format
"""
from .render import render_cards, render_cards_async, card_html  # noqa: F401

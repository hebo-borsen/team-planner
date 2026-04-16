import json
import os

from flask import session, request

# ---------------------------------------------------------------------------
# Load translations
# ---------------------------------------------------------------------------

SUPPORTED_LANGUAGES = ('en', 'da')
DEFAULT_LANGUAGE = 'da'

_translations = {}
_translations_dir = os.path.join(os.path.dirname(__file__), 'translations')

for lang_code in SUPPORTED_LANGUAGES:
    path = os.path.join(_translations_dir, f'{lang_code}.json')
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            _translations[lang_code] = json.load(f)


# ---------------------------------------------------------------------------
# Translation function
# ---------------------------------------------------------------------------

def get_locale():
    """Return the current language code from session or cookie."""
    return session.get('lang') or request.cookies.get('lang') or DEFAULT_LANGUAGE


def _(text):
    """Translate *text* into the active language.

    Returns the original English text if no translation is found.
    """
    lang = get_locale()
    if lang == 'en':
        return text
    return _translations.get(lang, {}).get(text, text)

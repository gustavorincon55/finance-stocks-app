import requests
import urllib.parse

from flask import redirect, render_template, request, session
from functools import wraps


#finnhub/api token:
TOKEN = ""

def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""

    # Contact API
    try:       
        response_info = requests.get(f"https://finnhub.io/api/v1/search?q={urllib.parse.quote_plus(symbol.upper())}&token={TOKEN}")
        response_info.raise_for_status()
        response_quote = requests.get(f"https://finnhub.io/api/v1/quote?symbol={urllib.parse.quote_plus(symbol.upper())}&token={TOKEN}")
        response_quote.raise_for_status()

        
    except requests.RequestException:
        return None


    # Parse response
    try:
        quote = response_quote.json()
        info = response_info.json()
        info = info['result']

        for result in info:
            if result['symbol'] == symbol.upper():
                info = result
                break


        return {
            "name": info["description"],
            "price": float(quote["c"]),
            "symbol": info["symbol"]
        }
    except (KeyError, TypeError, ValueError):
        return None

def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"

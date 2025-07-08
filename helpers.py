import os
import requests
from flask import redirect, render_template, request, session
from functools import wraps
from fmp_python.fmp import FMP

api_keys = {
    "ALPHA_VANTAGE_API_KEY": os.environ.get("ALPHA_VANTAGE_API_KEY", ""),
    "FMP_API_KEY": os.environ.get("FMP_API_KEY", ""),
}

fmp = FMP(api_key=api_keys["FMP_API_KEY"])


def apology(message, code=400):
    def escape(s):
        for old, new in [
            ("-", "--"),
            (" ", "-"),
            ("_", "__"),
            ("?", "~q"),
            ("%", "~p"),
            ("#", "~h"),
            ("/", "~s"),
            ('"', "''"),
        ]:
            s = s.replace(old, new)
        return s

    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function


def bulk_lookup_fmp(symbols: str):
    """Looks up quote for one or more stock symbols from FMP."""
    try:
        # The fmp-python library's get_quote method handles comma-separated strings.
        # It returns a list of quote dictionaries.
        quotes = fmp.get_quote(symbols)

        # Filter out empty results which indicate an invalid symbol
        invalid_quotes = [q for q in quotes if not q]
        if invalid_quotes:
            print(f"Invalid symbols found: {[q.get('symbol') for q in invalid_quotes]}")
            if len(invalid_quotes) == len(quotes):
                print("All provided symbols were invalid.")

        return [
            {
                "name": item.get("name", "N/A"),
                "price": (
                    float(item.get("price")) if item.get("price") is not None else None
                ),
                "symbol": item.get("symbol", ""),
            }
            for item in quotes
        ]
    except Exception as e:
        print(f"An unexpected error occurred during bulk lookup: {e}")
        return []


def lookup_fmp(symbol: str):
    """Looks up quote for a single stock symbol from FMP."""
    try:
        # The fmp-python library returns a list of quote dictionaries directly.
        quotes = fmp.get_quote(symbol)
        # An empty list or a list with an empty dict means the symbol was not found.
        if quotes and quotes[0]:
            quote_data = quotes[0]
            return {
                "name": quote_data.get("name"),
                "price": (
                    float(quote_data.get("price"))
                    if quote_data.get("price") is not None
                    else None
                ),
                "symbol": quote_data.get("symbol"),
            }
        else:
            # This path is taken if the symbol is invalid.
            print(f"No data found for symbol: {symbol}")
            return None
    except (KeyError, TypeError, ValueError, IndexError) as e:
        print(f"Error processing FMP quote response for {symbol}: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


def lookup_alpha_vantage(symbol: str):
    try:
        api_key = api_keys["ALPHA_VANTAGE_API_KEY"]
        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={api_key}"
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Quote API request failed: {e}")
        return None

    try:
        data = response.json()
        quote_data = data.get("Global Quote", {})
        if quote_data:
            price = quote_data.get("05. price")
            symbol_returned = quote_data.get("01. symbol")

            company_name = get_company_name(symbol, api_key)

            return {
                "name": company_name,
                "price": float(price) if price else None,
                "symbol": symbol_returned if symbol_returned else symbol,
            }
        else:
            print("No quote data found in Alpha Vantage response")
        return None

    except (KeyError, TypeError, ValueError) as e:
        print(f"Error parsing Alpha Vantage quote response: {e}")
        return None

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


def lookup(symbol):
    symbol = symbol.strip()
    if "," in symbol:
        return None

    if symbol:
        quote = lookup_fmp(symbol)
        if quote is None:
            quote = lookup_alpha_vantage(symbol)
            if quote is None:
                print(f"No data found for symbol: {symbol}")
                return None
        return quote
    else:
        return None


def get_company_name(symbol, api_key):
    try:
        url = f"https://www.alphavantage.co/query?function=SYMBOL_SEARCH&keywords={symbol}&apikey={api_key}"
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Search API request failed: {e}")
        return None

    try:
        data = response.json()
        best_match = None
        if data.get("bestMatches"):
            best_match = data["bestMatches"][0]
        if best_match:
            return best_match.get("2. name")
        else:
            print(f"No company name found for symbol: {symbol}")
            return None

    except (KeyError, TypeError, ValueError) as e:
        print(f"Error parsing Alpha Vantage search response: {e}")
        return None


def usd(value):
    return f"${value:,.2f}"


def render_quotes(quotes):
    return render_template("quotes.html", quotes=quotes)

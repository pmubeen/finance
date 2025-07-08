import os
import redis
import json
from os import environ

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, bulk_lookup_fmp
from datetime import datetime, timedelta

# Configure application
app = Flask(__name__)
app.secret_key = "13080dWOd01"
api_keys = {
    "ALPHA_VANTAGE_API_KEY": environ.get("ALPHA_VANTAGE_API_KEY", ""),
    "FMP_API_KEY": environ.get("FMP_API_KEY", ""),
}

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

app.config["SESSION_PERMANENT"] = True
app.permanent_session_lifetime = timedelta(minutes=5)
app.config["SESSION_TYPE"] = "redis"
app.config["SESSION_REDIS"] = redis.from_url("redis://127.0.0.1:6379")


# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not api_keys["ALPHA_VANTAGE_API_KEY"] and not api_keys["FMP_API_KEY"]:
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    try:
        all_stocks = db.execute(
            "SELECT symbol, SUM(shares) as net_shares, name FROM history WHERE id=:id GROUP BY symbol HAVING SUM(shares) > 0 ORDER BY shares DESC",
            id=session["user_id"],
        )
    except:
        return render_template("index.html", stocks=[])

    # Filter out symbols where net_shares is zero
    all_stocks = [stock for stock in all_stocks if stock["net_shares"] > 0]

    symbols = [stock["symbol"] for stock in all_stocks]
    quotes = bulk_lookup_fmp(",".join(symbols)) if symbols else []
    quotes_dict = {quote["symbol"]: quote for quote in quotes}

    stocks = []
    for stock_data in all_stocks:
        symbol = stock_data["symbol"]
        quote = quotes_dict.get(symbol)
        if quote:
            stocks.append(
                {
                    "symbol": symbol,
                    "name": stock_data["name"],
                    "price": round(quote.get("price"), 2),
                    "shares": stock_data["net_shares"],
                }
            )

    totval = 0
    for stock in stocks:
        stock["value"] = round(stock["shares"] * stock["price"], 2)
        totval += stock["value"]

    cash = db.execute("SELECT cash from users WHERE id=:id", id=session["user_id"])
    net = cash[0].get("cash") + totval - 10000
    return render_template(
        "index.html",
        stocks=stocks,
        cash=cash[0],
        totval=round(totval, 2),
        net=round(net, 2),
        data=json.dumps(stocks),
    )


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")
    else:
        symbol = request.form.get("stocks")
        shares = request.form.get("shares")

        if not symbol:
            return apology("Missing Symbol", 400)
        elif not shares:
            return apology("Missing Shares", 400)

        try:
            shares = int(shares)
        except ValueError:
            return apology("Shares must be an integer", 400)

        if shares <= 0:
            return apology("Shares must be a positive integer", 400)

        quote = lookup(symbol)
        if quote is None:
            return apology("Invalid Symbol", 400)

        price = quote["price"]
        cost = price * shares

        rows = db.execute(
            "SELECT cash FROM users WHERE id = :id", id=session["user_id"]
        )
        cash = rows[0]["cash"]

        if cash < cost:
            return apology("Not Enough Cash", 400)

        db.execute(
            "UPDATE users SET cash = cash - :cost WHERE id = :id",
            cost=cost,
            id=session["user_id"],
        )

        db.execute(
            "INSERT INTO history (id, symbol, shares, price, time) VALUES (:id, UPPER(:symbol), :name, :shares, :price, :time)",
            id=session["user_id"],
            symbol=symbol,
            shares=shares,
            price=price,
            name=quote["name"],
            time=datetime.now(),
        )
        return redirect("/")


@app.route("/history")
@login_required
def history():
    history = db.execute(
        "SELECT symbol,shares,price,time from history WHERE id=:id",
        id=session["user_id"],
    )
    if history != []:
        return render_template("history.html", history=history, error=False)
    else:
        return render_template("history.html", error=True)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = :username",
            username=request.form.get("username"),
        )

        correct = 0
        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            correct = 1
            return render_template("login.html", correct=correct)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "GET":
        return render_template("quote.html")
    else:
        symbols_str = request.form.get("stocks")
        symbols = [
            s.strip() for s in symbols_str.split(",") if s.strip()
        ]  # Clean and split

        if not symbols:
            return render_template("quote.html", stockval=False)

        if len(symbols) == 1:
            stockval = [lookup(symbols[0])]
        else:
            stockval = bulk_lookup_fmp(",".join(symbols))

        if not any(stockval):  # Check if all results are None or empty
            return render_template("quote.html", stockval=False)
        else:
            return render_template("quote.html", isValid=True, stockval=stockval)


@app.route("/reset", methods=["GET", "POST"])
def forgot():
    if request.method == "GET":
        return render_template("reset.html")
    else:
        security = str(request.form.get("security"))
        new_pass = str(generate_password_hash(request.form.get("password")))
        sec_passed = db.execute(
            "SELECT * from users WHERE security=:security", security=security
        )
        if sec_passed == []:
            e = f"Incorrect response to security. Please try again"
            return render_template("reset.html", error=True, e=e)
        else:
            db.execute(
                "UPDATE users SET hash=:new_pass WHERE security=:security",
                new_pass=new_pass,
                security=security,
            )
            return redirect("/")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    else:
        username = str(request.form.get("username"))
        p_hash = str(generate_password_hash(request.form.get("password")))
        security = str(request.form.get("security"))
        user_exists = db.execute(
            "SELECT * FROM users WHERE username = :username", username=username
        )
        if user_exists:
            return render_template("register.html", user_exists=user_exists)
        else:
            db.execute(
                "INSERT INTO users (username, hash, security) VALUES(:username, :hash, :security)",
                username=username,
                hash=p_hash,
                security=security,
            )
            return render_template("login.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        stocks = db.execute(
            "SELECT symbol FROM history WHERE id = :id GROUP BY symbol HAVING SUM(shares) > 0",
            id=session["user_id"],
        )
        return render_template("sell.html", stocks=stocks)
    else:
        symbol = request.form.get("stocks")
        shares = request.form.get("shares")

        if not symbol:
            return apology("Missing Symbol", 400)
        elif not shares:
            return apology("Missing Shares", 400)

        try:
            shares = int(shares)
        except ValueError:
            return apology("Shares must be an integer", 400)

        if shares <= 0:
            return apology("Shares must be a positive integer", 400)

        # Check if user owns enough shares
        rows = db.execute(
            "SELECT SUM(shares) as total_shares FROM history WHERE id = :id AND symbol = UPPER(:symbol)",
            id=session["user_id"],
            symbol=symbol,
        )

        total_shares = rows[0]["total_shares"]

        if total_shares < shares:
            return apology("Too many shares", 400)

        quote = lookup(symbol)
        if quote is None:
            return apology("Invalid Symbol", 400)

        price = quote["price"]
        proceeds = price * shares

        db.execute(
            "UPDATE users SET cash = cash + :proceeds WHERE id = :id",
            proceeds=proceeds,
            id=session["user_id"],
        )

        db.execute(
            "INSERT INTO history (id, symbol, shares, price, time) VALUES (:id, UPPER(:symbol), :name, :shares, :price, :time)",
            id=session["user_id"],
            symbol=symbol,
            shares=-shares,
            name=quote["name"],
            price=price,
            time=datetime.now(),
        )

        return redirect("/")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

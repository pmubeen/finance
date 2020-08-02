import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd
from datetime import datetime

# Configure application
app = Flask(__name__)

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

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = True
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
os.environ["API_KEY"] = "pk_1fa2f8c3dfaa44cdb247ab846c09ee6f"
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    try:
        all_stocks = db.execute("SELECT symbol,shares FROM history WHERE id=:id ORDER BY shares DESC",id=session["user_id"])
    except:
        return render_template("index.html",stocks=[])
    stocks = []
    for i in range((len(all_stocks))):
        if stocks == []:
            stocks.append({"symbol":(all_stocks[i])['symbol'], "price":lookup(((all_stocks[i])['symbol'])).get('price'), "shares":((all_stocks[i])['shares'])})
        else:
            nostock = True
            for stock in stocks:
                if stock.get('symbol') == all_stocks[i].get('symbol'):
                    stock['shares'] = round(float(stock['shares']),2) + round(float(all_stocks[i].get('shares')),2)
                    nostock = False
            if nostock:
                    stocks.append({"symbol":(all_stocks[i])['symbol'], "price":lookup(((all_stocks[i])['symbol'])).get('price'), "shares":(all_stocks[i])['shares']})
    cash = db.execute("SELECT cash from users WHERE id=:id",id=session["user_id"])       
    return render_template("index.html",stocks=stocks,cash=cash[0])


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == 'GET':
        return render_template('buy.html')
    else:
        symbol = str(request.form.get('stocks'))
        stockval = lookup(symbol)
        num_shares = int(request.form.get('shares'))
        if stockval == None:
            e = f"Invalid stock name. Please try again"
            return render_template('buy.html', e=e, error=True)

        cash = round(float((db.execute("SELECT cash FROM users WHERE id = :id",id=session["user_id"])[0])['cash']),2)
        expense = round(float(stockval['price'])*float(num_shares), 2)
        if cash < expense:
            e = f"Not enough cash. Cash: {cash}, Cost: {expense}"
            return render_template('buy.html', e=e, error=True)
        else:
            try:
                db.execute("SELECT * FROM history")
            except:
                db.execute("CREATE TABLE history ( id INTEGER, symbol TEXT, shares INTEGER, price INTEGER, time TEXT )")
                db.execute("INSERT INTO history (id,symbol,shares,price,time) VALUES (:id,:symbol,:shares,:price,:time)",id=session["user_id"],symbol=stockval['symbol'],shares=num_shares,price=expense,time=((datetime.now()).strftime("%d/%m/%Y %H:%M:%S")))
                db.execute("UPDATE users SET cash = :cash WHERE id = :id",cash=(cash-expense),id=session["user_id"])
            else:
                db.execute("INSERT INTO history (id,symbol,shares,price,time) VALUES (:id,:symbol,:shares,:price,:time)",id=session["user_id"],symbol=stockval['symbol'],shares=num_shares,price=expense,time=(datetime.now()).strftime("%d/%m/%Y %H:%M:%S"))
                db.execute("UPDATE users SET cash = :cash WHERE id = :id",cash=round((cash-expense),2),id=session["user_id"])
        return render_template('buy.html')


@app.route("/history")
@login_required
def history():
        history = db.execute("SELECT symbol,shares,price,time from history WHERE id=:id",id=session["user_id"])
        if history != []:    
            return render_template("history.html",history=history,error=False)
        else:
            return render_template("history.html",error=True)


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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))
        
        correct=0
        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            correct=1
            return render_template("login.html",correct=correct)

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
    isValid = False
    if request.method == "GET":
        return render_template("quote.html")
    else:
        symbol = str(request.form.get("stocks")).split(",")
        stockval = []
        for i in range(0,(len(symbol))):
            if symbol[i] != '':
                stockval.append(lookup(symbol[i]))
        if stockval == []:
            return render_template("quote.html", stockval=False)
        else:
            return render_template("quote.html", isValid=isValid, stockval=stockval)
        


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    else:
        username = str(request.form.get("username"))
        p_hash = str(generate_password_hash(request.form.get("password")))
        user_exists = db.execute("SELECT * FROM users WHERE username = :username",username=username)
        if user_exists:
            return render_template("register.html",user_exists=user_exists)
        else:
            db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)",username=username,hash=p_hash)
            return render_template("login.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "GET":
        return render_template('sell.html')
    else:
        stock = request.form.get("stocks")
        stockval = lookup(stock)
        error = False
        
        if stockval == None:
            e = f"Invalid stockname. Please try again"
            return render_template('sell.html',error=True,e=e)
        num_shares = int(request.form.get("shares"))
        has_stock = db.execute("SELECT * from history WHERE id=:id AND symbol=:symbol",id=session["user_id"],symbol=stock)
        totalstock = 0
        
        for entry in has_stock:
            totalstock += int(entry['shares'])
        
        if totalstock == 0:
            e = f"You dont own any shares of that stock. Please try again."            
            return render_template('sell.html',error=True,e=e)
        elif num_shares == 0:
            e = f"Please enter no of shares greater than 0."            
            return render_template('sell.html',error=True,e=e)
        elif num_shares in range(1,totalstock+1):
            sellval = round(float(stockval['price'])*num_shares, 2)
            cash = round(float((db.execute("SELECT cash FROM users WHERE id = :id",id=session["user_id"])[0])['cash']),2)
            db.execute("INSERT INTO history (id,symbol,shares,price,time) VALUES (:id,:symbol,:shares,:price,:time)", id=session["user_id"], symbol=stock, shares=-num_shares, price=stockval['price'],time=(datetime.now()).strftime("%d/%m/%Y %H:%M:%S"))
            db.execute("UPDATE users SET cash=:cash WHERE id=:id",cash=cash+sellval,id=session["user_id"])
        else:
            e = f"You dont own enough shares to sell. Shares inputted: {num_shares}, Shares currently owned {totalstock}."
            return render_template('sell.html',error=True,e=e)
        return render_template('sell.html')


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

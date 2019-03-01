import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

import datetime

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
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# test to see if the session can be prolongue
app.config["PERMANENT_SESSION_LIFETIME"] = 600;
#

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # get from the database the amount of money
    result = db.execute('SELECT "company_name","symbol", SUM("shares") "shares" FROM "trans" WHERE userId == :userId GROUP BY "company_name"', userId = session["user_id"])

    # global variables for user's cash, user's money from current stocks value, and grand total (aka cash + tota_stocks_value)
    total_stocks_value = 0
    cash = 0
    grand_total = 0

    # get the current price per stock, and get the sum_total (aka: price of stocks * number of stocks)
    # also, check for the companies that have cero shares. Later on delete those companies.
    index = 0
    cero_shares = []
    for stock in result:

        stock["current_price"] = lookup(stock["symbol"])
        stock["current_price"] = stock["current_price"]["price"]

        stock["sum_total"] = stock["shares"] * stock["current_price"]

        # add to global variable
        total_stocks_value += stock["sum_total"]

        #format in dollars
        stock["current_price"] = usd(stock["current_price"])
        stock["sum_total"] = usd(stock["sum_total"])

        if stock["shares"] == 0:
            cero_shares.append(index)
        index += 1

    # sort the list to avoid index-out-of-range errors
    cero_shares.sort(reverse = True)
    for index in cero_shares:
        del result[index]


    # get the user's cash
    cash = db.execute('SELECT "cash" FROM "users" WHERE "id" == :id',id=session["user_id"])
    cash = cash[0]["cash"]

    grand_total = cash + total_stocks_value

    return render_template("index.html",stocks = result, cash = usd(cash), total_stocks_value = usd(total_stocks_value), grand_total = usd(grand_total))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():

    if request.method == "POST":

        # look for the company's stock symbol
        api = lookup(request.form.get("symbol"))

        # check if the symbol is correct
        if api == None:
            return apology("That symbol doesn't exist.")

        name = api["name"]
        price = api["price"]
        symbol = api["symbol"]
        date_time = datetime.datetime.now()

        # get the number of shares to buy
        shares = request.form.get("shares")

        # check if shares is a number
        try:
            shares = int(shares)
        except:
            shares = 0

        if shares <= 0:
            return apology("You need to buy some shares...")

        cash = db.execute('SELECT "cash" FROM "users" WHERE "id" == :id',id=session["user_id"])
        cash = cash[0]["cash"]

        x = price * shares

        # check if user has enough cash to buy shares
        if cash < x:
            return apology("You don't have enough money")
        print(cash,x,(price * shares))
        # substract the amount of the purshase from the user's cash
        db.execute("UPDATE \"users\" SET \"cash\" = :newCash WHERE \"id\"==:id",id=session["user_id"], newCash = (cash - x))

        # add transaction to the transaction database
        result = db.execute("INSERT INTO trans(company_name, userId, symbol, price, shares, total, datetime, _type) VALUES(:company_name,:userId, :symbol, :price, :shares, :total, :datetime, :_type)", company_name = name,
        userId=session["user_id"], symbol = symbol, price = price, shares = shares, total = price * shares, datetime = date_time, _type =  "buy")

        flash("You bough the shares!")
        return render_template("bought.html",name=name,price=usd(price),symbol=symbol,shares=shares, total_spent = usd(shares * price))
    else:
        return render_template("buy.html")


@app.route("/check", methods=["POST"])
def check():
    """Return true if username available, else false, in JSON format"""
    print("working")
    username = request.args

    print(username)
    #result = db.execute("SELEC * FROM users WHERE username == :username", username = username)

   #if len(result) > 0:
        return jsonify(True)

    return jsonify(False)


@app.route("/history")
@login_required
def history():
    """
    For each row, make clear whether a stock was bought or sold and include the stock’s symbol,
    the (purchase or sale) price, the number of shares bought or sold, and the date and time at which the transaction occurred.
    """

    trans = db.execute('SELECT * FROM "trans" WHERE userId == :userId ORDER BY datetime', userId = session["user_id"])

    for tran in trans:

        if tran["_type"] == "sell":
            tran["shares"] = tran["shares"] * -1
            tran["total"] = tran["total"] * -1
            print("_type: sell")

        tran["price"] = usd(tran["price"])
        tran["total"] = usd(tran["total"])

    return render_template("history.html", trans = trans)


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

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

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
    """Get stock quote."""
    print(session["user_id"])

    if request.method == "POST":

        api = lookup(request.form.get("symbol"))
        if api == None:
            return apology("That symbol doesn't exist.")
        name=api["name"]
        price=api["price"]
        symbol=api["symbol"]

        return render_template("quoted.html",name=name,price=usd(price),symbol=symbol)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if username == "":
            return apology("You must provide an username")
        if password == "":
            return apology("You must provide a password")
        elif confirmation != password:
            return apology("Both passwords must be equal.")

        checker = db.execute('SELECT * FROM users where username == :username', username = username)

        if len(checker) > 0:
            return apology("Sorry, username is not available.")

        result = db.execute("INSERT INTO users(username, hash, cash) VALUES(:name, :hashedP, :cash)",
        name=username,hashedP=generate_password_hash(password),cash=20000)

        return redirect("/")

    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":
        symbol_to_sell = request.form.get("symbol")
        # check if the user wrote a valid number of shares
        try:
            shares_to_sell = int(request.form.get("shares"))

        except:
            flash("Sorry, you need to write how many stocks you want to buy.")
            return redirect("/sell")


        stocks = db.execute('SELECT "company_name","symbol", SUM("shares") "shares" FROM "trans" WHERE userId == :userId  AND symbol == :symbol_to_sell  GROUP BY "company_name"',
        userId = session["user_id"], symbol_to_sell = symbol_to_sell)

        # if nothing was returned from the query it means the user doesn't have stocks on that company.
        try:
            shares_owned = stocks[0]["shares"]
        except:
            flash("Sorry, you don't have shares on that company.")
            return redirect("/sell")

        # check if the user can sell that many stocks
        if shares_owned < shares_to_sell:
            flash("Sorry, you don't have that many shares.")
            return redirect("/sell")

        stock = lookup(symbol_to_sell)


        # update trans with a sell transaction
        trans = db.execute("INSERT INTO trans(company_name, userId, symbol, price, shares, total, datetime, _type) VALUES(:company_name,:userId, :symbol, :price, :shares, :total, :datetime, :_type)", company_name = stock["name"],
        userId=session["user_id"], symbol = symbol_to_sell, price = stock["price"], shares = -shares_to_sell, total = stock["price"] * -shares_to_sell, datetime = datetime.datetime.now(), _type = "sell")

        print(trans)

        users = db.execute('select "cash" FROM "users" WHERE "id"==:id',id=session["user_id"])

        cash = users[0]["cash"]

        print(cash)

        cash = cash + (stock["price"] * shares_to_sell)

        users = db.execute('UPDATE "users" SET "cash" = :cash WHERE "id"==:id',id=session["user_id"], cash = cash)

        flash("You succesfully made the sell")
        return redirect("/")



    stocks = db.execute('SELECT "company_name","symbol", SUM("shares") "shares" FROM "trans" WHERE userId == :userId GROUP BY "company_name"', userId = session["user_id"])

    # make a list of the stocks that have cero shares
    index = 0
    cero_shares = []
    for stock in stocks:
        if stock["shares"] == 0:
            cero_shares.append(index)
        index += 1

    # erase the stocks that have cero shares (first sort the list to avoid index-out-of-range errors)
    cero_shares.sort(reverse= True)
    for index in cero_shares:
        del stocks[index]

    return render_template("sell.html", stocks = stocks)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

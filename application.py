import os

from flask import Flask, flash, redirect, render_template, request, session, url_for 
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, login_required, lookup, usd

#if the app works, erase this.
#from helpers import apology, login_required, lookup, usd

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.mysql import BIGINT

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
app.config["PERMANENT_SESSION_LIFETIME"] = 600


#database set up
SQLALCHEMY_DATABASE_URI = "mysql+mysqlconnector://{username}:{password}@{hostname}/{databasename}".format(
    username="gustavorincon37",
    password="Gstvo_37",
    hostname="gustavorincon37.mysql.pythonanywhere-services.com",
    databasename="gustavorincon37$finance",
)

#app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///finance.db"
app.config["SQLALCHEMY_POOL_RECYCLE"] = 299
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config['SQLALCHEMY_ECHO'] = True

db = SQLAlchemy(app)

@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    #get from the database the amount of money
    _result = db.engine.execute(
        'SELECT company_name,symbol, SUM(shares) shares FROM trans WHERE userId = ? GROUP BY company_name', (str(session["user_id"])))

    result = _result.fetchall()



    # global variables for user's cash, user's money from current stocks value, and grand total (aka cash + tota_stocks_value)
    total_stocks_value = 0
    cash = 0
    grand_total = 0
    stocks = []

    # get the current price per stock, and get the sum_total (aka: price of stocks * number of stocks)
    # also, check for the companies that have cero shares. Later on delete those companies.
    index = 0
    zero_share = []

    for stock in result:

        stock = dict(stock.items())

        stock["current_price"] = lookup(stock["symbol"])
        stock["current_price"] = stock["current_price"]["price"]

        stock["sum_total"] = float(stock["shares"]) * stock["current_price"]

        # add to global variable
        total_stocks_value += stock["sum_total"]

        #format in dollars
        stock["current_price"] = usd(stock["current_price"])
        stock["sum_total"] = usd(stock["sum_total"])

        if stock["shares"] == 0:
            zero_share.append(index)
        index += 1

        stocks.append(stock)

    # sort the list to avoid index-out-of-range errors
    zero_share.sort(reverse=True)
    for index in zero_share:
        del stocks[index]

    # get the user's cash
    cash = db.engine.execute('SELECT cash FROM users WHERE id = ?',(str(session["user_id"])))
    cash = cash.first()
    cash = cash["cash"]

    grand_total = float(cash) + total_stocks_value
    return render_template("index.html", stocks=stocks, cash=usd(cash), total_stocks_value=usd(total_stocks_value), grand_total=usd(grand_total))



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():

    if request.method == "POST":

        # look for the company's stock symbol
        api = lookup(request.form.get("symbol"))

        # check if the symbol is correct
        if api == None:
            flash("That symbol doesn't exist.")
            return redirect(url_for("buy"))

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
            flash("You need to buy some shares...")
            return redirect(url_for("buy"))

        cash = db.engine.execute('SELECT cash FROM users WHERE id = ?',str(session["user_id"]))

        cash= cash.first()
        cash = cash["cash"]

        x = price * shares

        # check if user has enough cash to buy shares
        if cash < x:
            flash("You don't have enough money")
            return redirect(url_for("buy"))
            
        # substract the amount of the purshase from the user's cash
        db.engine.execute('UPDATE users SET cash = ? WHERE id= ?',str(float(cash) - float(x)), str(session["user_id"]))

        # add transaction to the transaction database
        result = db.engine.execute("INSERT INTO trans(company_name, userId, symbol, price, shares, total, datetime, _type) VALUES(?,?, ?, ?, ?, ?, ?, ?)", name,
        str(session["user_id"]), symbol, str(price), str(shares), str(price * shares), str(date_time), "buy")

        flash("Bought!")
        
        return redirect("/")
        
        #return render_template("bought.html",name=name,price=usd(price),symbol=symbol,shares=shares, total_spent = usd(shares * price))
    else:
        return render_template("buy.html")


@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""
    username = request.args.get("username", None)
    result = db.engine.execute("SELECT * FROM users WHERE username = ?", username)

    # return false if the user exist. True otherwise.
    if len(result) > 0:
        return "false"

    return "true"


@app.route("/history")
@login_required
def history():
    """
    For each row, make clear whether a stock was bought or sold and include the stock’s symbol,
    the (purchase or sale) price, the number of shares bought or sold, and the date and time at which the transaction occurred.
    """

    query_trans = db.engine.execute('SELECT * FROM trans WHERE userId = ? ORDER BY datetime', str(session["user_id"]))
    
    _trans = query_trans.fetchall()

    transactions = []

    for _tran in _trans:

        tran = dict(_tran.items())
        if tran["_type"] == "sell":
            tran["shares"] = tran["shares"] * -1
            tran["total"] = float(tran["total"]) * -1

        tran["price"] = usd(tran["price"])
        tran["total"] = usd(tran["total"])

        transactions.append(tran)

    return render_template("history.html", trans = transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            flash("Must provide username")
            return render_template("login.html")

        # Ensure password was submitted
        elif not request.form.get("password"):
            flash("Must provide password")
            return render_template("login.html")



        


        # Query database for username
        rows = db.engine.execute("SELECT * FROM users WHERE username= ?", (request.form.get("username")))
        

        rows = rows.first()
        # Ensure username exists and password is correct

        try:
            if not check_password_hash(rows["hash"], request.form.get("password")):

                flash('Invalid username and/or password')
                return render_template("login.html")
        except:

            flash('Invalid username and/or password')
            return render_template("login.html")


        # Remember which user has logged in
        session["user_id"] = rows["id"]

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
    if request.method == "POST":

        api = lookup(request.form.get("symbol"))
        if api == None:
            flash("That symbol doesn't exist.")
            return render_template("quote.html")        
        
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
            flash("You must provide an username")
            return redirect(url_for("register"))

        if password == "":
            flash("You must provide a password")
            return redirect(url_for("register"))

        elif confirmation != password:
            flash("Both passwords must be equal.")
            return redirect(url_for("register"))


        checker = users.query.filter_by(username=username).first()

        if checker != None:
            flash("Sorry, username is not available.")
            return redirect(url_for("register"))

        new_user = users(username=username, hash=generate_password_hash(password), cash=20000)
        db.session.add(new_user)
        db.session.commit()


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


        _stock = db.engine.execute('SELECT company_name,symbol, SUM(shares) shares FROM trans WHERE userId = ?  AND symbol = ?  GROUP BY company_name',
        session["user_id"], symbol_to_sell)
        stock_user = _stock.first()

        # if nothing was returned from the query it means the user doesn't have stocks on that company.
        try:
            shares_owned = stock_user["shares"]
        except:
            flash("Sorry, you don't have that many shares.")
            return redirect(url_for("sell"))

        # check if the user can sell that many stocks
        if shares_owned < shares_to_sell:
            flash("Sorry, you don't have that many shares.")
            return redirect(url_for("sell"))

        stock = lookup(symbol_to_sell)


        # update trans with a sell transaction
        trans = db.engine.execute("INSERT INTO trans(company_name, userId, symbol, price, shares, total, datetime, _type) VALUES(?, ?, ?, ?, ?, ?, ?, ?)", stock["name"],
        str(session["user_id"]), symbol_to_sell, str(stock["price"]), str(-shares_to_sell), str(stock["price"] * -shares_to_sell), str(datetime.datetime.now()), "sell")

        _user = db.engine.execute('select cash FROM users WHERE id = ?',str(session["user_id"]))
        user = _user.first()
        cash = user["cash"]

        cash = float(cash) + (stock["price"] * shares_to_sell)

        users = db.engine.execute('UPDATE users SET cash = ? WHERE id = ?', str(cash), session["user_id"])

        flash("You succesfully made the sell")
        return redirect("/")


    _stocks = db.engine.execute('SELECT company_name,symbol, SUM(shares) shares FROM trans WHERE userId = ? GROUP BY company_name', str(session["user_id"]))

    stocks = _stocks.fetchall()


    # make a list of the stocks that have cero shares
    index = 0
    zero_share = []
    for stock in stocks:
        if stock["shares"] == 0:
            zero_share.append(index)
        index += 1

    # erase the stocks that have zero shares (first sort the list to avoid index-out-of-range errors)
    zero_share.sort(reverse= True)
    for index in zero_share:
        del stocks[index]

    return render_template("sell.html", stocks = stocks)

@app.route("/sell/<symbol>", methods=["GET", "POST"])
@login_required
def sell_direct(symbol):

    x = lookup(symbol)

    stocks = [1]
    stocks.append({"symbol": x["symbol"], "company_name": x["name"]})

    return render_template("sell.html", stocks = stocks)


@app.route("/buy/<symbol>", methods=["GET", "POST"])
@login_required
def buy_direct(symbol):

    return render_template("buy.html", symbol = symbol)


@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():

    if request.method == "POST":

        # check if current password is correct

        current_password = request.form.get("current-password")
        new_password = request.form.get("password")

        old_hash = db.engine.execute('SELECT * FROM users WHERE id = ?', str(session["user_id"]))
        old_hash = old_hash.first()
        old_hash = old_hash['hash']

        if check_password_hash(old_hash, current_password):

            # update password in the database
            result = db.engine.execute("UPDATE users SET hash = ? WHERE id = ?", generate_password_hash(new_password), str(session['user_id']))

            flash("Your password has been changed correctly.")
            return redirect(url_for("index"))
        else:
            return redirect(url_for("change_password"))



        flash("Your password has been changed correctly.")
        return redirect("/")

    return render_template("change_password.html")



def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

class trans(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    userId = db.Column("userId", db.String(255))
    symbol = db.Column("symbol", db.String(120))
    price = db.Column("price", db.Numeric(precision=10,scale=2))
    shares = db.Column("shares", db.Integer())
    total = db.Column("total", db.Numeric(precision=10,scale=2))
    company_name = db.Column("company_name", db.String(510))
    datetime = db.Column("datetime", db.Date())
    _type = db.Column("_type", db.String(10))

class users(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    username = db.Column("username", db.String(510))
    hash = db.Column("hash", db.Text())
    cash = db.Column("cash", db.Numeric(precision=10, scale=2))

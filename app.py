from flask import Flask, render_template, redirect, url_for, request, flash, abort, session
from flask_session import Session
from key import secret_key,salt1,salt2
from stoken import token
from cmail import sendmail
from itsdangerous import URLSafeTimedSerializer
from apscheduler.schedulers.background import BackgroundScheduler
import requests
import mysql.connector
import os

app = Flask(__name__)
app.secret_key=secret_key
app.config['SESSION_TYPE']='filesystem'
Session(app)

# Database Configuration
'''
DB_HOST = 'localhost'
DB_USER = 'root'
DB_PASSWORD = 'admin'
DB_NAME = 'news_aggregator'
'''


# API Configuration
API_KEY = '1cb52271030c45bcb934b442580ef362'

# Database Connection
'''
mydb = mysql.connector.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME
)
'''
db=os.environ['RDS_DB_NAME']
user=os.environ['RDS_USERNAME']
password=os.environ['RDS_PASSWORD']
host=os.environ['RDS_HOSTNAME']
port=os.environ['RDS_PORT']
with mysql.connector.connect(host=host,user=user,password=password,db=db) as conn:
    cursor=conn.cursor(buffered=True)
    cursor.execute('create table if not exists users(username varchar(15) NOT NULL primary key,password varchar(15),email varchar(80),email_status enum("confirmed","not_confirmed") DEFAULT "not_confirmed")')
    cursor.execute('create table if not exists articles(id int NOT NULL PRIMARY KEY AUTO_INCREMENT,title varchar(255) NOT NULL,description text,source_name varchar(255),url varchar(1000))')
    cursor.execute('create table if not exists newsletter(username varchar(15),headline varchar(255),artcle_url varchar(1000))')
mydb=mysql.connector.connect(host=host,user=user,password=password,db=db)


#cursor = mydb.cursor()

@app.route('/')
def index():
    return render_template('title.html')

@app.route('/login',methods=['GET','POST'])
def login():
    if session.get('user'):
        return redirect(url_for('home'))
    if request.method=='POST':
        username=request.form['username']
        password=request.form['password']
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select count(*) from users where username=%s',[username])
        count=cursor.fetchone()[0]
        if count==1:
            cursor.execute('select count(*) from users where username=%s and password=%s',[username,password])
            p_count=cursor.fetchone()[0]
            if p_count==1:
                session['user']=username
                cursor.execute('select email_status from users where username=%s',[username])
                status=cursor.fetchone()[0]
                cursor.close()
                if status!='confirmed':
                    return redirect(url_for('inactive'))
                else:
                    return redirect(url_for('home'))
            else:
                cursor.close()
                flash('Invalid password')
                return render_template('login.html')
        else:
            cursor.close()
            flash('Invalid username')
            return render_template('login.html')
    return render_template('login.html')

@app.route('/inactive')
def inactive():
    if session.get('user'):
        username=session.get('user')
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select email_status from users where username=%s',[username])
        status=cursor.fetchone()[0]
        cursor.close()
        if status=='confirmed':
            return redirect(url_for('home'))
        else:
            return render_template('inactive.html')
    else:
        return redirect(url_for('login'))

@app.route('/homepage')
def home():
    if session.get('user'):
        username=session.get('user')
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select email_status from users where username=%s',[username])
        status=cursor.fetchone()[0]
        if status=='confirmed':
            # Get top headlines
            top_headlines_url = f'https://newsapi.org/v2/top-headlines?country=us&apiKey={API_KEY}'
            top_headlines_response = requests.get(top_headlines_url)
            top_headlines_data = top_headlines_response.json()
            top_headlines_articles = top_headlines_data['articles']

            # Get category names
            categories = ['entertainment', 'business', 'health', 'science', 'sports', 'technology']
            category_articles = {}

            # Get articles for each category
            for category in categories:
                category_url = f'https://newsapi.org/v2/top-headlines?country=us&category={category}&apiKey={API_KEY}'
                category_response = requests.get(category_url)
                category_data = category_response.json()
                category_articles[category] = category_data['articles']

            # Insert articles into the database
            insert_articles(top_headlines_articles)
            for articles in category_articles.values():
                insert_articles(articles)
                cursor.close()

            return render_template('index.html', top_headlines=top_headlines_articles, categories=categories)
        else:
            return redirect((url_for('inactive')))
    else:
        return redirect(url_for('login'))

@app.route('/category/<category>')
def show_category(category):
    cursor=mydb.cursor(buffered=True)
    # Get articles for the selected category
    category_url = f'https://newsapi.org/v2/top-headlines?country=us&category={category}&apiKey={API_KEY}'
    category_response = requests.get(category_url)
    category_data = category_response.json()
    articles = category_data['articles']

    # Insert articles into the database
    insert_articles(articles)
    cursor.close()

    return render_template('category.html', category=category, articles=articles)

@app.route('/news/<path:article_url>')
def show_news(article_url):
    cursor=mydb.cursor(buffered=True)
    # Retrieve article from the database
    article = get_article(article_url)
    cursor.close()

    return render_template('news.html', article=article)

def insert_articles(articles):
    # Insert articles into the database
    for article in articles:
        title = article['title']
        description = article['description']
        source_name = article['source']['name']
        url = article['url']

        insert_query = "INSERT INTO articles (title, description, source_name, url) VALUES (%s, %s, %s, %s)"
        insert_values = (title, description, source_name, url)

        cursor=mydb.cursor(buffered=True)
        cursor.execute(insert_query, insert_values)
        mydb.commit()
        cursor.close()

def get_article(article_url):
    # Retrieve article from the database
    select_query = "SELECT * FROM articles WHERE url = %s"
    select_values = (article_url,)

    cursor=mydb.cursor(buffered=True)
    cursor.execute(select_query, select_values)
    article = cursor.fetchone()
    cursor.close()

    if article:
        article_data = {
            'title': article[1],
            'description': article[2],
            'source': {
                'name': article[3]
            },
            'url': article[4]
        }
        return article_data

    return None

@app.route('/resendconfirmation')
def resend():
    if session.get('user'):
        username=session.get('user')
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select email_status from users where username=%s',[username])
        status=cursor.fetchone()[0]
        cursor.execute('select email from users where username=%s',[username])
        email=cursor.fetchone()[0]
        cursor.close()
        if status=='confirmed':
            flash('Email already confirmed')
            return redirect(url_for('home'))
        else:
            subject='Email Confirmation'
            confirm_link=url_for('confirm',token=token(email,salt1),_external=True)
            body=f"Please confirm your mail. Follow this link - \n\n{confirm_link}"
            sendmail(to=email,body=body,subject=subject)
            flash('Confirmation link sent check your email')
            return redirect(url_for('inactive'))
    else:
        return redirect(url_for('login'))

@app.route('/registration',methods=['GET','POST'])
def registration():
    if request.method=='POST':
        username=request.form['username']
        password=request.form['password']
        email=request.form['email']
        cursor=mydb.cursor(buffered=True)
        try:
            cursor.execute('insert into users(username,password,email) values(%s,%s,%s)',(username,password,email))
        except mysql.connector.IntegrityError:
            flash('username or email is already in use')
            return render_template('registration.html')
        else:
            mydb.commit()
            cursor.close()
            subject='Email Confirmation'
            confirm_link=url_for('confirm',token=token(email,salt1),_external=True)
            body=f"Thanks for signing up. Follow this link - \n\n{confirm_link}"
            sendmail(to=email,body=body,subject=subject)
            flash('Confirmation link sent check your email')
            return render_template('registration.html')
    return render_template('registration.html')

@app.route('/confirm/<token>')
def confirm(token):
    try:
        serializer=URLSafeTimedSerializer(secret_key)
        email=serializer.loads(token,salt=salt1,max_age=120)
    except Exception as e:
        abort(404,'Link expired')
    else:
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select email_status from users where email=%s',[email])
        status=cursor.fetchone()[0]
        cursor.close()
        if status=='confirmed':
            flash('email already confirmed')
            return redirect(url_for('login'))
        else:
            cursor=mydb.cursor(buffered=True)
            cursor.execute("update users set email_status='confirmed' where email=%s",[email])
            mydb.commit()
            flash('Email confirmation success')
            return redirect(url_for('login'))

@app.route('/forget',methods=['GET','POST'])
def forgot():
    if request.method=='POST':
        email=request.form['email']
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select count(*) from users where email=%s',[email])
        count=cursor.fetchone()[0]
        cursor.close()
        if count==1:
            cursor=mydb.cursor(buffered=True)
            cursor.execute('select email_status from users where email=%s',[email])
            status=cursor.fetchone()[0]
            cursor.close()
            if status!='confirmed':
                flash('Please confirm your mail first')
                return render_template('forgot.html')
            else:
                subject='Email Confirmation'
                confirm_link=url_for('reset',token=token(email,salt2),_external=True)
                body=f"Use this link to reset password - \n\n{confirm_link}"
                sendmail(to=email,body=body,subject=subject)
                flash('Password reset link sent check your email')
                return redirect(url_for('login'))
        else:
            flash('Invalid email id')
            return render_template('forgot.html')
    return render_template('forgot.html')

@app.route('/reset/<token>',methods=['GET','POST'])
def reset(token):
    try:
        serializer=URLSafeTimedSerializer(secret_key)
        email=serializer.loads(token,salt=salt2,max_age=120) 
    except:
        abort(404,'Link expired')
    else:
        if request.method=='POST':
            newpassword=request.form['npassword']
            confirmpassword=request.form['cpassword']
            if newpassword==confirmpassword:
                cursor=mydb.cursor(buffered=True)
                cursor.execute('update users set password=%s where email=%s',[newpassword,email])
                mydb.commit()
                cursor.close()
                flash('Reset successful')
                return redirect(url_for('login'))
            else:
                flash('Password mismatched')
                return render_template('newpassword.html')
        return render_template('newpassword.html')

@app.route('/logout')
def logout():
    if session.get('user'):
        session.pop('user')
        return redirect(url_for('login'))
    else:
        return redirect(url_for('login'))

@app.route('/save_article',methods=['GET'])
def save_article():
    if session.get('user'):
        username=session.get('user')
        hl = request.args.get('title')
        article_url = request.args.get('url')
        cursor=mydb.cursor(buffered=True)
        cursor.execute('insert into newsletter(username,headline,article_url) values(%s,%s,%s)',(username,hl,article_url))
        mydb.commit()
        cursor.close()
        flash('Article saved successfully !')
        return redirect(request.referrer)
    else:
        return redirect(url_for('login')) 
    return render_template('news.html')

@app.route('/generate_newsletter')
def generate_newsletter():
    if session.get('user'):
        username=session.get('user')
        newsletter_content = f"Latest News\n\n"
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select headline,article_url from newsletter where username=%s',[username])
        contents=cursor.fetchall()
        cursor.close()
        for content in contents:
            title=content[0]
            url=content[1]
            article_card = f"Title: {title}\nURL: {url}\n\n"
            newsletter_content+=article_card
    return newsletter_content

@app.route('/send_newsletter')
def send_newsletter():
    if session.get('user'):
        username=session.get('user')
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select email from users where username=%s',[username])
        email=cursor.fetchone()[0]
        newsletter_content = generate_newsletter()
        subject='Top headlines'
        body=newsletter_content
        sendmail(to=email,body=body,subject=subject)
        cursor.execute('delete from newsletter where username=%s',[username])
        mydb.commit()
        cursor.close()
        return redirect(url_for('home'))
    else:
        return redirect(url_for('login'))
    return redirect(url_for('home'))

@app.route('/aboutus')
def aboutus():
    if session.get('user'):
        return render_template('aboutus.html')
    else:
        return redirect(url_for('login'))

if __name__ == '__main__':
    app.run()

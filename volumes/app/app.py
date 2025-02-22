from flask import Flask, render_template, request, flash, redirect, url_for, session, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from flask_simpleldap import LDAP
from datetime import timedelta
from json import dumps
from conf import config
import validators

app = Flask(__name__)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db/links.db'
app.config['SECRET_KEY'] = config['SECRET_KEY']
app.config['PERMANENT_SESSION_LIFETIME'] =  timedelta(minutes=15)

ldap = LDAP(app)

db = SQLAlchemy(app)
from models import *

@app.route('/', methods=('GET', 'POST'))
def index():
    if session.get('status'):
        links = Link.query.all()
        return render_template('index.html', links=links)
    else:
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('status'):
        return redirect(url_for('index'))
    else:
        if request.method == 'GET':
            return render_template('login.html')
        else:
            login = str(request.form['login'])
            password = str(request.form['password'])
            q = ldap.bind_user(login, password)
            if password and q == True:
                session['status'] = True
                session['login'] = login
                return redirect(url_for('index'))
            else:
                return 'Bad Login '

@app.route('/logout', methods=['GET'])
def logout():
    if session.get('status'):
        session['status'] = False
        return redirect(url_for('login'))
    else:
        return redirect(url_for('login'))

@app.route('/add', methods=['POST'])
def add():
    if session.get('status'):
        url = request.form['url']

        if not validators.url(url):
            flash('A valid URL is required!', 'danger')
            return redirect(url_for('index'))

        try:
            new_link = Link(url = url)
            db.session.add(new_link)
            db.session.commit()
        except IntegrityError:
            flash('URL already registred', 'danger')
            return redirect(url_for('index'))

        str_tags = request.form['tags']
        q = Link.query.filter_by(url=url).first()
        for name in str_tags.split(','):
            new_tag = Tag(name = name.strip().lower(), link_id = q.id)
            db.session.add(new_tag)
            db.session.commit()
        flash('Link has been added', 'success')
        return redirect(url_for('index'))
    else:
        return redirect(url_for('login'))

@app.route('/like/<id>')
def like(id):
    if session.get('status'):
        login = session.get('login')
        q = Like.query.filter_by(link_id=id, login=login).first()
        if q is None:
            new_like = Like(login=login, link_id=id)
            db.session.add(new_like)
            db.session.commit()
        elif login in q.login:
            Like.query.filter_by(link_id=id, login=login).delete()
            db.session.commit()
        res = {"nb": len(Link.query.filter_by(id=id).first().likes), "users": [x[0] for x in Like.query.with_entities(Like.login).filter_by(link_id=id).all()]}
        return Response(dumps(res), mimetype='application/json', status=200)    
    else:
        return redirect(url_for('login'))

@app.route('/dislike/<id>')
def dislike(id):
    if session.get('status'):
        login = session.get('login')
        q = Dislike.query.filter_by(link_id=id, login=login).first()
        if q is None:
            new_dislike = Dislike(login=login, link_id=id)
            db.session.add(new_dislike)
            db.session.commit()
        elif login in q.login:
            Dislike.query.filter_by(link_id=id, login=login).delete()
            db.session.commit()
        res = {"nb": len(Link.query.filter_by(id=id).first().dislikes), "users": [x[0] for x in Dislike.query.with_entities(Dislike.login).filter_by(link_id=id).all()]}
        return Response(dumps(res), mimetype='application/json', status=200)    
    else:
        return redirect(url_for('login'))

@app.route('/edit/<id>', methods=('GET', 'POST'))
def edit(id):
    if session.get('status'):
        str_tags = request.form['tags']
        Tag.query.filter_by(link_id=id).delete()
        for name in str_tags.split(','):
            new_tag = Tag(name = name.strip().lower(), link_id = id)
            db.session.add(new_tag)
            db.session.commit()
        flash('Link has been modified', 'success')
        return redirect(url_for('index'))
    else:
        return redirect(url_for('login'))

@app.route('/archive/<id>')
def archive(id):
    if session.get('status'):
        q = Link.query.filter_by(id=id).first()
        if q.archive:
            q.archive = False
            res = {'restore': True}
            flash('Link has been restored', 'success')
        else:
            q.archive = True
            res = {'archive': True}
            flash('Link has been archived', 'success')
        db.session.commit()
        return (dumps(res), 200)
    else:
        return redirect(url_for('login'))
        
@app.route('/delete/<id>', methods=('GET', 'POST'))
def delete(id):
    if session.get('status'):
        Link.query.filter_by(id=id).delete()
        db.session.commit()
        flash('Link has been deleted', 'danger')
        return redirect(url_for('index'))
    else:
        return redirect(url_for('login'))

@app.route('/tags')
def tags():
    if session.get('status'):
        q = Tag.query.with_entities(Tag.name).group_by(Tag.name).all()
        return Response(dumps([ tag[0] for tag in q]), mimetype='application/json', status=200  )

@app.route('/tag/<name>')
def tag(name):
    if session.get('status'):
        look_for = '%{0}%'.format(name)
        q = Tag.query.with_entities(Tag.name).filter(Tag.name.like(look_for)).group_by(Tag.name).all()
        return Response(dumps([ tag[0] for tag in q]), mimetype='application/json', status=200  )

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=80)

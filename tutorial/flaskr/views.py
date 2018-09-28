from functools import wraps
from flask import request, redirect, url_for, render_template, flash, abort, \
        jsonify, session, g
from flaskr import app, db
from flaskr.models import Entry, User
import requests, json, sys, urllib3
import pdb
from collections import Counter
import collections

def login_required(f):
    @wraps(f)
    def decorated_view(*args, **kwargs):
        if g.user is None:
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated_view

@app.before_request
def load_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = User.query.get(session['user_id'])


@app.route('/')
def show_entries():
    entries = Entry.query.order_by(Entry.id.desc()).all()
    return render_template('show_entries.html', entries=entries)

@app.route('/add', methods=['POST'])
def add_entry():
    entry = Entry(
            title=request.form['title'],
            text=request.form['text']
            )
    db.session.add(entry)
    db.session.commit()
    flash('New entry was successfully posted')
    return redirect(url_for('show_entries'))


@app.route('/users/')
# @login_required
def user_list():
    users = User.query.all()
    return render_template('user/list.html', users=users)

@app.route('/users/<int:user_id>/')
# @login_required
def user_detail(user_id):
    user = User.query.get(user_id)
    return render_template('user/detail.html', user=user)

@app.route('/users/<int:user_id>/edit/', methods=['GET', 'POST'])
# @login_required
def user_edit(user_id):
    user = User.query.get(user_id)
    if user is None:
        abort(404)
    if request.method == 'POST':
        user.name=request.form['name']
        user.email=request.form['email']
        if request.form['password']:
            user.password=request.form['password']
        #db.session.add(user)
        db.session.commit()
        return redirect(url_for('user_detail', user_id=user_id))
    return render_template('user/edit.html', user=user)

@app.route('/users/create/', methods=['GET', 'POST'])
# @login_required
def user_create():
    if request.method == 'POST':
        user = User(name=request.form['name'],
                    email=request.form['email'],
                    password=request.form['password'])
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('user_list'))
    return render_template('user/edit.html')

@app.route('/users/<int:user_id>/delete/', methods=['DELETE'])
def user_delete(user_id):
    user = User.query.get(user_id)
    if user is None:
        response = jsonify({'status': 'Not Found'})
        response.status_code = 404
        return response
    db.session.delete(user)
    db.session.commit()
    return jsonify({'status': 'OK'})


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user, authenticated = User.authenticate(db.session.query,
                request.form['email'], request.form['password'])
        if authenticated:
            session['user_id'] = user.id
            flash('You were logged in')
            return redirect(url_for('show_entries'))
        else:
            flash('Invalid email or password')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You were logged out')
    return redirect(url_for('show_entries'))

@app.route('/menu')
def menu():
    users = request.args.getlist('userID[]')
    users = list(filter(lambda u: len(u) > 0, users))
    if users:
        # {'monaga0518': weeklytrackchart, 'marutaku': weeklytrackchart}
        weeklytrackcharts = {}
        for user in users:
            url = "http://ws.audioscrobbler.com/2.0/?method=user.getweeklytrackchart&user=" + user + "&api_key=8c42502db628c941691f3212cf636c5e&format=json";
            # print(url)
            r = requests.get(url)
            data = r.json()
            # print(data)
            # print(data['weeklytrackchart']['track'])
            weeklytrackchart = data['weeklytrackchart']['track']
            weeklytrackcharts[user] = weeklytrackchart

        # for song in weeklytrackchart:
            # print(song)
        lovedtracks = {}
        for user in users:
            url = "http://ws.audioscrobbler.com/2.0/?method=user.getlovedtracks&user=" + user + "&api_key=8c42502db628c941691f3212cf636c5e&format=json";
            # print(url)
            r = requests.get(url)
            data = r.json()
            lovedtrack = data['lovedtracks']['track']
            lovedtracks[user] = lovedtrack
            # print(lovedtracks[user])

        # 完全一致を調べる（lovedtracks）
        lovedtracks_set = []
        for tracks in lovedtracks.values():
            lovedtracks_set.extend(tracks)
        lovedtracks_set = list({track['url']: track for track in lovedtracks_set}.values())

        loved_urls = []
        for user in users:
            for song in lovedtracks[user]:
                loved_urls.append(song['url'])

        ## 同じurlを含むものの取得(lovedtracks)
        recommend_songs_url = []
        for url, count in Counter(loved_urls).items():
            if count > 1:
                recommend_songs_url.append(url)

        recommend_songs = []
        for track in lovedtracks_set:
            if track['url'] in recommend_songs_url:
                recommend_songs.append(track)

        # 完全一致を調べる（weekly）
        weeklytrackcharts_set = []
        for tracks in weeklytrackcharts.values():
            weeklytrackcharts_set.extend(tracks)
        weeklytrackcharts_set = list({track['url']: track for track in weeklytrackcharts_set}.values())

        weekly_urls = []
        for user in users:
            for song in weeklytrackcharts[user]:
                weekly_urls.append(song['url'])
        print(Counter(weekly_urls))

        ## 同じurlを含むものの取得(weeklytrackcharts)
        for url, count in Counter(weekly_urls).items():
            if count > 1:
                recommend_songs_url.append(url)

        for track in weeklytrackcharts_set:
            if track['url'] in recommend_songs_url:
                recommend_songs.append(track)

        # lovedtrackから類似する曲を取得
        similartracks = {}
        for user, lovedtrack in lovedtracks.items():
            for song in lovedtrack:
                # song['name']
                # song['artist']['name']
                url = "http://ws.audioscrobbler.com/2.0/?method=track.getsimilar&artist=" + song['artist']['name'] + "&track=" + song['name'] + "&api_key=8c42502db628c941691f3212cf636c5e&format=json"
                # print(url)
                r = requests.get(url)
                data = r.json()
                similartrack = data['similartracks']['track']
                similartracks[user] = similartrack
                # print(similartracks[user])

        ##類似曲の中で同じurlを含むものの取得(lovedtracks)
        similartracks_set = []
        for tracks in similartracks.values():
            similartracks_set.extend(tracks)
            # print(similartracks_set)
        similartracks_set = list({track['url']: track for track in similartracks_set}.values())

        similar_urls = []
        for user in users:
            for song in similartracks[user]:
                similar_urls.append(song['url'])
                # print(similar_urls)

        for url, count in Counter(similar_urls).items():
            if count > 1:
                recommend_songs_url.append(url)

        for track in similartracks_set:
            if track['url'] in recommend_songs_url:
                recommend_songs.append(track)


        # weeklyから類似する曲を取得
        # similartracks = {}
        for user, similartrack in weeklytrackcharts.items():
            for song in similartrack:
                # song['name']
                # song['artist']['name']
                url = "http://ws.audioscrobbler.com/2.0/?method=track.getsimilar&artist=" + song['artist']['#text'] + "&track=" + song['name'] + "&api_key=8c42502db628c941691f3212cf636c5e&format=json"
                # print(url)
                r = requests.get(url)
                data = r.json()
                similartrack = data['similartracks']['track']
                similartracks[user] = similartrack
                # print(similartracks[user])

        ##類似曲の中で同じurlを含むものの取得(weekly)
        for tracks in similartracks.values():
            similartracks_set.extend(tracks)
            # print(similartracks_set)
        similartracks_set = list({track['url']: track for track in similartracks_set}.values())

        # similar_urls = []
        for user in users:
            for song in similartracks[user]:
                similar_urls.append(song['url'])
                # print(similar_urls)

        for url, count in Counter(similar_urls).items():
            if count > 1:
                recommend_songs_url.append(url)

        for track in similartracks_set:
            if track['url'] in recommend_songs_url:
                recommend_songs.append(track)

        #アーティストの類似度が高い曲を取得(weekly)
        






        # weekly_urls = []
        # for user in users:
        #     for song in lovedtracks[user]:
        #         weekly_urls.append(song['url'])
        # print(Counter(weekly_urls))

    else:
        weeklytrackcharts = None
        lovedtracks = None
        recommend_songs = None
        similartracks = None
    # return render_template('menu.html', user=user, weeklytrackcharts=weeklytrackcharts, lovedtracks=lovedtracks)
    return render_template('menu.html', weeklytrackcharts=weeklytrackcharts, lovedtracks=lovedtracks, recommend_songs=recommend_songs, similartracks=similartracks)

@app.route('/deux')
def deux():
    return render_template('deux.html')

@app.route('/restaurants')
def restaurants():
    # payload = {'keyid': '8c42502db628c941691f3212cf636c5e', 'format': 'json'}
    r = requests.get('http://ws.audioscrobbler.com/2.0/?method=album.getinfo&api_key=8c42502db628c941691f3212cf636c5e&artist=HYDE&album=HYDE&format=json')
    data = r.json()
    print(data)
    # rests=data["album"]

    return render_template('restaurants.html')

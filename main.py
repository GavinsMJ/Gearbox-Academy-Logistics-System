from flask import Flask, request
import flask
import mysql.connector
import bcrypt
import os
import json

DATABASE_USER = 'phpmyadmin'
DATABASE_PASSWORD = '123456'
DATABASE_HOST = 'localhost'
DATABASE_NAME = 'gearbox_academy_logistics'

IMAGES_DIRECTORY = './static/images/'

app = Flask(__name__)
app.secret_key = "jiugyfhafd76e48w3yrgeurbgi7846e7rt"

my_db = mysql.connector.connect(
    host=DATABASE_HOST,
    user=DATABASE_USER,
    password=DATABASE_PASSWORD,
    database=DATABASE_NAME
)
my_cursor = my_db.cursor(dictionary=True)


@app.route('/', methods=['GET'])
def index():
    if not flask.session.get('logged_in'):
        return flask.redirect(flask.url_for('login'))
    return flask.render_template('home.html')


@app.route('/logout', methods=['GET'])
def logout():
    flask.session.clear()
    return flask.redirect(flask.url_for('index'))


#############################
# User section begins here  #
#############################

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'submit' in request.form:
        email = request.form['email']
        password = request.form['password']

        my_cursor.execute(f'SELECT * FROM users WHERE email=\'{email}\' AND password=\'{password}\'')

        result = my_cursor.fetchall()

        if len(result) == 0:
            flask.session['error-message'] = 'Invalid email or password.'
            return flask.render_template('login.html')
        else:
            # here user has logged in successfully
            flask.session['logged_in'] = True
            flask.session['user_id'] = result[0].get('id')
            return flask.redirect(flask.url_for('index'))

    else:
        return flask.render_template('login.html')


@app.route('/search-items', methods=['GET', 'POST'])
def search_items():
    # first check if user is logged in
    if not flask.session.get('logged_in'):
        return flask.redirect(flask.url_for('login'))

    if 'add-item-to-cart' in request.form:
        item_id = request.form['id']
        user_id = flask.session.get('user_id')

        my_cursor.execute('INSERT INTO cart (user_id, item_id, quantity) '
                          'VALUES (%s,%s,"1")',
                          (user_id, item_id))
        my_db.commit()

        my_cursor.execute('SELECT name FROM items WHERE id = %s', (item_id,))
        result = my_cursor.fetchone()

        return flask.jsonify(result)

    my_cursor.execute(f'SELECT * FROM items')
    items = my_cursor.fetchall()

    return flask.render_template('search-items.html', items=items)


@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    # first check if user is logged in
    if not flask.session.get('logged_in'):
        return flask.redirect(flask.url_for('login'))

    user_id = flask.session.get('user_id')

    if 'delete-item-from-cart' in request.form:
        item_id = request.form['id']
        my_cursor.execute('DELETE FROM cart WHERE user_id = %s AND item_id = %s', (user_id, item_id))
        my_db.commit()

        my_cursor.execute('SELECT id,name FROM items WHERE id = %s', (item_id,))
        result = my_cursor.fetchone()

        return flask.jsonify(result)
    elif 'open-locks' in request.form:
        items = request.form['items']

        shelves_to_open = []

        for item in json.loads(items):
            my_cursor.execute('SELECT shelf,drawer FROM items WHERE id = %s', (item.get('id'),))
            result = my_cursor.fetchone()
            shelves_to_open.append(result.get('shelf'))

            my_cursor.execute('INSERT INTO logs (user_id, item_id, quantity)'
                              'VALUES (%s,%s,%s)', (user_id, item.get('id'), item.get('quantity')))
            my_db.commit()

        # here is where we should communicate with the nodeMcu to open locks
        shelves_to_open = set(shelves_to_open)

        # clear users cart items
        my_cursor.execute('DELETE FROM cart WHERE user_id = %s ', (user_id,))
        my_db.commit()

    my_cursor.execute('SELECT * FROM cart WHERE user_id = %s', (user_id,))
    results = my_cursor.fetchall()
    items = []
    # probably should use mysql join here
    for result in results:
        my_cursor.execute('SELECT * FROM items WHERE id = %s', (result.get('item_id'),))
        items.append(my_cursor.fetchone())

    return flask.render_template('checkout.html', items=items)


#############################
# Admin section begins here #
#############################


@app.route('/admin', methods=['GET'])
def admin():
    if not flask.session.get('admin_logged_in'):
        return flask.redirect(flask.url_for('admin_login'))
    return flask.render_template('admin/home.html')


@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if 'submit' in request.form:
        email = request.form['email']
        password = request.form['password']

        my_cursor.execute(f'SELECT * FROM admin WHERE email=\'{email}\' AND password=\'{password}\'')

        result = my_cursor.fetchall()

        if len(result) == 0:
            flask.session['error-message'] = 'Invalid email or password.'
            return flask.render_template('admin/login.html')

        else:
            # here Admin has logged in successfully
            flask.session['admin_logged_in'] = True
            return flask.redirect(flask.url_for('admin'))

    else:
        return flask.render_template('admin/login.html')


############################
# Admin management section #
############################

@app.route('/manage-users', methods=['GET', 'POST'])
def manage_users():
    # first check if admin is logged
    if not flask.session.get('admin_logged_in'):
        return flask.redirect(flask.url_for('admin_login'))

    if 'add-user' in request.form:
        first_name = request.form['firstname']
        second_name = request.form['lastname']
        email = request.form['email']
        mobile = request.form['mobile']

        # here is where we hash our passwords to store them securely
        hashed_password = bcrypt.hashpw(email.encode('utf-8'), bcrypt.gensalt())

        my_cursor.execute('INSERT INTO users (first_name, second_name, email, mobile, profile_pic, password) '
                          'VALUES (%s,%s,%s,%s,"profile.jpg",%s)',
                          (first_name, second_name, email, mobile, hashed_password))
        my_db.commit()

        flask.session['success-message'] = f'User {first_name} {second_name} added successfully'
    elif 'delete-user' in request.form:
        user_id = request.form['id']

        my_cursor.execute('DELETE FROM users WHERE id = %s', (user_id,))
        my_db.commit()

        flask.session['success-message'] = f'User Deleted successfully'
    elif 'get-row' in request.form:
        user_id = request.form['id']
        my_cursor.execute('SELECT id, first_name, second_name FROM users WHERE id = %s', (user_id,))
        user = my_cursor.fetchone()
        return flask.jsonify(user)

    my_cursor.execute(f'SELECT * FROM users')
    users = my_cursor.fetchall()

    return flask.render_template('admin/manage-users.html', users=users)


@app.route('/manage-items', methods=['GET', 'POST'])
def manage_items():
    # first check if admin is logged in
    if not flask.session.get('admin_logged_in'):
        return flask.redirect(flask.url_for('admin_login'))

    if 'add-item' in request.form:
        name = request.form['name']
        shelf = request.form['shelf']
        drawer = request.form['drawer']
        quantity = request.form['quantity']
        description = request.form['description']
        link = request.form['link']
        if request.files['photo'].filename == '':
            image_path = 'profile.jpg'
        else:
            photo = request.files['photo']
            image_path = f'items/{name}-{photo.filename}'
            photo.save(os.path.join(IMAGES_DIRECTORY, image_path))

        my_cursor.execute('INSERT INTO items (name, image, shelf, drawer, quantity, description, external_link) '
                          'VALUES (%s,%s,%s,%s,%s,%s, %s)',
                          (name, image_path, shelf, drawer, quantity, description, link))
        my_db.commit()

        flask.session['success-message'] = f'Item {name} added successfully'
    elif 'edit-item' in request.form:
        item_id = request.form['id']
        name = request.form['name']
        shelf = request.form['shelf']
        drawer = request.form['drawer']
        quantity = request.form['quantity']
        description = request.form['description']
        link = request.form['link']
        if request.files['photo'].filename == '':
            my_cursor.execute('UPDATE items SET name=%s, shelf=%s, drawer=%s, quantity=%s, description=%s, '
                              'external_link=%s '
                              'WHERE id = %s', (name, shelf, drawer, quantity, description, link, item_id))
        else:
            photo = request.files['photo']
            image_path = f'items/{name}-{photo.filename}'
            photo.save(os.path.join(IMAGES_DIRECTORY, image_path))

            my_cursor.execute('UPDATE items SET name=%s, image=%s, shelf=%s, drawer=%s, quantity=%s, description=%s, '
                              'external_link=%s '
                              'WHERE id = %s', (name, image_path, shelf, drawer, quantity, description, link, item_id))

        my_db.commit()

        flask.session['success-message'] = f'Item {name} updated successfully'

    elif 'delete-item' in request.form:
        user_id = request.form['id']

        my_cursor.execute('DELETE FROM items WHERE id = %s', (user_id,))
        my_db.commit()

        flask.session['success-message'] = f'Item Deleted successfully'
    elif 'get-row' in request.form:
        user_id = request.form['id']
        my_cursor.execute('SELECT * FROM items WHERE id = %s', (user_id,))
        user = my_cursor.fetchone()
        return flask.jsonify(user)

    my_cursor.execute(f'SELECT * FROM items')
    items = my_cursor.fetchall()

    return flask.render_template('admin/manage-items.html', items=items)


if __name__ == '__main__':
    app.run(threaded=True, port=5000, debug=False)

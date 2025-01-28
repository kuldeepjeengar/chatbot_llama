from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from database import extract_data
import pandas as pd
import logging

app = Flask(__name__)
app.secret_key = 'admin@123'
# Configure logging
logging.basicConfig(level=logging.DEBUG)


@app.route('/')
def welcome():
    return render_template("welcome.html")

@app.route('/log_in')
def again():
    error_message = session.pop('error_message', None)
    return render_template("log_in.html",error_message=error_message)


# Route for the login page (root URL)
@app.route('/log_in', methods=['POST'])
def log_in():

    if request.method == 'POST':
        # global username
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            session['error_message'] = 'Invalid username or password, please try again.'
            return redirect(url_for('again'))
        try:
            # Fetch user data from the database
            user_data = extract_data(username)
            if not user_data:
                session['error_message'] = 'Invalid username or password, please try again.'

                return redirect(url_for('again'))

            df = pd.DataFrame(user_data)
            input_username = df['name'].tolist()
            input_password = df['password'].tolist()

            # Check if the username and password match
            
            if username in input_username and password in input_password:
                # global username
                return redirect(url_for('home',username=username))
            else:
                session['error_message'] = 'Invalid username or password, please try again.'
                return redirect(url_for('again'))
            

        except Exception as e:
            session['error_message'] = 'Invalid username or password, please try again.'
            return redirect(url_for('again'))

    return render_template("log_in.html")



@app.route('/home/<username>')
def home(username):
    return render_template('home.html')

if __name__ == '__main__':
    app.run(debug=True)
from flask import Flask, render_template, request, jsonify, redirect,url_for

app = Flask(__name__)

# Route for the login page (root URL)
@app.route('/log_in', methods=['GET', 'POST'])
def log_in():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # Process the username and password here

        if username and password:
            return redirect(url_for('home'))

    return render_template("log_in.html")

@app.route('/home')
def home():
    return render_template('home.html')  

if __name__ == '__main__':
    app.run(debug=True)

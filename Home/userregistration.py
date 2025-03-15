#This file stores student information into SQL database for future access, and saves into server-side for login

from flask import Flask, request, redirect, render_template
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'  #  STUDENT INFO DATABASE
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

#TRANSLATE USER INFO INTO SQLITE DATABASE. EACH ROW = 1 USER
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)  
    last_name = db.Column(db.String(50), nullable=False)  
    password_hash = db.Column(db.String(128), nullable=False)

with app.app_context():
    db.drop_all()  # Remove the existing tables
    db.create_all() #INCLUDES 'USER' IN THE DATABASE

#STUDENT & TEACHER SIGN-UP URL
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        first_name = request.form['first_name']  # Get first name
        last_name = request.form['last_name'] 
        email = request.form['email']
        return redirect(f'/create-password?email={email}') #redirect to next page, createPassword.HTML
    return render_template('signup.html')

#REGISTER THE PASSWORD & STORE EMAIL + PASSWORD INTO DATABASE
@app.route('/create-password', methods=['GET', 'POST'])
def create_password():
    email = request.args.get('email')  
    first_name = request.args.get('first_name')
    last_name = request.args.get('last_name')
    
    if request.method == 'POST':
        password = request.form['password']
        password_hash = generate_password_hash(password)
        
        #store email, password, and first+last name
        user = User(email=email, password_hash=password_hash)
        db.session.add(user)
        db.session.commit() #commit to SQL database
        return redirect('/login')   
    return render_template('password.html')

# IF EXISTING USERS NEED TO BE QUERIED: 
# users = User.query.all()
# for user in users:
#     print(user.first_name, user.last_name, user.email)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']  
        password = request.form['password'] 
        
        user = User.query.filter_by(email=email).first()  
        
        if user:
            if check_password_hash(user.password_hash, password):  
                return 'Login Successful' 
            else:
                return render_template('login.html', message="Incorrect password, please try again.")  
        else:
            return render_template('login.html', message="Email does not exist, please check again.")  
    return render_template('login.html')  

if __name__ == '__main__':
    app.run(debug=True)

from flask import Blueprint, render_template

# Define the blueprint for home routes
home_bp = Blueprint('home', __name__)

@home_bp.route("/home")
def home():
    return render_template("home.html")

@home_bp.route("/interface")
def interface():
    return render_template("interface.html")

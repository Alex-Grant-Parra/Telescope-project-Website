from flask import Blueprint, render_template

# Define the blueprint for interface routes
interface_bp = Blueprint('interface', __name__)

@interface_bp.route("/interface")
def interface():
    return render_template("interface.html")
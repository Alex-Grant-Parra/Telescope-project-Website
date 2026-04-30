from flask import Blueprint, render_template


process_bp = Blueprint("process", __name__)


@process_bp.route("/process")
def process():
    return render_template("process.html")
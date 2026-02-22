from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import pandas as pd
import os
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import pagesizes
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics



app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['UPLOAD_FOLDER'] = 'uploads'

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


# ------------------ MODELS ------------------

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    role = db.Column(db.String(20))
    department = db.Column(db.String(50))


class Timetable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.String(20))
    period = db.Column(db.String(20))
    room = db.Column(db.String(50))
    department = db.Column(db.String(50))
    subject = db.Column(db.String(100))
    professor = db.Column(db.String(100))


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ------------------ ROUTES ------------------

@app.route('/')
def home():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.password == request.form['password']:
            login_user(user)
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('hod_dashboard'))
        flash("Invalid credentials")

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ------------------ ADMIN ------------------

@app.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return "Unauthorized"
    return render_template('admin_dashboard.html')


@app.route('/upload', methods=['POST'])
@login_required
def upload():

    if current_user.role != 'admin':
        return "Unauthorized"

    file = request.files['file']
    filename = file.filename
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # Clear old timetable (optional but recommended)
    Timetable.query.delete()
    db.session.commit()

    # If Excel file
    if filename.endswith(('.xlsx', '.xls')):

        excel_file = pd.ExcelFile(filepath)

        for sheet in excel_file.sheet_names:
            df = pd.read_excel(excel_file, sheet_name=sheet)

            for index, row in df.iterrows():
                day = row[0]

                for col in df.columns[1:]:
                    department = row[col]

                    entry = Timetable(
                        day=str(day),
                        period=str(col),
                        room=str(sheet),
                        department=str(department)
                    )
                    db.session.add(entry)

    # If CSV file
    elif filename.endswith('.csv'):

        df = pd.read_csv(filepath)

        room_name = filename.replace('.csv', '')

        for index, row in df.iterrows():
            day = row[0]

            for col in df.columns[1:]:
                department = row[col]

                entry = Timetable(
                    day=str(day),
                    period=str(col),
                    room=str(room_name),
                    department=str(department)
                )
                db.session.add(entry)

    else:
        return "Unsupported file format"

    db.session.commit()
    flash("File uploaded successfully")
    return redirect(url_for('admin_dashboard'))

# ------------------ HOD ------------------

@app.route('/hod')
@login_required
def hod_dashboard():
    view = request.args.get("view", "full")

    if view == "own":
        entries = Timetable.query.filter_by(
            department=current_user.department
        ).all()
    else:
        entries = Timetable.query.all()

    return render_template(
        'hod_dashboard.html',
        entries=entries,
        view=view
    )


@app.route('/edit/<int:id>', methods=['POST'])
@login_required
def edit(id):
    entry = Timetable.query.get(id)

    if current_user.department != entry.department:
        return "Unauthorized"

    entry.subject = request.form['subject']
    entry.professor = request.form['professor']
    db.session.commit()

    return redirect(url_for('hod_dashboard'))

# @app.route('/download_pdf')
# @login_required
# def download_pdf():

#     filename = f"{current_user.department}_timetable.pdf"
#     filepath = os.path.join("uploads", filename)

#     doc = SimpleDocTemplate(
#         filepath,
#         pagesize=pagesizes.landscape(pagesizes.A4)
#     )

#     elements = []

#     # Get department data
#     entries = Timetable.query.filter_by(
#         department=current_user.department
#     ).all()

#     # Get unique days, sections, periods
#     days = sorted(list(set([e.day for e in entries])))
#     sections = sorted(list(set([e.room for e in entries])))
#     periods = sorted(list(set([e.period for e in entries])))

#     # Header row
#     data = [["Day", "Section"] + periods]

#     for day in days:
#         for section in sections:

#             row = [day, section]

#             for period in periods:
#                 cell = ""

#                 entry = Timetable.query.filter_by(
#                     day=day,
#                     room=section,
#                     period=period,
#                     department=current_user.department
#                 ).first()

#                 if entry and entry.subject:
#                     cell = f"{entry.subject}\n({entry.professor})"

#                 row.append(cell)

#             data.append(row)

#     table = Table(data)

#     table.setStyle(TableStyle([
#         ('GRID', (0,0), (-1,-1), 1, colors.black),
#         ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
#         ('ALIGN', (0,0), (-1,-1), 'CENTER'),
#         ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
#     ]))

#     elements.append(table)
#     doc.build(elements)

#     return redirect("/" + filepath)
@app.route('/print')
@login_required
def print_view():

    # Proper academic day order
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

    # Get ALL entries (not filtered)
    all_entries = Timetable.query.all()

    # Unique sections and periods
    sections = sorted(list(set([e.room for e in all_entries])))
    periods = sorted(list(set([e.period for e in all_entries])))

    # Build timetable structure
    timetable = {}

    for day in day_order:
        timetable[day] = {}

        for section in sections:
            timetable[day][section] = {}

            for period in periods:
                timetable[day][section][period] = ""

                entry = Timetable.query.filter_by(
                    day=day,
                    room=section,
                    period=period,
                    department=current_user.department
                ).first()

                if entry and entry.subject:
                    timetable[day][section][period] = f"{entry.subject} ({entry.professor})"

    return render_template(
        'print.html',
        timetable=timetable,
        days=day_order,
        sections=sections,
        periods=periods
    )

# ------------------ MAIN ------------------

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

        # Create default users (ONLY RUN ONCE)
        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin", password="admin123", role="admin", department="")
            cs = User(username="cs_hod", password="123", role="hod", department="CS")
            civil = User(username="civil_hod", password="123", role="hod", department="Civil")

            db.session.add(admin)
            db.session.add(cs)
            db.session.add(civil)
            db.session.commit()

    app.run(debug=True)
    
    
    
    
    
    
    
#     username: admin
# password: admin123


# username: cs_hod
# password: 123



# username: civil_hod
# password: 123
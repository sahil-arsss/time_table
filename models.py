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
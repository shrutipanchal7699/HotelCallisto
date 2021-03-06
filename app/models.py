import enum
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import and_, or_

from app.helpers import cast_date

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(128), index=True, unique=True)
    password_hash = db.Column(db.String(128))

    def __repr__(self):
        return '<User {}>'.format(self.email)

    @classmethod
    def create(cls, email, password):
        pw_hash = generate_password_hash(password, method='sha256')
        new_user = cls(email=email, password_hash=pw_hash)
        db.session.add(new_user)
        db.session.commit()
        return new_user

    @classmethod
    def get_by_id(cls, id):
        return cls.query.get(int(id))
    
    #Accepts username and password, return the user if the login information is good
    @classmethod
    def check_login(cls, email, password):
        user = cls.query.filter_by(email=email).first()
        if user:
            if check_password_hash(user.password_hash, password):
                return user
        return None

    def delete_account(self, password):
        if check_password_hash(self.password_hash, password):
            db.session.delete(self)
            db.session.commit()

    def delete_reservation(self, res_id):
        target =  Reservation.query.get(int(res_id))
        if target and target.user_id == self.id:
            db.session.delete(target)
            db.session.commit()
            return True
        return False

    def update_password(self, new_password, old_password):
        if check_password_hash(self.password_hash, old_password):
            pw_hash = generate_password_hash(new_password, method='sha256')
            self.password_hash = pw_hash
            db.session.commit()



class RoomType(enum.Enum):
    Regular = 'Regular'
    Executive = 'Executive'
    Presidential = 'Presidential'

#class for Room 
class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    num_beds = db.Column(db.Integer, nullable=False)
    num_baths = db.Column(db.Integer, nullable=False)

    room_type = db.Column(db.Enum(RoomType), nullable=False)
    price = db.Column(db.Float, nullable=False)
    max_occupants = db.Column(db.Integer, nullable=False)

    @classmethod
    def get_by_id(cls, id):
        return cls.query.get(int(id))

    @classmethod
    def fetch_room_to_query(cls, query):
        """
        Expected query object:
            check_in_date (required)- date user intends to check in
            check_out_date (required) - date user intends to check out
            room_type - type of room
            num_occupants - number of occupants user intends to bring
        """
        #Construct query
        rooms = cls.query
        if query['room_type']:
            rooms = rooms.filter(Room.room_type == query['room_type'])
        if query['num_occupants']:
            rooms = rooms.filter(Room.max_occupants >= query['num_occupants'])
        #Return a list
        rooms = rooms.all()
        rooms = filter(
            lambda room: room.is_available_between(query['check_in_date'], query['check_out_date']), 
            rooms)

        return list(rooms)

    def is_available_between(self, start, end):
        """
        Given a start date and end date, 
        check if the room is wholy available between that time period
        """
        conflicting_reservations = Reservation.find_conflicting_reservations(self.id, start, end)
        # return true if no conflicting reservations exist
        return len(conflicting_reservations) == 0
    
    def accomodations(self):
        bed_string = str(self.num_beds) + (" bed" if self.num_beds == 1 else " beds")
        bath_string = str(self.num_baths) + (" bath" if self.num_baths == 1 else " baths")
        return bed_string + ", " + bath_string


#reservation Class 
class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    check_in_date = db.Column(db.Date, nullable=False)
    check_out_date = db.Column(db.Date, nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User',backref=db.backref('reservations', lazy=True, cascade="all"))

    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    room = db.relationship('Room',backref=db.backref('reservations', lazy=True, cascade="all"))

    @classmethod
    def find_conflicting_reservations(cls, room_id, start_date, end_date):
        """ Return all reservations that fits the conditions:
            - Reserved for room with id room_id
            - Start date and end date are NOT both before the target start date
            - Start date and end date are NOT both after the target end date
        """
        reservations = cls.query.filter(
            Reservation.room_id == room_id,
            and_(
                or_(
                    Reservation.check_in_date >= start_date,
                    Reservation.check_out_date >= start_date
                ),
                or_(
                    Reservation.check_in_date <= end_date,
                    Reservation.check_out_date <= end_date
                )
            )
        )
        return reservations.all()

    @classmethod
    def fetch_users_reservation(cls, user_id):
        reservations = cls.query.filter(Reservation.user_id == user_id)
        return reservations

    @classmethod
    def create(cls, check_in_date, check_out_date, room_id, user_id, **kwargs):
        if isinstance(check_in_date, str):
            check_in_date = cast_date(check_in_date)
        if isinstance(check_out_date, str):
            check_out_date = cast_date(check_out_date)

        new_reservation = cls(
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            user_id=user_id,
            room_id=room_id
        )
        db.session.add(new_reservation)
        db.session.commit()
        return new_reservation


class PaymentMethod(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    card_number = db.Column(db.String(16), unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User',backref=db.backref('payment_methods', lazy=True, cascade="all"))

    @classmethod
    def create(cls, name, card_number, user_id):
        new_payment_method = cls(
            name=name,
            card_number=card_number,
            user_id=user_id
        )
        db.session.add(new_payment_method)
        db.session.commit()
        return new_payment_method

    def display_string(self):
        return "●●●● ●●●● ●●●● " + self.card_number[-4:]
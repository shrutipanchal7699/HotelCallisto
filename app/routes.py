from datetime import timedelta, date, datetime

from flask import make_response, render_template, session, request, redirect, url_for, flash
from flask_login import login_user, current_user, logout_user, login_required
from flask_mail import Message, Mail

from app import login_manager
from app.forms import (
    LoginForm, 
    RegisterForm,
    QueryForm, 
    MakeReservationForm, 
    UpdatePasswordForm, 
    DeleteAccountForm,
    AddPaymentMethodForm)
from app.models import User, Room, Reservation, PaymentMethod
from app.helpers import cast_date

mail = Mail()

def configure_routes(app):

    @app.route('/auth')
    def auth_page():
        if current_user.is_authenticated:
            return redirect(url_for('room_list_page'))
        return render_template('auth.html')

    @app.route('/login', methods=['POST'])
    def login():
        f = LoginForm(data=request.form)
        if f.validate():
            #Login user
            login_user(f.valid_user, remember=f.remember.data)
            return redirect(url_for('room_list_page'))
        else:
            #put login errors in flash
            flash('show form', 'show_form_login')
            for field in f:
                for error in field.errors:
                    flash(str(error), 'login_' + field.name)
        return redirect(url_for('auth_page'))

    @app.route('/register', methods=['POST'])
    def register():
        f = RegisterForm(data=request.form)
        if f.validate():
            new_user = User.create(email=f.email.data, password=f.password.data)
            login_user(new_user)
            return redirect(url_for('room_list_page'))
        else:
            flash('show form', 'show_form_register')
            for field in f:
                for error in field.errors:
                    flash(str(error), 'register_' + field.name)
        return redirect(url_for('auth_page'))

    @app.route('/profile')
    @login_required
    def profile_page():
        update_pw_form = UpdatePasswordForm()
        delete_form = DeleteAccountForm()

        return render_template('profile.html', update_pw_form=update_pw_form, delete_form=delete_form)

    @app.route('/profile/update', methods=['POST'])
    @login_required
    def update_password():
        f = UpdatePasswordForm(data=request.form)
        if f.validate():
            current_user.update_password(
                new_password=f.new_password.data,
                old_password=f.password.data
            )
        else:
            flash('show form', 'show_form_updatepw')
            for field in f:
                for error in field.errors:
                    flash(str(error), 'updatepw_' + field.name)
        return redirect(url_for('profile_page'))

    @app.route('/profile/delete', methods=['POST'])
    @login_required
    def delete_account():
        f = DeleteAccountForm(data=request.form)
        if f.validate():
            current_user.delete_account(password=f.password.data)
            logout_user()
            return redirect(url_for('auth_page'))
        else:
            flash('show form', 'show_form_delete_account')
            for field in f:
                for error in field.errors:
                    flash(str(error), 'delete_account_' + field.name)
        return redirect(url_for('profile_page'))

    @app.route('/profile/add_payment', methods=['POST'])
    @login_required
    def add_payment():
        f = AddPaymentMethodForm(data=request.form)
        if f.validate():
            new_payment = PaymentMethod.create(
                name=f.name.data,
                card_number=f.card_number.data,
                user_id=current_user.id
            )
        else:
            for field in f:
                for error in field.errors:
                    flash(str(error), 'add_payment_' + field.name)
        flash('show form', "show_form_add_payment")
        return redirect(url_for('profile_page'))

    #User logout 
    @app.route('/logout')
    def logout():
        if current_user.is_authenticated:
            logout_user()
        return redirect(url_for('auth_page'))
    
    #ContactUs Page
    @app.route('/contactus')
    def contact_us():
        return render_template('contactus.html')
    

    #displays list of rooms to the user
    @app.route('/')
    @app.route('/rooms')
    def room_list_page():
        return render_template('roomList.html')

    @app.route('/fetch_rooms')
    def fetch_room_list():
        cleaned_data = {
            'csrf_token': request.args.get('csrf_token'),
            'check_in_date' : request.args.get('check_in_date', default=date.today(), type=cast_date),
            'check_out_date' : request.args.get('check_out_date', default=date.today(), type=cast_date),
            'num_occupants' : request.args.get('num_occupants', default=1, type=int),
            'room_type' : request.args.get('room_type')
        }
        
        f = QueryForm(data=cleaned_data)
        if f.validate():
            rooms = Room.fetch_room_to_query(cleaned_data)
            session['check_in_date'] =  request.args.get('check_in_date')
            session['check_out_date'] = request.args.get('check_out_date')
            session['num_occupants'] = cleaned_data['num_occupants']
            return render_template('roomSearchResults.html', rooms=rooms)
        return 404

    # displays the details of different rooms
    @app.route('/rooms/<id>')
    def room_detail_page(id):
        room = Room.get_by_id(id)
        return render_template('roomDetail.html', room=room)

    #for user reservation
    @app.route('/rooms/<id>/book', methods=['GET', 'POST'])
    @login_required
    def reserve_room_page(id):
        room = Room.get_by_id(id)

        if request.method == 'POST':
            data = request.form
            reservation = Reservation.create(**data, room_id=id, user_id=current_user.id)
            return redirect(url_for('bookings_page'))

        data = {
            'room': room,
            'check_in_date': session.pop('check_in_date', date.today().strftime("%Y-%m-%d")),
            'check_out_date': session.pop('check_out_date', date.today().strftime("%Y-%m-%d")),
            'num_occupants': session.pop('num_occupants', 1),
        }

        return render_template('reserve.html', **data)

    #Bookings Page
    @app.route('/bookings')
    @login_required
    def bookings_page():
        reservations = Reservation.fetch_users_reservation(current_user.id)
        data = {
            'reservations' : reservations
        }
        return render_template('bookings.html', **data)
    
    #CancelReservation Page
    @app.route('/bookings/<res_id>/cancel')
    @login_required
    def cancel_reservation(res_id):
        """
        res_id: id of reservation the client wants to cancel
        """
        current_user.delete_reservation(res_id)
        return redirect(url_for('bookings_page'))

    @app.route('/contact', methods=['POST'])
    def send_mail():
        sender = current_user.email if current_user.is_authenticated else request.form.get('email', 'Anonymous')
        body="Message from " + sender + ":\n\n" + request.form.get('message', 'No body')
        msg = Message(
            subject=request.form.get('subject', 'No Subject'),
            body=body,
            sender=sender,
            recipients=["hotelcallisto131@gmail.com"]
            )
        mail.send(msg)
        return redirect(url_for('room_list_page'))
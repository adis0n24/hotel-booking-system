from datetime import datetime
from flask import Flask, render_template, request, jsonify
import mysql.connector
from mysql.connector import Error

app = Flask(__name__, template_folder='.', static_folder='.')

db_config = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': 'aditya@2006',
    'database': 'HotelBookingSystem',
    'auth_plugin': 'mysql_native_password'
}

def get_db_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        if conn.is_connected():
            return conn
    except Error as exc:
        print(f"Error connecting to MySQL: {exc}")
    return None


def parse_date(date_string, label):
    if not date_string:
        raise ValueError(f'Missing {label} date.')
    try:
        return datetime.strptime(date_string, '%Y-%m-%d').date()
    except ValueError as exc:
        raise ValueError(f'Invalid {label} date format. Use YYYY-MM-DD.') from exc


# ✅ FIXED availability checker
def is_room_available(cursor, room_id, check_in, check_out):
    query = """
        SELECT COUNT(*) AS overlap_count
        FROM BOOKINGS
        WHERE RoomID = %s
          AND Status != 'Cancelled'
          AND NOT (%s >= CheckOutDate OR %s <= CheckInDate)
    """
    cursor.execute(query, (room_id, check_in, check_out))
    overlap_count = cursor.fetchone()[0]
    return overlap_count == 0


def refresh_room_status(cursor, room_id):
    query = """
        SELECT COUNT(*) 
        FROM BOOKINGS
        WHERE RoomID = %s 
        AND Status = 'Confirmed'
        AND CheckOutDate >= CURDATE()
    """
    cursor.execute(query, (room_id,))
    active_bookings = cursor.fetchone()[0]
    new_status = 'Occupied' if active_bookings else 'Available'
    
    cursor.execute("UPDATE ROOMS SET Status = %s WHERE RoomID = %s", (new_status, room_id))


@app.route('/')
def index():
    return render_template('hotel_frontend.html')


@app.route('/api/rooms', methods=['GET'])
def get_rooms():
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT R.RoomID, RT.TypeName, RT.BasePrice, R.Floor, R.Status
            FROM ROOMS R
            JOIN ROOM_TYPE RT ON R.TypeID = RT.TypeID
            ORDER BY R.RoomID
        """)
        rooms = cursor.fetchall()
        return jsonify(rooms)
    except Error as exc:
        return jsonify({'error': str(exc)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/check-room', methods=['POST'])
def check_room():
    data = request.json or {}
    required = ('roomId', 'checkIn', 'checkOut')

    if not all(field in data for field in required):
        return jsonify({'available': False, 'message': 'Room and dates are required.'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'available': False, 'message': 'Database connection failed.'}), 500

    cursor = conn.cursor()
    try:
        check_in = parse_date(data['checkIn'], 'check-in')
        check_out = parse_date(data['checkOut'], 'check-out')

        if check_in >= check_out:
            return jsonify({'available': False, 'message': 'Check-out must be after check-in.'}), 400

        cursor.execute("SELECT Status FROM ROOMS WHERE RoomID = %s", (data['roomId'],))
        if cursor.fetchone() is None:
            return jsonify({'available': False, 'message': 'Room not found.'}), 404

        available = is_room_available(cursor, data['roomId'], check_in, check_out)
        message = 'Room is available.' if available else 'Room is already booked for the selected dates.'

        return jsonify({'available': available, 'message': message})
    except ValueError as exc:
        return jsonify({'available': False, 'message': str(exc)}), 400
    except Error as exc:
        return jsonify({'available': False, 'message': str(exc)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/book', methods=['POST'])
def make_booking():
    data = request.json or {}
    required = ('customerId', 'roomId', 'staffId', 'checkIn', 'checkOut', 'guests')

    if not all(field in data for field in required):
        return jsonify({'success': False, 'message': 'All booking fields are required.'}), 400

    try:
        check_in = parse_date(data['checkIn'], 'check-in')
        check_out = parse_date(data['checkOut'], 'check-out')

        if check_in >= check_out:
            return jsonify({'success': False, 'message': 'Check-out must be after check-in.'}), 400
    except ValueError as exc:
        return jsonify({'success': False, 'message': str(exc)}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection failed.'}), 500

    cursor = conn.cursor()
    try:
        cursor.execute("SELECT Status FROM ROOMS WHERE RoomID = %s", (data['roomId'],))
        room_row = cursor.fetchone()

        if not room_row:
            return jsonify({'success': False, 'message': 'Room not found.'}), 404

        if room_row[0] == 'Maintenance':
            return jsonify({'success': False, 'message': 'Room is under maintenance.'}), 400

        available = is_room_available(cursor, data['roomId'], check_in, check_out)
        if not available:
            return jsonify({'success': False, 'message': 'Room is already booked for the selected dates.'}), 409

        # ✅ FIXED INSERT QUERY (correct column names)
        insert_query = """
            INSERT INTO BOOKINGS (CustomerID, RoomID, StaffID, CheckInDate, CheckOutDate, NumGuests, Status)
            VALUES (%s, %s, %s, %s, %s, %s, 'Confirmed')
        """

        cursor.execute(insert_query, (
            data['customerId'],
            data['roomId'],
            data['staffId'],
            check_in,
            check_out,
            data['guests']
        ))

        booking_id = cursor.lastrowid
        refresh_room_status(cursor, data['roomId'])
        conn.commit()

        return jsonify({'success': True, 'message': f'Booking confirmed (ID #{booking_id}).'})

    except Error as exc:
        conn.rollback()
        return jsonify({'success': False, 'message': str(exc)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/cancel', methods=['POST'])
def cancel_booking():
    data = request.json or {}
    booking_id = data.get('bookingId')

    if not booking_id:
        return jsonify({'success': False, 'message': 'Booking ID is required.'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection failed.'}), 500

    cursor = conn.cursor()
    try:
        cursor.execute("SELECT RoomID, Status FROM BOOKINGS WHERE BookingID = %s", (booking_id,))
        booking_row = cursor.fetchone()

        if not booking_row:
            return jsonify({'success': False, 'message': 'Booking not found.'}), 404

        room_id, status = booking_row

        if status == 'Cancelled':
            return jsonify({'success': False, 'message': 'Booking is already cancelled.'}), 400

        cursor.execute("UPDATE BOOKINGS SET Status = 'Cancelled' WHERE BookingID = %s", (booking_id,))
        refresh_room_status(cursor, room_id)
        conn.commit()

        return jsonify({'success': True, 'message': f'Booking {booking_id} cancelled successfully.'})
    except Error as exc:
        conn.rollback()
        return jsonify({'success': False, 'message': str(exc)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/report', methods=['GET'])
def generate_report():
    start = request.args.get('start')
    end = request.args.get('end')

    if not start or not end:
        return jsonify({'error': 'Start and end dates are required.'}), 400

    try:
        start_date = parse_date(start, 'start')
        end_date = parse_date(end, 'end')

        if start_date > end_date:
            return jsonify({'error': 'Start date must be on or before end date.'}), 400
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed.'}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        # ✅ FIXED DATEDIFF column names
        report_query = """
            SELECT
                RT.TypeName,
                COUNT(B.BookingID) AS TotalBookings,
                COALESCE(SUM(RT.BasePrice * DATEDIFF(B.CheckOutDate, B.CheckInDate)), 0) AS TotalRevenue
            FROM BOOKINGS B
            JOIN ROOMS R ON B.RoomID = R.RoomID
            JOIN ROOM_TYPE RT ON R.TypeID = RT.TypeID
            WHERE B.Status = 'Confirmed'
              AND B.CheckInDate >= %s
              AND B.CheckOutDate <= %s
            GROUP BY RT.TypeName
            ORDER BY TotalRevenue DESC
        """

        cursor.execute(report_query, (start_date, end_date))
        data = cursor.fetchall()

        return jsonify(data)

    except Error as exc:
        return jsonify({'error': str(exc)}), 500
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    print('Starting Hotel Booking Server on http://127.0.0.1:5000')
    app.run(debug=True, port=5000)

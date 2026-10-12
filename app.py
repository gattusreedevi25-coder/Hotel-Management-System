
import streamlit as st
import sqlite3
from datetime import date

st.set_page_config(
    page_title="Hotel Management System",
    page_icon="🏨",
    layout="wide"
)

DB_NAME = "hotel.db"


# Connect to database and create tables
def initialize_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            room_no INTEGER PRIMARY KEY,
            room_type TEXT NOT NULL,
            price REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            phone TEXT,
            room_no INTEGER,
            check_in TEXT,
            check_out TEXT,
            total REAL,
            status TEXT DEFAULT 'Booked'
        )
    """)

    # Add sample rooms only when the table is empty
    cursor.execute("SELECT COUNT(*) FROM rooms")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO rooms VALUES (?, ?, ?)",
            [
                (101, "Single", 1500),
                (102, "Single", 1500),
                (201, "Double", 2500),
                (202, "Double", 2500),
                (301, "Deluxe", 4000)
            ]
        )

    conn.commit()
    conn.close()


def get_rooms():
    conn = sqlite3.connect(DB_NAME)
    rows = conn.execute(
        "SELECT room_no, room_type, price FROM rooms ORDER BY room_no"
    ).fetchall()
    conn.close()
    return rows


def get_bookings():
    conn = sqlite3.connect(DB_NAME)
    rows = conn.execute("""
        SELECT id, customer_name, phone, room_no,
               check_in, check_out, total, status
        FROM bookings
        ORDER BY id DESC
    """).fetchall()
    conn.close()
    return rows


def get_available_rooms(check_in, check_out):
    rooms = get_rooms()
    bookings = get_bookings()

    available = []
    for room in rooms:
        room_no = room[0]
        occupied = False

        for booking in bookings:
            if booking[3] != room_no:
                continue

            if booking[7] not in ("Booked", "Checked In"):
                continue

            old_in = date.fromisoformat(booking[4])
            old_out = date.fromisoformat(booking[5])

            if check_in < old_out and check_out > old_in:
                occupied = True
                break

        if not occupied:
            available.append(room)

    return available


initialize_database()

st.title("🏨 Hotel Management System")
st.caption("Manage rooms, customers, reservations and billing.")

dashboard, rooms_tab, booking_tab, billing_tab = st.tabs([
    "📊 Dashboard",
    "🛏️ Rooms",
    "📝 Reservations",
    "💳 Billing"
])

# Dashboard
with dashboard:
    bookings = get_bookings()
    rooms = get_rooms()

    total_rooms = len(rooms)
    total_bookings = len(bookings)
    active_bookings = sum(
        1 for b in bookings if b[7] in ("Booked", "Checked In")
    )
    revenue = sum(
        b[6] or 0 for b in bookings
        if b[7] == "Checked Out"
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Rooms", total_rooms)
    c2.metric("Total Bookings", total_bookings)
    c3.metric("Active Bookings", active_bookings)
    c4.metric("Completed Revenue", f"₹{revenue:,.2f}")

    st.subheader("Recent Reservations")
    if bookings:
        st.dataframe(
            [
                {
                    "Booking ID": b[0],
                    "Customer": b[1],
                    "Room": b[3],
                    "Check-in": b[4],
                    "Check-out": b[5],
                    "Amount": f"₹{b[6]:,.2f}",
                    "Status": b[7]
                }
                for b in bookings[:10]
            ],
            use_container_width=True
        )
    else:
        st.info("No reservations yet.")

# Rooms
with rooms_tab:
    st.subheader("Available Hotel Rooms")

    st.dataframe(
        [
            {
                "Room Number": r[0],
                "Room Type": r[1],
                "Price per Night": f"₹{r[2]:,.2f}"
            }
            for r in get_rooms()
        ],
        use_container_width=True
    )

# Reservations
with booking_tab:
    st.subheader("Create a Reservation")

    with st.form("booking_form"):
        customer_name = st.text_input("Customer Name")
        phone = st.text_input("Phone Number")

        col1, col2 = st.columns(2)
        with col1:
            check_in = st.date_input(
                "Check-in Date", value=date.today()
            )
        with col2:
            check_out = st.date_input(
                "Check-out Date",
                value=date.today().fromordinal(date.today().toordinal() + 1)
            )

        submitted = st.form_submit_button("Find Available Rooms")

    if submitted:
        if not customer_name.strip():
            st.error("Please enter the customer name.")
        elif check_in < date.today():
            st.error("Check-in cannot be in the past.")
        elif check_out <= check_in:
            st.error("Check-out must be after check-in.")
        else:
            available = get_available_rooms(check_in, check_out)

            if not available:
                st.warning("No rooms available for these dates.")
            else:
                st.session_state["available_rooms"] = available
                st.session_state["booking_customer"] = customer_name.strip()
                st.session_state["booking_phone"] = phone.strip()
                st.session_state["booking_in"] = check_in.isoformat()
                st.session_state["booking_out"] = check_out.isoformat()
                st.success("Rooms found! Select a room below.")

    if "available_rooms" in st.session_state:
        available = st.session_state["available_rooms"]
        options = {
            f"Room {r[0]} - {r[1]} - ₹{r[2]:,.0f}/night": r
            for r in available
        }

        selected = st.selectbox(
            "Select Room",
            list(options.keys()),
            key="selected_room"
        )
        room = options[selected]
        nights = (
            date.fromisoformat(st.session_state["booking_out"])
            - date.fromisoformat(st.session_state["booking_in"])
        ).days
        total = room[2] * nights

        st.write(f"**Number of nights:** {nights}")
        st.write(f"**Total amount:** ₹{total:,.2f}")

        if st.button("Confirm Booking"):
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()

            # Check availability again before saving
            latest_available = get_available_rooms(
                date.fromisoformat(st.session_state["booking_in"]),
                date.fromisoformat(st.session_state["booking_out"])
            )
            still_available = any(
                r[0] == room[0] for r in latest_available
            )

            if not still_available:
                st.error("This room is no longer available. Search again.")
            else:
                cursor.execute("""
                    INSERT INTO bookings
                    (customer_name, phone, room_no, check_in,
                     check_out, total, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'Booked')
                """, (
                    st.session_state["booking_customer"],
                    st.session_state["booking_phone"],
                    room[0],
                    st.session_state["booking_in"],
                    st.session_state["booking_out"],
                    total
                ))
                conn.commit()
                st.session_state.pop("available_rooms", None)
                conn.close()
                st.success("Booking confirmed successfully!")
                st.rerun()

            if conn:
                conn.close()

    st.divider()
    st.subheader("Manage Reservations")

    bookings = get_bookings()
    if bookings:
        for b in bookings:
            with st.expander(
                f"Booking #{b[0]} — {b[1]} — Room {b[3]} — {b[7]}"
            ):
                st.write(f"Phone: {b[2] or 'Not provided'}")
                st.write(f"Check-in: {b[4]}")
                st.write(f"Check-out: {b[5]}")
                st.write(f"Total: ₹{b[6]:,.2f}")

                if b[7] == "Booked":
                    if st.button("Check In", key=f"in_{b[0]}"):
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute(
                            "UPDATE bookings SET status='Checked In' WHERE id=?",
                            (b[0],)
                        )
                        conn.commit()
                        conn.close()
                        st.rerun()

                    if st.button("Cancel Booking", key=f"cancel_{b[0]}"):
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute(
                            "UPDATE bookings SET status='Cancelled' WHERE id=?",
                            (b[0],)
                        )
                        conn.commit()
                        conn.close()
                        st.rerun()

                elif b[7] == "Checked In":
                    if st.button("Check Out", key=f"out_{b[0]}"):
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute(
                            "UPDATE bookings SET status='Checked Out' WHERE id=?",
                            (b[0],)
                        )
                        conn.commit()
                        conn.close()
                        st.success("Customer checked out.")
                        st.rerun()
    else:
        st.info("No reservations to manage.")

# Billing
with billing_tab:
    st.subheader("Generate Invoice")

    bookings = get_bookings()
    if bookings:
        booking_options = {
            f"Booking #{b[0]} - {b[1]} - Room {b[3]}": b
            for b in bookings
        }

        selected_booking = st.selectbox(
            "Choose a Booking", list(booking_options.keys())
        )
        b = booking_options[selected_booking]

        st.write(f"**Customer:** {b[1]}")
        st.write(f"**Room Number:** {b[3]}")
        st.write(f"**Check-in:** {b[4]}")
        st.write(f"**Check-out:** {b[5]}")
        st.write(f"**Booking Status:** {b[7]}")
        st.subheader(f"Total Amount: ₹{b[6]:,.2f}")

        invoice = f"""
HOTEL MANAGEMENT SYSTEM
-----------------------
Invoice / Booking ID: {b[0]}
Customer Name: {b[1]}
Phone Number: {b[2] or 'Not provided'}
Room Number: {b[3]}
Check-in Date: {b[4]}
Check-out Date: {b[5]}
Total Amount: Rs. {b[6]:.2f}
Status: {b[7]}

Thank you for choosing our hotel!
"""

        st.download_button(
            "Download Invoice",
            data=invoice,
            file_name=f"invoice_{b[0]}.txt",
            mime="text/plain"
        )
    else:
        st.info("Create a reservation first to generate an invoice.")

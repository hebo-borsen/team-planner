import streamlit as st
import mysql.connector
import pandas as pd
from datetime import datetime, timedelta
import os
from io import BytesIO

# Database connection configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'database': os.getenv('DB_NAME', 'vacation_db'),
    'user': os.getenv('DB_USER', 'vacation_user'),
    'password': os.getenv('DB_PASSWORD', 'vacation_pass')
}


def get_db_connection():
    """Create a database connection."""
    return mysql.connector.connect(**DB_CONFIG)


def get_team_members():
    """Fetch all team members from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, emoji FROM team_members ORDER BY name")
    members = cursor.fetchall()
    cursor.close()
    conn.close()
    return members


def add_team_member(name, emoji):
    """Add a new team member."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO team_members (name, emoji) VALUES (%s, %s)",
            (name, emoji)
        )
        conn.commit()
        success = True
        message = "Team member added successfully!"
    except mysql.connector.IntegrityError:
        success = False
        message = "A team member with this name already exists."
    finally:
        cursor.close()
        conn.close()
    return success, message


def delete_team_member(member_id):
    """Delete a team member."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM team_members WHERE id = %s", (member_id,))
    conn.commit()
    cursor.close()
    conn.close()


def add_vacation_day(member_id, vacation_date):
    """Add a single vacation day for a team member."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO vacation_days (member_id, vacation_date) VALUES (%s, %s)",
            (member_id, vacation_date)
        )
        conn.commit()
        success = True
        message = "Vacation day added successfully!"
    except mysql.connector.IntegrityError:
        success = False
        message = "This vacation day already exists."
    finally:
        cursor.close()
        conn.close()
    return success, message


def add_vacation_range(member_id, start_date, end_date):
    """Add a range of vacation days for a team member."""
    conn = get_db_connection()
    cursor = conn.cursor()

    current_date = start_date
    added_count = 0
    skipped_count = 0

    while current_date <= end_date:
        try:
            cursor.execute(
                "INSERT INTO vacation_days (member_id, vacation_date) VALUES (%s, %s)",
                (member_id, current_date)
            )
            added_count += 1
        except mysql.connector.IntegrityError:
            skipped_count += 1

        current_date += timedelta(days=1)

    conn.commit()
    cursor.close()
    conn.close()

    return added_count, skipped_count


def get_all_vacations():
    """Fetch all vacation days with team member names."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            tm.name as member_name,
            vd.vacation_date,
            vd.id
        FROM vacation_days vd
        JOIN team_members tm ON vd.member_id = tm.id
        ORDER BY vd.vacation_date DESC, tm.name
    """)
    vacations = cursor.fetchall()
    cursor.close()
    conn.close()
    return vacations


def get_vacations_for_month(year, month):
    """Fetch all vacation days for a specific month."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            tm.id,
            tm.name as member_name,
            vd.vacation_date
        FROM team_members tm
        LEFT JOIN vacation_days vd ON tm.id = vd.member_id
            AND YEAR(vd.vacation_date) = %s
            AND MONTH(vd.vacation_date) = %s
        ORDER BY tm.name, vd.vacation_date
    """, (year, month))
    vacations = cursor.fetchall()
    cursor.close()
    conn.close()
    return vacations


def delete_vacation(vacation_id):
    """Delete a vacation day."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vacation_days WHERE id = %s", (vacation_id,))
    conn.commit()
    cursor.close()
    conn.close()


def add_holiday(holiday_date, holiday_name):
    """Add a holiday."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO holidays (holiday_date, holiday_name) VALUES (%s, %s)",
            (holiday_date, holiday_name)
        )
        conn.commit()
        success = True
        message = "Holiday added successfully!"
    except mysql.connector.IntegrityError:
        success = False
        message = "This holiday date already exists."
    finally:
        cursor.close()
        conn.close()
    return success, message


def add_holiday_range(start_date, end_date, holiday_name):
    """Add a range of holiday days."""
    conn = get_db_connection()
    cursor = conn.cursor()

    current_date = start_date
    added_count = 0
    skipped_count = 0

    while current_date <= end_date:
        try:
            cursor.execute(
                "INSERT INTO holidays (holiday_date, holiday_name) VALUES (%s, %s)",
                (current_date, holiday_name)
            )
            added_count += 1
        except mysql.connector.IntegrityError:
            skipped_count += 1

        current_date += timedelta(days=1)

    conn.commit()
    cursor.close()
    conn.close()

    return added_count, skipped_count


def get_holidays_for_month(year, month):
    """Fetch all holidays for a specific month."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT holiday_date, holiday_name, id
        FROM holidays
        WHERE YEAR(holiday_date) = %s AND MONTH(holiday_date) = %s
        ORDER BY holiday_date
    """, (year, month))
    holidays = cursor.fetchall()
    cursor.close()
    conn.close()
    return holidays


def get_all_holidays():
    """Fetch all holidays."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT holiday_date, holiday_name, id
        FROM holidays
        ORDER BY holiday_date DESC
    """)
    holidays = cursor.fetchall()
    cursor.close()
    conn.close()
    return holidays


def delete_holiday(holiday_id):
    """Delete a holiday."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM holidays WHERE id = %s", (holiday_id,))
    conn.commit()
    cursor.close()
    conn.close()


def create_event(event_name):
    """Create a new event."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO events (event_name) VALUES (%s)",
            (event_name,)
        )
        conn.commit()
        success = True
        message = "Event created successfully!"
    except mysql.connector.Error as e:
        success = False
        message = f"Error creating event: {str(e)}"
    finally:
        cursor.close()
        conn.close()
    return success, message


def get_all_events():
    """Fetch all events."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, event_name, created_at
        FROM events
        ORDER BY created_at DESC
    """)
    events = cursor.fetchall()
    cursor.close()
    conn.close()
    return events


def delete_event(event_id):
    """Delete an event."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM events WHERE id = %s", (event_id,))
    conn.commit()
    cursor.close()
    conn.close()


def set_event_response(event_id, member_id, is_attending):
    """Set or update a team member's response to an event."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO event_responses (event_id, member_id, is_attending)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE is_attending = %s
        """, (event_id, member_id, is_attending, is_attending))
        conn.commit()
        success = True
    except mysql.connector.Error as e:
        success = False
        print(f"Error setting event response: {str(e)}")
    finally:
        cursor.close()
        conn.close()
    return success


def get_event_responses(event_id):
    """Get all responses for an event."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            tm.id as member_id,
            tm.name as member_name,
            tm.emoji as member_emoji,
            er.is_attending
        FROM team_members tm
        LEFT JOIN event_responses er ON tm.id = er.member_id AND er.event_id = %s
        ORDER BY tm.name
    """, (event_id,))
    responses = cursor.fetchall()
    cursor.close()
    conn.close()
    return responses


def export_to_excel(df):
    """Export DataFrame to Excel file."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Vacations')
    output.seek(0)
    return output


# Streamlit UI
st.set_page_config(page_title="Team Vacation Planner", page_icon="🏖️", layout="wide")

st.title("🏖️ Team Vacation Planner")

# Sidebar for adding vacations
st.sidebar.header("Add Vacation")

# Get team members
members = get_team_members()
member_dict = {f"{emoji} {name}": id for id, name, emoji in members}
member_names = list(member_dict.keys())

if not member_names:
    st.sidebar.error("No team members found. Please add team members below.")
else:
    selected_member = st.sidebar.selectbox("Select Team Member", member_names)
    member_id = member_dict[selected_member]

    # Tab for single day or date range
    vacation_type = st.sidebar.radio("Vacation Type", ["Single Day", "Date Range"])

    if vacation_type == "Single Day":
        vacation_date = st.sidebar.date_input("Select Date")

        if st.sidebar.button("Add Vacation Day"):
            success, message = add_vacation_day(member_id, vacation_date)
            if success:
                st.sidebar.success(message)
                st.rerun()
            else:
                st.sidebar.warning(message)

    else:  # Date Range
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_date = st.date_input("Start Date")
        with col2:
            end_date = st.date_input("End Date")

        if st.sidebar.button("Add Vacation Range"):
            if start_date <= end_date:
                added, skipped = add_vacation_range(member_id, start_date, end_date)
                if added > 0:
                    st.sidebar.success(f"Added {added} vacation day(s)!")
                if skipped > 0:
                    st.sidebar.info(f"Skipped {skipped} duplicate day(s).")
                st.rerun()
            else:
                st.sidebar.error("End date must be after start date.")

# Footer
st.sidebar.markdown("---")
st.sidebar.info("💡 Tip: Use date range to quickly add multiple consecutive vacation days.")

# Main content - Tabs
tab1, tab2, tab3, tab4 = st.tabs(["📅 Calendar", "🎉 Holidays", "👥 Team Members", "🎪 Event Planning"])

# Tab 1: Calendar View
with tab1:
    st.header("Vacation Calendar")

    # Month/Year selector
    col1, col2 = st.columns([1, 3])
    with col1:
        selected_month = st.selectbox(
            "Select Month",
            range(1, 13),
            index=datetime.now().month - 1,
            format_func=lambda x: datetime(2000, x, 1).strftime('%B')
        )
    with col2:
        selected_year = st.selectbox(
            "Select Year",
            range(datetime.now().year - 1, datetime.now().year + 3),
            index=1
        )

    # Get vacations and holidays for selected month
    vacations_data = get_vacations_for_month(selected_year, selected_month)
    holidays_data = get_holidays_for_month(selected_year, selected_month)

    if not members:
        st.info("No team members found.")
    else:
        # Calculate days in month
        import calendar
        days_in_month = calendar.monthrange(selected_year, selected_month)[1]

        # Create holidays data structure
        holiday_days = {}
        for holiday_date, holiday_name, holiday_id in holidays_data:
            holiday_days[holiday_date.day] = holiday_name

        # Create calendar data structure for vacations
        vacation_dict = {}
        for member_id, member_name, vacation_date in vacations_data:
            if member_name not in vacation_dict:
                vacation_dict[member_name] = set()
            if vacation_date:
                vacation_dict[member_name].add(vacation_date.day)

        # Build calendar DataFrame
        calendar_data = []

        # First row: Holidays
        holiday_row = {'Team Member': '🎉 Holidays'}
        for day in range(1, days_in_month + 1):
            holiday_row[str(day)] = 'H' if day in holiday_days else ''
        calendar_data.append(holiday_row)

        # Team member rows
        for member_id, member_name, member_emoji in members:
            row = {'Team Member': f"{member_emoji} {member_name}"}
            member_vacations = vacation_dict.get(member_name, set())
            for day in range(1, days_in_month + 1):
                row[str(day)] = 'V' if day in member_vacations else ''
            calendar_data.append(row)

        calendar_df = pd.DataFrame(calendar_data)

        # Determine which days are weekends
        weekend_days = set()
        for day in range(1, days_in_month + 1):
            date = datetime(selected_year, selected_month, day)
            if date.weekday() in [5, 6]:  # Saturday = 5, Sunday = 6
                weekend_days.add(day)

        # Style the dataframe - weekends always grey, then holidays green, vacation days blue
        def highlight_cells(val, day):
            if day in weekend_days:
                return 'background-color: #E8E8E8'
            elif val == 'H':
                return 'background-color: #4CAF50; color: white; font-weight: bold'
            elif val == 'V':
                return 'background-color: #4A90E2; color: white; font-weight: bold'
            return ''

        styled_df = calendar_df.style
        for day in range(1, days_in_month + 1):
            styled_df = styled_df.applymap(lambda val, d=day: highlight_cells(val, d), subset=[str(day)])

        # Display calendar
        st.dataframe(
            styled_df,
            use_container_width=True,
            hide_index=True,
            height=400
        )

        # Export functionality
        st.markdown("---")

        # Get all vacations for export
        all_vacations = get_all_vacations()
        if all_vacations:
            export_df = pd.DataFrame(all_vacations, columns=['Team Member', 'Vacation Date', 'ID'])
            export_df = export_df[['Team Member', 'Vacation Date']].copy()
            export_df['Vacation Date'] = pd.to_datetime(export_df['Vacation Date']).dt.strftime('%Y-%m-%d')

            excel_file = export_to_excel(export_df)
            st.download_button(
                label="📥 Export All Vacations to Excel",
                data=excel_file,
                file_name=f"team_vacations_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            st.write(f"**Total vacation days across all months:** {len(all_vacations)}")

        # Optional: Delete vacation days
        if all_vacations:
            with st.expander("Delete Vacation Day"):
                st.write("Select a vacation day to delete:")
                delete_options = [f"{row[0]} - {row[1]}" for row in all_vacations]
                vacation_to_delete = st.selectbox("Vacation Day", delete_options)

                if st.button("Delete Selected Vacation"):
                    vacation_index = delete_options.index(vacation_to_delete)
                    vacation_id = all_vacations[vacation_index][2]
                    delete_vacation(vacation_id)
                    st.success("Vacation day deleted!")
                    st.rerun()

# Tab 2: Holidays Management
with tab2:
    st.header("Manage Holidays")

    # Add holiday section
    st.subheader("Add Holiday")
    holiday_name = st.text_input("Holiday Name", placeholder="e.g., Christmas", key="holiday_name")
    holiday_type = st.radio("Holiday Type", ["Single Day", "Date Range"], key="holiday_type")

    if holiday_type == "Single Day":
        holiday_date = st.date_input("Holiday Date", key="holiday_date")

        if st.button("Add Holiday"):
            if holiday_name:
                success, message = add_holiday(holiday_date, holiday_name)
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.warning(message)
            else:
                st.error("Please enter a holiday name.")

    else:  # Date Range
        col1, col2 = st.columns(2)
        with col1:
            holiday_start_date = st.date_input("Start Date", key="holiday_start")
        with col2:
            holiday_end_date = st.date_input("End Date", key="holiday_end")

        if st.button("Add Holiday Range"):
            if holiday_name:
                if holiday_start_date <= holiday_end_date:
                    added, skipped = add_holiday_range(holiday_start_date, holiday_end_date, holiday_name)
                    if added > 0:
                        st.success(f"Added {added} holiday day(s)!")
                    if skipped > 0:
                        st.info(f"Skipped {skipped} duplicate day(s).")
                    st.rerun()
                else:
                    st.error("End date must be after start date.")
            else:
                st.error("Please enter a holiday name.")

    # Delete holidays section
    st.markdown("---")
    st.subheader("Delete Holidays")
    all_holidays = get_all_holidays()
    if all_holidays:
        st.write("Select a holiday to delete:")
        holiday_delete_options = [f"{row[1]} - {row[0]}" for row in all_holidays]
        holiday_to_delete = st.selectbox("Holiday", holiday_delete_options, key="tab2_holiday")

        if st.button("Delete Selected Holiday", key="tab2_delete_holiday"):
            holiday_index = holiday_delete_options.index(holiday_to_delete)
            holiday_id = all_holidays[holiday_index][2]
            delete_holiday(holiday_id)
            st.success("Holiday deleted!")
            st.rerun()
    else:
        st.info("No holidays added yet.")

# Tab 3: Team Members Management
with tab3:
    st.header("Manage Team Members")

    # Add team member section
    st.subheader("Add Team Member")
    new_member_name = st.text_input("Member Name", placeholder="e.g., John Doe", key="new_member_name")

    # Emoji selection
    emoji_options = [
        "👤", "👨", "👩", "👨‍💼", "👩‍💼", "👨‍💻", "👩‍💻", "👨‍🎨", "👩‍🎨",
        "👨‍🔬", "👩‍🔬", "👨‍🏫", "👩‍🏫", "👨‍⚕️", "👩‍⚕️", "👨‍🎓", "👩‍🎓",
        "🚀", "⭐", "💼", "💻", "🎨", "🔬", "📊", "🎯", "🏆", "💡",
        "🌟", "🔥", "⚡", "🎪", "🎭", "🎬", "🎮", "🎸", "🎵", "⚽",
        "🏀", "🎾", "🏐", "🏈", "⚾", "🎳", "🏓", "🥊", "🎿", "🏂"
    ]

    new_member_emoji = st.selectbox(
        "Select Emoji",
        emoji_options,
        format_func=lambda x: f"{x}",
        key="new_member_emoji"
    )

    if st.button("Add Team Member"):
        if new_member_name and new_member_emoji:
            success, message = add_team_member(new_member_name, new_member_emoji)
            if success:
                st.success(message)
                st.rerun()
            else:
                st.warning(message)
        else:
            st.error("Please enter a name.")

    # Delete team member section
    st.markdown("---")
    st.subheader("Delete Team Member")
    if members:
        st.write("Select a team member to delete:")
        delete_member_options = [f"{emoji} {name}" for id, name, emoji in members]
        member_to_delete = st.selectbox("Team Member", delete_member_options, key="tab3_delete_member")

        if st.button("Delete Team Member", key="tab3_delete_member_btn"):
            member_index = delete_member_options.index(member_to_delete)
            member_id_to_delete = members[member_index][0]
            delete_team_member(member_id_to_delete)
            st.success("Team member deleted!")
            st.rerun()
    else:
        st.info("No team members found.")

# Tab 4: Event Planning
with tab4:
    st.header("Event Planning")

    # Add event section
    st.subheader("Create Event")
    event_name_input = st.text_input("Event Name", placeholder="e.g., Team Dinner, Sprint Planning", key="event_name")

    if st.button("Create Event"):
        if event_name_input:
            success, message = create_event(event_name_input)
            if success:
                st.success(message)
                st.rerun()
            else:
                st.error(message)
        else:
            st.error("Please enter an event name.")

    st.markdown("---")

    # Display events and responses
    st.subheader("Events")
    all_events = get_all_events()

    if not all_events:
        st.info("No events created yet.")
    else:
        for event_id, event_name, created_at in all_events:
            with st.expander(f"📌 {event_name}", expanded=True):
                st.write(f"**Created:** {created_at.strftime('%Y-%m-%d %H:%M')}")

                # Get responses for this event
                responses = get_event_responses(event_id)

                if not responses:
                    st.info("No team members found.")
                else:
                    st.write("**Team Member Responses:**")

                    # Display each team member with checkbox
                    for member_id, member_name, member_emoji, is_attending in responses:
                        col1, col2 = st.columns([3, 1])

                        with col1:
                            # Create a unique key for each checkbox
                            checkbox_key = f"event_{event_id}_member_{member_id}"
                            current_value = is_attending if is_attending is not None else False

                            is_going = st.checkbox(
                                f"{member_emoji} {member_name}",
                                value=current_value,
                                key=checkbox_key
                            )

                            # Update response if changed
                            if is_going != current_value:
                                set_event_response(event_id, member_id, is_going)
                                st.rerun()

                        with col2:
                            if is_attending:
                                st.write("✅ Going")
                            elif is_attending is False:
                                st.write("❌ Not going")
                            else:
                                st.write("⚪ No response")

                st.markdown("---")

                # Delete event button
                if st.button(f"Delete Event", key=f"delete_event_{event_id}"):
                    delete_event(event_id)
                    st.success("Event deleted!")
                    st.rerun()

import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure the root project directory is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Conversion functions with `None` handling
def hms_to_decimal_hours(hms: str) -> float:
    """Convert HH:MM:SS.s format to decimal hours, but only if needed."""
    if hms is None or hms.strip() == "":  # Handle None or empty strings
        return None
    if ":" not in hms:  # Already converted
        return float(hms)
    
    hours, minutes, seconds = map(float, hms.split(':'))
    return hours + minutes / 60 + seconds / 3600

def dms_to_decimal_degrees(dms: str) -> float:
    """Convert ±DD:MM:SS.s format to decimal degrees, but only if needed."""
    if dms is None or dms.strip() == "":  # Handle None or empty strings
        return None
    if ":" not in dms:  # Already converted
        return float(dms)
    
    sign = 1 if dms[0] == '+' else -1  # Determine if positive or negative
    dms = dms[1:] if dms[0] in '+-' else dms  # Remove sign for processing
    degrees, minutes, seconds = map(float, dms.split(':'))
    
    return sign * (degrees + minutes / 60 + seconds / 3600)

# Set up database session
engine = create_engine('sqlite:///Data.db')  # Adjust if necessary
Session = sessionmaker(bind=engine)
session = Session()

def update_ngc_table():
    """Update NGCtable with converted RA and Dec values only if needed."""
    from models.tables import NGCtable  # Import inside function to avoid circular import

    for record in session.query(NGCtable).all():
        # Convert only if not None
        new_ra = hms_to_decimal_hours(record.RA)
        new_dec = dms_to_decimal_degrees(record.Dec)

        if new_ra is not None and str(new_ra) != record.RA:
            print(f"Updating {record.Name}: RA {record.RA} -> {new_ra}")
            record.RA = str(new_ra)
        if new_dec is not None and str(new_dec) != record.Dec:
            print(f"Updating {record.Name}: Dec {record.Dec} -> {new_dec}")
            record.Dec = str(new_dec)

    session.commit()

def update_index_table():
    """Update IndexTable with converted RA and Dec values only if needed."""
    from models.tables import IndexTable  # Import inside function to avoid circular import

    for record in session.query(IndexTable).all():
        # Convert only if not None
        new_ra = hms_to_decimal_hours(record.RA)
        new_dec = dms_to_decimal_degrees(record.DEC)

        if new_ra is not None and str(new_ra) != record.RA:
            print(f"Updating {record.Name}: RA {record.RA} -> {new_ra}")
            record.RA = str(new_ra)
        if new_dec is not None and str(new_dec) != record.DEC:
            print(f"Updating {record.Name}: Dec {record.DEC} -> {new_dec}")
            record.DEC = str(new_dec)

    session.commit()

# Run both update functions
update_ngc_table()
update_index_table()

# Close the session
session.close()

from db import db
from sqlalchemy import Table, MetaData, Column, String, REAL

def get_app():
    from Server import app
    return app

# Base class for reflection to be inherited by all models
class BaseTable(db.Model):

    __abstract__ = True  # This class is not directly mapped to a table

    @classmethod
    def get_all_fields(cls):
        return {column.name: getattr(cls, column.name) for column in cls.__table__.columns}

    @classmethod
    def reflect_table(cls):
        app = get_app()  # Get app inside the function
        with app.app_context():
            cls.__table__ = Table(cls.__tablename__, db.metadata, autoload_with=db.engine)


    @classmethod
    def __init_subclass__(cls):
        super().__init_subclass__()
        cls.reflect_table()


# HDSTARtable: Define columns dynamically using reflection
class HDSTARtable(BaseTable):
    __tablename__ = 'HDSTARTable'  # The actual table name in the database

    @staticmethod
    def query_by_name(name):
        print(f"Querying HDSTARtable for name: {name}")
        result = db.session.query(HDSTARtable).filter_by(Name=name).first()
        if result:
            if isinstance(result, dict):
                return result
            result_data = {column: getattr(result, column) for column in result.__table__.columns.keys()}
            return result_data
        return None


# IndexTable: Define columns dynamically using reflection
class IndexTable(BaseTable):
    __tablename__ = 'IndexTable'

    @staticmethod
    def query_by_name(name):
        print(f"Querying IndexTable for name: {name}")
        result = db.session.query(IndexTable).filter_by(Name=name).first()
        if result:
            if isinstance(result, dict):
                return result
            result_data = {column: getattr(result, column) for column in result.__table__.columns.keys()}
            return result_data
        return None


# NGCtable: Define columns dynamically using reflection
class NGCtable(BaseTable):
    __tablename__ = 'NGCtable'

    @staticmethod
    def query_by_name(name):
        print(f"Querying NGCtable for name: {name}")
        result = db.session.query(NGCtable).filter_by(Name=name).first()
        if result:
            if isinstance(result, dict):
                return result
            result_data = {column: getattr(result, column) for column in result.__table__.columns.keys()}
            return result_data
        return None

    @staticmethod
    def query_by_messier(messier_designation):
        """
        Query NGCtable by Messier designation (e.g., 'M1', 'M31', 'M104')
        """
        print(f"Querying NGCtable for Messier: {messier_designation}")
        result = db.session.query(NGCtable).filter_by(Messier=messier_designation).first()
        if result:
            if isinstance(result, dict):
                return result
            result_data = {column: getattr(result, column) for column in result.__table__.columns.keys()}
            return result_data
        return None

    @staticmethod
    def query_by_messier(messier_designation):
        """
        Query NGCtable by Messier designation (e.g., 'M1', 'M31', 'M104')
        """
        print(f"Querying NGCtable for Messier: {messier_designation}")
        result = db.session.query(NGCtable).filter_by(Messier=messier_designation).first()
        if result:
            if isinstance(result, dict):
                return result
            result_data = {column: getattr(result, column) for column in result.__table__.columns.keys()}
            return result_data
        return None

    @staticmethod
    def query_by_common_name(common_name):
        """
        Query NGCtable by common name using case-insensitive exact matching
        """
        print(f"Querying NGCtable for common name: {common_name}")
        # Use ilike for case-insensitive exact matching
        result = db.session.query(NGCtable).filter(
            NGCtable.__table__.c['Common names'].ilike(common_name)
        ).first()
        if result:
            if isinstance(result, dict):
                return result
            result_data = {column: getattr(result, column) for column in result.__table__.columns.keys()}
            return result_data
        return None


# PlanetsTable: Define columns dynamically using reflection
class PlanetsTable(BaseTable):
    __tablename__ = 'PlanetsTable'  # The actual table name in the database

    @staticmethod
    def query_by_name(name):
        print(f"Querying PlanetsTable for name: {name}")
        result = db.session.query(PlanetsTable).filter_by(Name=name).first()
        if result:
            if isinstance(result, dict):
                return result
            result_data = {column: getattr(result, column) for column in result.__table__.columns.keys()}
            return result_data
        return None

    @staticmethod
    def load_planets():
        """
        Load all planets into a dictionary for easy access by name.
        """
        planets = db.session.query(PlanetsTable).all()
        return {row.name.lower(): row for row in planets if hasattr(row, 'name')}  # Assuming 'name' is a column


# Telescope model: For managing connected telescopes
class Telescope(BaseTable):
    __tablename__ = 'telescopes'  # The actual table name in the database
    
    @staticmethod
    def get_all_telescopes():
        """
        Get all telescopes from the database.
        """
        telescopes = db.session.query(Telescope).all()
        return telescopes
    
    @staticmethod
    def get_telescope_by_id(telescope_id):
        """
        Get a specific telescope by its telescopeId.
        """
        result = db.session.query(Telescope).filter_by(telescopeId=telescope_id).first()
        if result:
            if isinstance(result, dict):
                return result
            result_data = {column: getattr(result, column) for column in result.__table__.columns.keys()}
            return result_data
        return None
    
    @staticmethod
    def is_telescope_online(telescope_id):
        """
        Check if a telescope is considered online (seen within last 5 minutes).
        """
        import time
        current_time = time.time()
        telescope = db.session.query(Telescope).filter_by(telescopeId=telescope_id).first()
        if telescope and hasattr(telescope, 'lastSeen'):
            # Consider telescope online if seen within last 5 minutes (300 seconds)
            return (current_time - telescope.lastSeen) < 300
        return False
    
    @staticmethod
    def add_telescope(telescope_id, ip_address, firmware_version, capabilities, last_seen=None):
        """
        Add a new telescope to the database.
        
        Args:
            telescope_id (str): Unique identifier for the telescope
            ip_address (str): IP address of the telescope
            firmware_version (str): Firmware version of the telescope
            capabilities (str): Comma-separated list of telescope capabilities
            last_seen (float, optional): Unix timestamp of last contact. Defaults to current time.
        
        Returns:
            dict: Success/error status and message
        """
        try:
            import time
            if last_seen is None:
                last_seen = time.time()
            
            # Check if telescope already exists
            existing = db.session.query(Telescope).filter_by(telescopeId=telescope_id).first()
            if existing:
                return {"status": "error", "message": f"Telescope with ID '{telescope_id}' already exists"}
            
            # Use raw SQL to insert since we're using table reflection
            from sqlalchemy import text
            db.session.execute(
                text("INSERT INTO telescopes (telescopeId, ipAddress, firmwareVersion, capabilities, lastSeen) "
                     "VALUES (:telescopeId, :ipAddress, :firmwareVersion, :capabilities, :lastSeen)"),
                {
                    'telescopeId': telescope_id,
                    'ipAddress': ip_address,
                    'firmwareVersion': firmware_version,
                    'capabilities': capabilities,
                    'lastSeen': last_seen
                }
            )
            db.session.commit()
            
            return {"status": "success", "message": f"Telescope '{telescope_id}' added successfully"}
            
        except Exception as e:
            db.session.rollback()
            return {"status": "error", "message": f"Failed to add telescope: {str(e)}"}
    
    @staticmethod
    def remove_telescope(telescope_id):
        """
        Remove a telescope from the database by telescope ID.
        
        Args:
            telescope_id (str): The telescope ID to remove
        
        Returns:
            dict: Success/error status and message
        """
        try:
            # Check if telescope exists
            telescope = db.session.query(Telescope).filter_by(telescopeId=telescope_id).first()
            if not telescope:
                return {"status": "error", "message": f"Telescope with ID '{telescope_id}' not found"}
            
            # Delete the telescope
            db.session.delete(telescope)
            db.session.commit()
            
            return {"status": "success", "message": f"Telescope '{telescope_id}' removed successfully"}
            
        except Exception as e:
            db.session.rollback()
            return {"status": "error", "message": f"Failed to remove telescope: {str(e)}"}
    
    @staticmethod
    def update_last_seen(telescope_id, last_seen=None):
        """
        Update the last seen timestamp for a telescope.
        
        Args:
            telescope_id (str): The telescope ID to update
            last_seen (float, optional): Unix timestamp. Defaults to current time.
        
        Returns:
            dict: Success/error status and message
        """
        try:
            import time
            if last_seen is None:
                last_seen = time.time()
            
            # Use raw SQL to update since we're using table reflection
            from sqlalchemy import text
            result = db.session.execute(
                text("UPDATE telescopes SET lastSeen = :lastSeen WHERE telescopeId = :telescopeId"),
                {'lastSeen': last_seen, 'telescopeId': telescope_id}
            )
            
            if result.rowcount == 0:
                return {"status": "error", "message": f"Telescope with ID '{telescope_id}' not found"}
            
            db.session.commit()
            return {"status": "success", "message": f"Updated last seen for telescope '{telescope_id}'"}
            
        except Exception as e:
            db.session.rollback()
            return {"status": "error", "message": f"Failed to update telescope: {str(e)}"}

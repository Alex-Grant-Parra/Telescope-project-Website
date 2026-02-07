from app.db import db
import logging

logger = logging.getLogger(__name__)
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

    @staticmethod
    def query_by_name_flexible(name_or_hd: str):
        """
        Query HDSTARtable matching HD name case/space-insensitively.
        Examples accepted: "HD48915", "hd48915", "HD 48915".
        Also tries exact Name match for non-HD inputs.
        Returns a dict of row data or None.
        """
        try:
            from sqlalchemy import text
            # Normalize: remove spaces and uppercase for comparison
            norm = (name_or_hd or "").strip().replace(" ", "").upper()
            # If it looks like an HD pattern without prefix, leave as-is for exact fallthrough
            if norm.startswith("HD"):
                stmt = text(
                    "SELECT * FROM HDSTARTable WHERE REPLACE(UPPER(Name),' ', '') = :norm LIMIT 1"
                )
                row = db.session.execute(stmt, {"norm": norm}).mappings().first()
                if row:
                    return dict(row)
            # Fallback: try exact Name (case-sensitive as stored)
            result = db.session.query(HDSTARtable).filter_by(Name=name_or_hd).first()
            if result:
                return {column: getattr(result, column) for column in result.__table__.columns.keys()}
        except Exception as e:
            logger.error(f"query_by_name_flexible failed: {e}")
        return None

    @staticmethod
    def query_by_common_name(common_name: str):
        """
        Query HDSTARtable by commonNames column using case-insensitive substring match.
        Requires the 'commonNames' column to exist; returns dict or None.
        """
        try:
            col_map = getattr(HDSTARtable, "__table__").c
            if 'commonNames' not in col_map:
                return None
            # Use ilike for case-insensitive match on the comma-separated names list
            result = db.session.query(HDSTARtable).filter(
                col_map['commonNames'].ilike(f"%{common_name}%")
            ).first()
            if result:
                if isinstance(result, dict):
                    return result
                return {column: getattr(result, column) for column in result.__table__.columns.keys()}
        except Exception as e:
            logger.error(f"query_by_common_name failed: {e}")
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
        logger.debug(f"Querying PlanetsTable for name: {name}")
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
class Telescope(db.Model):
    __tablename__ = 'telescopes'
    __table_args__ = {'extend_existing': True}
    
    # Explicit column definitions
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    telescope_id = db.Column(db.String(255), unique=True, nullable=False, index=True)
    ip_address = db.Column(db.String(45), nullable=True)  # IPv4 or IPv6
    type = db.Column(db.String(100), nullable=True)
    last_seen = db.Column(db.Float, nullable=True)  # Unix timestamp
    
    def __repr__(self):
        return f"<Telescope(id={self.id}, telescope_id='{self.telescope_id}', type='{self.type}')>"
    
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
        Get a specific telescope by its telescope_id (human-readable name).
        """
        result = db.session.query(Telescope).filter_by(telescope_id=telescope_id).first()
        if result:
            return {
                'id': result.id,
                'telescope_id': result.telescope_id,
                'ip_address': result.ip_address,
                'type': result.type,
                'last_seen': result.last_seen
            }
        return None
    
    @staticmethod
    def is_telescope_online(telescope_id):
        """
        Check if a telescope is considered online (seen within last 5 minutes).
        """
        import time
        current_time = time.time()
        telescope = db.session.query(Telescope).filter_by(telescope_id=telescope_id).first()
        if telescope and telescope.last_seen:
            # Consider telescope online if seen within last 5 minutes (300 seconds)
            return (current_time - telescope.last_seen) < 300
        return False
    
    @staticmethod
    def add_telescope(telescope_id, ip_address=None, telescope_type=None, last_seen=None):
        """
        Add a new telescope to the database.
        
        Args:
            telescope_id (str): Unique identifier for the telescope (name)
            ip_address (str, optional): IP address of the telescope
            telescope_type (str, optional): Client type (telescope/observer)
            last_seen (float, optional): Unix timestamp of last contact. Defaults to current time.
        
        Returns:
            dict: Success/error status and message
        """
        try:
            import time
            if last_seen is None:
                last_seen = time.time()
            
            # Check if telescope already exists
            existing = db.session.query(Telescope).filter_by(telescope_id=telescope_id).first()
            if existing:
                return {"status": "error", "message": f"Telescope with ID '{telescope_id}' already exists"}
            
            # Create new telescope instance
            new_telescope = Telescope(
                telescope_id=telescope_id,
                ip_address=ip_address,
                type=telescope_type or "telescope",
                last_seen=last_seen
            )
            
            db.session.add(new_telescope)
            db.session.commit()
            
            return {"status": "success", "message": f"Telescope '{telescope_id}' added successfully", "id": new_telescope.id}
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to add telescope: {str(e)}")
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
            telescope = db.session.query(Telescope).filter_by(telescope_id=telescope_id).first()
            if not telescope:
                return {"status": "error", "message": f"Telescope with ID '{telescope_id}' not found"}
            
            # Delete the telescope
            db.session.delete(telescope)
            db.session.commit()
            
            return {"status": "success", "message": f"Telescope '{telescope_id}' removed successfully"}
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to remove telescope: {str(e)}")
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
            
            telescope = db.session.query(Telescope).filter_by(telescope_id=telescope_id).first()
            
            if not telescope:
                return {"status": "error", "message": f"Telescope with ID '{telescope_id}' not found"}
            
            telescope.last_seen = last_seen
            db.session.commit()
            
            return {"status": "success", "message": f"Updated last seen for telescope '{telescope_id}'"}
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to update telescope: {str(e)}")
            return {"status": "error", "message": f"Failed to update telescope: {str(e)}"}
    
    @staticmethod
    def update_ip_address(telescope_id, ip_address):
        """
        Update the IP address for a telescope.
        
        Args:
            telescope_id (str): The telescope ID to update
            ip_address (str): New IP address
        
        Returns:
            dict: Success/error status and message
        """
        try:
            telescope = db.session.query(Telescope).filter_by(telescope_id=telescope_id).first()
            
            if not telescope:
                return {"status": "error", "message": f"Telescope with ID '{telescope_id}' not found"}
            
            telescope.ip_address = ip_address
            db.session.commit()
            
            return {"status": "success", "message": f"Updated IP address for telescope '{telescope_id}'"}
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to update telescope IP: {str(e)}")
            return {"status": "error", "message": f"Failed to update telescope: {str(e)}"}

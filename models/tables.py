from db import db
from sqlalchemy import Table, MetaData, Column, String, REAL
from Server import app  # Adjust the import path based on where your Flask app is defined

# Base class for reflection to be inherited by all models
class BaseTable(db.Model):
    __abstract__ = True  # This class is not directly mapped to a table

    @classmethod
    def get_all_fields(cls):
        """
        Dynamically get all column names and values for the model's table.
        """
        return {column.name: getattr(cls, column.name) for column in cls.__table__.columns}

    @classmethod
    def get_primary_key(cls):
        """
        Dynamically get the primary key column(s) for the model's table.
        """
        primary_key_columns = cls.__table__.primary_key
        return [column.name for column in primary_key_columns]

    @classmethod
    def reflect_table(cls):
        """
        Reflect the table schema from the database and add it to the class.
        """
        # Ensure we're in the application context before proceeding
        with app.app_context():  # Make sure the app context is available for reflection
            # Reflect the table schema from the database
            cls.__table__ = Table(cls.__tablename__, db.metadata, autoload_with=db.engine)

            # SQLAlchemy handles columns automatically after reflection
            # We don't need to manually add columns here. Reflection already handles this.

    @classmethod
    def __init_subclass__(cls):
        """ 
        This method will be automatically called when a subclass of BaseTable is defined. 
        This ensures reflection happens for each subclass **after** the app context is initialized.
        """
        super().__init_subclass__()  # Call the parent class's method (if it exists)
        # Delay reflection until application context is available
        cls.reflect_table()  # Trigger reflection for each subclass


# HDSTARtable: Define columns dynamically using reflection
class HDSTARtable(BaseTable):
    __tablename__ = 'HDSTARTable'  # The actual table name is 'HDSTARTable'

    # Do NOT manually define 'Name' again. Reflection will handle this automatically.

    @staticmethod
    def query_by_name(name):
        print(f"Querying HDSTARtable for name: {name}")

        # Get the primary key dynamically
        primary_key = HDSTARtable.get_primary_key()
        print(f"Primary Key: {primary_key}")  # This will print ['Name'] if 'Name' is the primary key

        result = db.session.query(HDSTARtable).filter_by(Name=name).first()
        if result:
            # Use get_all_fields method to get all columns dynamically
            result_data = {column: getattr(result, column) for column in result.__table__.columns.keys()}
            return result_data
        return None


# IndexTable: Define columns dynamically using reflection
class IndexTable(BaseTable):
    __tablename__ = 'IndexTable'

    # Reflect and add columns dynamically (called automatically via __init_subclass__)
    
    @staticmethod
    def query_by_name(name):
        print(f"Querying IndexTable for name: {name}")
        result = db.session.query(IndexTable).filter_by(name=name).first()
        if result:
            result_data = {column: getattr(result, column) for column in result.__table__.columns.keys()}
            return result_data
        return None


# NGCtable: Define columns dynamically using reflection
class NGCtable(BaseTable):
    __tablename__ = 'NGCtable'

    # Reflect and add columns dynamically (called automatically via __init_subclass__)

    @staticmethod
    def query_by_name(name):
        print(f"Querying NGCtable for name: {name}")
        result = db.session.query(NGCtable).filter_by(name=name).first()
        if result:
            result_data = {column: getattr(result, column) for column in result.__table__.columns.keys()}
            return result_data
        return None

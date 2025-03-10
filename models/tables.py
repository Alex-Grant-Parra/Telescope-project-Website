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

    # @classmethod
    # def get_primary_key(cls):
    #     """
    #     Dynamically get the primary key column(s) for the model's table.
    #     """
    #     primary_key_columns = cls.__table__.primary_key
    #     return [column.name for column in primary_key_columns]

    @classmethod
    def reflect_table(cls):
        """
        Reflect the table schema from the database and add it to the class.
        """
        with app.app_context():  # Ensure the app context is available for reflection
            cls.__table__ = Table(cls.__tablename__, db.metadata, autoload_with=db.engine)
            # Reflection handles the columns automatically

    @classmethod
    def __init_subclass__(cls):
        """
        Automatically called when a subclass is defined. This ensures reflection
        happens for each subclass after the app context is initialized.
        """
        super().__init_subclass__()
        cls.reflect_table()


# HDSTARtable: Define columns dynamically using reflection
class HDSTARtable(BaseTable):
    __tablename__ = 'HDSTARTable'  # The actual table name in the database

    # Do NOT manually define 'Name' – reflection will load it.

    @staticmethod
    def query_by_name(name):
        print(f"Querying HDSTARtable for name: {name}")
        # primary_key = HDSTARtable.get_primary_key()
        # print(f"Primary Key: {primary_key}")  # Expecting ['Name']
        result = db.session.query(HDSTARtable).filter_by(Name=name[2:]).first()
        if result:
            if isinstance(result, dict):  # unlikely if reflection returns a model instance
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

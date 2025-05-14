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


# PlanetsTable: Define columns dynamically using reflection
class PlanetsTable(BaseTable):
    __tablename__ = 'PlanetsTable'  # The actual table name in the database

    @staticmethod
    def query_by_name(name):
        print(f"Querying PlanetsTable for name: {name}")
        result = db.session.query(PlanetsTable).filter_by(name=name).first()
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

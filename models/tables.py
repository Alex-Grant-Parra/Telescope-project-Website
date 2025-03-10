# from db import db
# from sqlalchemy import Table, MetaData

# # Base class for reflection to be inherited by all models
# class BaseTable(db.Model):
#     __abstract__ = True  # This class is not directly mapped to a table
    
#     @classmethod
#     def get_all_fields(cls):
#         """
#         Dynamically get all column names and values for the model's table.
#         """
#         return {column.name: getattr(cls, column.name) for column in cls.__table__.columns}

# # Reflect the table schema from the database for each table

# class HDSTARtable(BaseTable):
#     __tablename__ = 'HDSTARtable'
    
#     # Ensure the table is reflected within the app context
#     @classmethod
#     def reflect_table(cls):
#         with db.session.begin():  # Ensure this happens inside the session context
#             # Reflect the table schema from the database
#             cls.__table__ = Table(cls.__tablename__, MetaData(), autoload_with=db.engine)

#     @staticmethod
#     def query_by_name(name):
#         print(f"Querying HDSTARtable for name: {name}")
#         result = db.session.query(HDSTARtable).filter_by(name=name).first()
#         if result:
#             return {column.name: getattr(result, column.name) for column in result.__table__.columns}
#         return None

# class IndexTable(BaseTable):
#     __tablename__ = 'IndexTable'
    
#     @classmethod
#     def reflect_table(cls):
#         with db.session.begin():  # Ensure this happens inside the session context
#             cls.__table__ = Table(cls.__tablename__, MetaData(), autoload_with=db.engine)

#     @staticmethod
#     def query_by_name(name):
#         print(f"Querying IndexTable for name: {name}")
#         result = db.session.query(IndexTable).filter_by(name=name).first()
#         if result:
#             return {column.name: getattr(result, column.name) for column in result.__table__.columns}
#         return None

# class NGCtable(BaseTable):
#     __tablename__ = 'NGCtable'
    
#     @classmethod
#     def reflect_table(cls):
#         with db.session.begin():  # Ensure this happens inside the session context
#             cls.__table__ = Table(cls.__tablename__, MetaData(), autoload_with=db.engine)

#     @staticmethod
#     def query_by_name(name):
#         print(f"Querying NGCtable for name: {name}")
#         result = db.session.query(NGCtable).filter_by(name=name).first()
#         if result:
#             return {column.name: getattr(result, column.name) for column in result.__table__.columns}
#         return None

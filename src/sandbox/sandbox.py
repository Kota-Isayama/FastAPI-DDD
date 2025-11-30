from sqlalchemy import create_engine

from infrastructure.indication.sqlalchemy.db_base import Base

if __name__ == "__main__":
    engine = create_engine("postgresql://user:postgres@localhost:5432/indication")
    Base.metadata.create_all(engine)
    
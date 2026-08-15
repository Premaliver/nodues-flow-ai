"""
Advanced Automated Database Manager for SQLAlchemy with PostgreSQL & SQLite.
Handles automatic schema creation, self-healing table columns, PostgreSQL extensions, and connection pooling.
"""

import logging
from sqlalchemy import text, inspect
from flask_migrate import Migrate
from models import db

logger = logging.getLogger(__name__)
migrate = Migrate()


def init_db_manager(app):
    """Initialize Flask-Migrate and execute self-building database schema logic."""
    migrate.init_app(app, db)
    
    with app.app_context():
        try:
            auto_build_schema(app)
        except Exception as e:
            logger.error(f"Error during automated database schema build: {e}")


def auto_build_schema(app):
    """
    Self-building and self-healing database schema routine.
    - Creates native PostgreSQL extensions (uuid-ossp, pg_trgm) when connected to Postgres.
    - Creates all missing ORM tables via db.create_all().
    - Automatically inspects models vs active DB tables and executes ALTER TABLE for missing columns.
    """
    engine = db.engine
    dialect_name = engine.dialect.name
    logger.info(f"⚡ Initializing self-building database architecture on dialect: {dialect_name}")

    # 1. PostgreSQL specific extension setup
    if dialect_name == "postgresql":
        try:
            with engine.connect() as conn:
                conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
                conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pg_trgm";'))
                conn.commit()
            logger.info("✓ PostgreSQL extensions (uuid-ossp, pg_trgm) ready.")
        except Exception as e:
            logger.warning(f"Could not enable PostgreSQL extensions (may require superuser privileges): {e}")

    # 2. Build missing tables using SQLAlchemy Metadata
    db.create_all()
    logger.info("✓ SQLAlchemy db.create_all() executed — all model tables created.")

    # 3. Self-healing column check for model-database synchronization
    try:
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()

        for model_class in db.Model.__subclasses__():
            if not hasattr(model_class, "__tablename__"):
                continue
            
            table_name = model_class.__tablename__
            if table_name not in existing_tables:
                continue

            existing_columns = {col["name"] for col in inspector.get_columns(table_name)}
            
            for column in model_class.__table__.columns:
                col_name = column.name
                if col_name not in existing_columns:
                    logger.info(f"Self-healing schema: Adding missing column '{col_name}' to table '{table_name}'...")
                    col_type_str = str(column.type.compile(engine.dialect))
                    nullable_str = "NULL" if column.nullable else ""
                    
                    alter_sql = f'ALTER TABLE "{table_name}" ADD COLUMN "{col_name}" {col_type_str} {nullable_str};'
                    try:
                        with engine.connect() as conn:
                            conn.execute(text(alter_sql))
                            conn.commit()
                        logger.info(f"✓ Column '{col_name}' added to '{table_name}'.")
                    except Exception as err:
                        logger.warning(f"Failed to alter table '{table_name}' for column '{col_name}': {err}")

    except Exception as e:
        logger.warning(f"Self-healing schema inspection notice: {e}")


def get_database_health(app):
    """Diagnose database engine status, connection pool info, and table counts."""
    with app.app_context():
        engine = db.engine
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        pool_status = "N/A"
        if hasattr(engine.pool, "size"):
            pool_status = f"Size: {engine.pool.size()}, Checkedout: {engine.pool.checkedout()}, Overflow: {engine.pool.overflow()}"

        return {
            "dialect": engine.dialect.name,
            "database_name": engine.url.database,
            "tables_count": len(tables),
            "tables_list": tables,
            "pool_status": pool_status,
            "is_connected": True,
        }

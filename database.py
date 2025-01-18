from sqlalchemy import URL, create_engine, text
import os


db_username = os.getenv("DB_USERNAME")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")
db_name = os.getenv("DB_NAME")


# Create a URL object for the PostgreSQL connection
url_object = URL.create(
    "postgresql+psycopg2",
    username=db_username,
    password=db_password,  # Replace with your actual password
    host=db_host,
    database=db_name,
)

# Create an engine
engine = create_engine(url_object)

def insert_into_request_table(data):
    """
    Inserts data into the 'request' table.
    
    Args:
        data (dict): A dictionary containing the values for the columns:
                     query, model, user_id, response, and date_time.
    """
    try:
        with engine.connect() as connection:
            print("Successfully connected to the database.")
            
            # Define the insert query
            insert_query = text("""
                INSERT INTO request (query, model, user_id, response, date_time) 
                VALUES (:query, :model, :user_id, :response, :date_time)
            """)

            # Execute the query with the provided data
            connection.execute(insert_query, parameters=data)

            # Commit the transaction
            connection.commit()
            print("Row successfully inserted into the 'request' table.")
    except Exception as e:
        print("Error while inserting into the database:", e)

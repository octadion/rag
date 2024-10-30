import os
from server.utils.chroma import load_documents, split_documents, add_to_chroma, load_documents_webbase
from server.database.db import get_db_connection

def run_update_database(file_name, file_id, file_location, vector_db_id, vector_db_location):
    try:
        folder = os.path.dirname(file_location)
        documents = load_documents(folder)
        chunks = split_documents(documents)
        add_to_chroma(chunks, vector_db_location)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO files (id, file_name, file_location, vector_db_id, vector_db_location) VALUES (%s, %s, %s, %s, %s)",
            (file_id, file_name, file_location, vector_db_id, vector_db_location)
        )

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error updating database: {e}")

def run_update_database_multi(file_locations, assistant_id, vector_db_location):
    try:
        all_documents = []
        for file_location in file_locations:
            folder = os.path.dirname(file_location)
            documents = load_documents(folder)
            all_documents.extend(documents)

        chunks = split_documents(all_documents)
        add_to_chroma(chunks, vector_db_location)
    except Exception as e:
        print(f"Error updating database: {e}")

def run_update_database_webbase(url, assistant_id, vector_db_location):
    try:
        
        # folder = os.path.dirname(url)
        documents = load_documents_webbase(url)

        chunks = split_documents(documents)
        add_to_chroma(chunks, vector_db_location)
    except Exception as e:
        print(f"Error updating database: {e}")
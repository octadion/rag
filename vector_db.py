import argparse
import os
import shutil
from langchain.document_loaders.pdf import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.schema.document import Document
from embedding import get_embedding_function
from langchain.vectorstores.chroma import Chroma
from fastapi import HTTPException
from typing import List
import psycopg2
def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("POSTGRES_DBNAME"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT")
    )
CHROMA_PATH = "chroma"
DATA_PATH = "data"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Reset the database.")
    args = parser.parse_args()
    if args.reset:
        print("✨ Clearing Database")
        clear_database()

    documents = load_documents()
    chunks = split_documents(documents)
    add_to_chroma(chunks)


def load_documents(file_location: str):
    document_loader = PyPDFDirectoryLoader(file_location)
    return document_loader.load()


def split_documents(documents: List[Document]):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=80,
        length_function=len,
        is_separator_regex=False,
    )
    return text_splitter.split_documents(documents)

def calculate_chunk_ids(chunks):

    last_page_id = None
    current_chunk_index = 0

    for chunk in chunks:
        source = chunk.metadata.get("source")
        page = chunk.metadata.get("page")
        current_page_id = f"{source}:{page}"
        if current_page_id == last_page_id:
            current_chunk_index += 1
        else:
            current_chunk_index = 0

        chunk_id = f"{current_page_id}:{current_chunk_index}"
        last_page_id = current_page_id

        chunk.metadata["id"] = chunk_id

    return chunks

def add_to_chroma(chunks: List[Document], vector_db_location: str):
    try:
        db = Chroma(
            persist_directory=vector_db_location, embedding_function=get_embedding_function()
        )
        print(vector_db_location)
        chunks_with_ids = calculate_chunk_ids(chunks)

        existing_items = db.get(include=[])
        existing_ids = set(existing_items["ids"])
        print(f"Number of existing documents in DB: {len(existing_ids)}")

        new_chunks = []
        for chunk in chunks_with_ids:
            chunk_id = chunk.metadata.get("id")
            if chunk_id not in existing_ids:
                new_chunks.append(chunk)
            else:
                print(f"Chunk with ID {chunk_id} already exists in the database.")

        if new_chunks:
            print(f"👉 Adding new documents: {len(new_chunks)}")
            new_chunk_ids = [chunk.metadata["id"] for chunk in new_chunks]
            try:
                db.add_documents(new_chunks, ids=new_chunk_ids)
            except Exception as e:
                print(f"Warning: Error while adding documents: {e}")
            db.persist()
            print("✅ New documents added and database persisted.")
        else:
            print("✅ No new documents to add")

    except Exception as e:
        print(f"Error in add_to_chroma: {e}")
        
def clear_database(vector_db_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT vector_db_location FROM files WHERE vector_db_id = %s", (vector_db_id,))
    result = cursor.fetchone()

    if result is None:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Vector DB location not found")

    vector_db_location = result[0]
    folder_path = os.path.dirname(vector_db_location)

    if os.path.isdir(folder_path):
        shutil.rmtree(folder_path)
    else:
        os.remove(folder_path)

    cursor.execute("DELETE FROM files WHERE vector_db_id = %s", (vector_db_id,))
    conn.commit()

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
import logging
import os
from datetime import datetime, timedelta

from azure.functions import HttpRequest, HttpResponse
from azure.storage.queue import QueueClient
from azure.data.tables import TableClient

from mysql.connector.cursor import MySQLCursor
import mysql.connector

# from dotenv import load_dotenv

# load_dotenv()

def connect_to_server():
    username=os.environ['db_username']
    password=os.environ['db_password']
    host=os.environ['db_host']
    database=os.environ['db_name']

    cnx = mysql.connector.connect(user=username, password=password,
                                host=host, database=database)
    return cnx

def connect_to_queue():
    queue_name = os.environ['queue_name']
    connection_string=os.environ['connection_string']
    queue = QueueClient.from_connection_string(conn_str=connection_string, queue_name=queue_name)
    return queue
    
def connect_to_table():
    table_name=os.environ['table_name']
    connection_string=os.environ['connection_string']
    table = TableClient.from_connection_string(conn_str=connection_string, table_name=table_name)
    return table

def log_request(table_client: TableClient, req: HttpRequest, status: str):
    request_log_entity = {
        "PartitionKey": "HttpRequestLog",
        "RowKey": datetime.utcnow().isoformat(),
        "RequestMethod": req.method,
        "RequestURL": req.url,
        "RequestBody": req.get_body().decode('utf-8') if req.get_body() else None,
        "Status": status,
        "Timestamp": datetime.utcnow().isoformat()
    }
    
    # Insert the new entity into the Azure Table
    table_client.create_entity(entity=request_log_entity)

def log_dead_letter(queue_client: QueueClient, req: HttpRequest , status: str):

    request_log_entity = {
        "PartitionKey": "HttpRequestLog",
        "RowKey": datetime.utcnow().isoformat(),
        "RequestMethod": req.method,
        "RequestURL": req.url,
        "RequestBody": req.get_body().decode('utf-8') if req.get_body() else None,
        "Status": status,
        "Timestamp": datetime.utcnow().isoformat()
    }
    
    # Insert the new entity into the Azure Table
    queue_client.send_message(request_log_entity)


def log_attendance(cursor: MySQLCursor, student_id, session_id, is_present):
    query = "INSERT INTO attendance (student_id, session_id, is_present) VALUES (%s, %s, %s)"
    cursor.execute(query, (student_id, session_id, is_present))

def is_code_valid(current_time, server_time, max_time_difference_seconds=10):
    # Check if the server timestamp is later than the current time but not later by more than 'max_time_difference_seconds'
    time_difference = current_time - server_time
    return timedelta(seconds=0) <= time_difference <= timedelta(seconds=max_time_difference_seconds)

 
def insert_presence(cursor: MySQLCursor, student_id, session_id, present: bool, date):
    # Insert data into 'attendance_log' table
    query = "INSERT INTO attendance (student_id, session_id, is_present) VALUES (%s, %s, %s)"
    cursor.execute(query, (student_id, session_id, present))

def log_client_info(cursor: MySQLCursor, azure_timestamp, session_id, student_id, random_code):
    logging.info(f"Logging client info: {azure_timestamp}, {session_id}, {student_id}, {random_code}")
    # Assuming client_infoid is auto_increment, so it's not included in the columns list
    query = ("INSERT INTO client_info (azure_timestamp, session_id, student_id, random_code) "
             "VALUES (%s, %s, %s, %s)")
    cursor.execute(query, (azure_timestamp, session_id, student_id, random_code))


def get_session_details(cursor: MySQLCursor, session_id, random_code) -> dict:
    query = ("SELECT qr_code.session_id, qr_code.server_timestamp, session.session_date "
             "FROM qr_code "
             "JOIN session ON qr_code.session_id = session.session_id "
             "WHERE qr_code.random_code = %s AND qr_code.session_id = %s")
    cursor.execute(query, (random_code, session_id))
    result = cursor.fetchone()
    return {'session_id': result[0], 'server_timestamp': result[1], 'session_date': result[2]} if result else None


def main(req: HttpRequest) -> HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    cnx = connect_to_server()
    cursor = cnx.cursor()
    queue = connect_to_queue()
    table = connect_to_table()
    log_request(table, req, "Received")

    # table.create_entity(req)

    session_id= req.params.get('session_id')
    student_id = req.params.get('student_id')
    random_code = req.params.get("random_code")
    
    current_timestamp = datetime.utcnow()
    

    if not session_id or not student_id or not random_code:
        logging.info('Didn\'t find all required parameters in the query string, trying the request body')
        try:
            req_body = req.get_json()
        except ValueError:
            log_dead_letter(queue, req, "Invalid request body")
            logging.info('Invalid request body')
            return HttpResponse("Invalid request body", status_code=400)
        else:

            session_id = req_body.get('session_id')
            student_id = req_body.get('student_id')
            random_code = req_body.get("random_code")
            logging.info(f"Session ID: {session_id}, Student ID: {student_id}, Random Code: {random_code}")


    # Fetch session details associated with the random code and course
    session_details = get_session_details(cursor, session_id, random_code)
    logging.info(f"Session details: {session_details}")
    
    if session_details and is_code_valid(current_timestamp, session_details['server_timestamp']):
        logging.info("Code is valid")
        log_client_info(cursor, current_timestamp, session_details['session_id'] if session_details else None, student_id, random_code)
        cnx.commit()
        # The code is valid, mark the attendance
        log_attendance(cursor, student_id, session_id, True)
        cnx.commit()
        message = f"Student {student_id} marked present for session {session_details['session_id']}."
        status_code = 200
    else:
        logging.info("Code is invalid")
        # The code is invalid or not yet valid
        log_attendance(cursor, student_id, session_id, False)
        log_dead_letter(queue, req, "Invalid or not yet valid attendance code")
        message = "Invalid or not yet valid attendance code."
        status_code = 400


    return HttpResponse(message, status_code=status_code)

# For reference later

# print("=== Testing connection to the Database")
# sql_str='SELECT now();'
# print(sql_str)
# rs=cursor.execute(sql_str)
# rs=cursor.fetchall()
# print(rs)


# print(f"=== Showing the Databases you have access to. This should include {database}")
# sql_str='show databases;'
# print(sql_str)
# rs=cursor.execute(sql_str)
# rs=cursor.fetchall()
# print(rs)


# print("=== Create a sample table: event")
# sql_str='''CREATE TABLE IF NOT EXISTS event (
#     id INT  NOT NULL AUTO_INCREMENT, 
#     name VARCHAR(20) , 
#     state VARCHAR(20),
#     datetime DATETIME NOT NULL,
#     PRIMARY KEY(id)
# );'''
# print(sql_str)

# cursor.execute(sql_str)

# sql_str='show tables;'
# print(sql_str)
# rs=cursor.execute(sql_str)
# rs=cursor.fetchall()
# print(rs)

# print("=== Inserting a record into event")
# sql_str=f"INSERT INTO event(name, state, datetime) VALUES ('test','live',NOW())"
# print(sql_str)
# cursor.execute(sql_str)
# cnx.commit() # commit is required when you run INSERT statement, to persist new data to tables

# sql_str='SELECT * FROM event;'
# print(sql_str)
# rs=cursor.execute(sql_str)
# rs=cursor.fetchall()
# print(rs)

# print("=== Dropping table event to leave a clean schema")
# sql_str='DROP TABLE event;'
# print(sql_str)
# rs=cursor.execute(sql_str)

# sql_str='show tables;'
# rs=cursor.execute(sql_str)
# rs=cursor.fetchall()
# print(rs)


# cursor.close() # Always close a cursor when no longer required
# cnx.close() # always close your database connections before the program exits

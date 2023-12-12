import logging

from azure.functions import HttpRequest, HttpResponse
from azure.storage.queue import QueueClient
import os

def main(req: HttpRequest) -> HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    message = req.params.get('message')
    if not message:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            message = req_body.get('message')

    queue_name=os.environ['queue_name']
    connection_string=os.environ['connection_string']
    if message:
        queue = QueueClient.from_connection_string(conn_str=connection_string, queue_name=queue_name)
        queue.send_message(message)
        return HttpResponse(f"This HTTP triggered function executed successfully.")
    else:
        return HttpResponse(
            "This HTTP triggered did not receive a message.",
            status_code=400
        )

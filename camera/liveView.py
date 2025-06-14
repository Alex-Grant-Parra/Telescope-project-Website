import threading
import time
from subprocess import Popen, PIPE, DEVNULL
from flask import Blueprint, Response, stream_with_context, request, jsonify


live_view_clients = set()
live_view_clients_lock = threading.Lock()
live_view_process = None
live_view_thread = None
live_view_data_lock = threading.Lock()
live_view_frame = None
stop_stream_event = threading.Event()


def start_live_view_process():
    global live_view_process, live_view_thread, stop_stream_event

    if live_view_process is not None:
        return  # Already running

    stop_stream_event.clear()

    def stream_reader():
        global live_view_frame

        cmd = ['gphoto2', '--capture-movie', '--stdout']

        live_view_process = Popen(cmd, stdout=PIPE, stderr=DEVNULL, bufsize=4096)
        data = b''

        try:
            while not stop_stream_event.is_set():
                chunk = live_view_process.stdout.read(4096)
                if not chunk:
                    break
                data += chunk

                while True:
                    start = data.find(b'\xff\xd8')
                    end = data.find(b'\xff\xd9')
                    if start != -1 and end != -1 and end > start:
                        jpg = data[start:end+2]
                        data = data[end+2:]

                        with live_view_data_lock:
                            live_view_frame = jpg
                    else:
                        break
        finally:
            if live_view_process.poll() is None:
                live_view_process.terminate()
                live_view_process.wait(timeout=3)

    live_view_thread = threading.Thread(target=stream_reader, daemon=True)
    live_view_thread.start()


def stop_live_view_process():
    global stop_stream_event, live_view_thread

    stop_stream_event.set()
    if live_view_thread is not None:
        live_view_thread.join(timeout=5)
    live_view_thread = None


@interface_bp.route('/live_view_stream')
def live_view_stream():
    client_id = request.remote_addr + ':' + str(request.environ.get('REMOTE_PORT'))

    with live_view_clients_lock:
        live_view_clients.add(client_id)

    start_live_view_process()

    def generate():
        try:
            while True:
                with live_view_data_lock:
                    frame = live_view_frame

                if frame:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                else:
                    time.sleep(0.05)
        except GeneratorExit:
            # Client disconnected
            with live_view_clients_lock:
                live_view_clients.discard(client_id)

                if len(live_view_clients) == 0:
                    stop_live_view_process()

    return Response(stream_with_context(generate()), mimetype='multipart/x-mixed-replace; boundary=frame')


@interface_bp.route('/stop_live_view', methods=['POST'])
def stop_live_view():
    client_id = request.remote_addr + ':' + str(request.environ.get('REMOTE_PORT'))

    with live_view_clients_lock:
        live_view_clients.discard(client_id)

        if len(live_view_clients) == 0:
            stop_live_view_process()
            return jsonify({"status": "success", "message": "Live view stopped (no users left)."})
        else:
            return jsonify({"status": "success", "message": f"Disconnected client {client_id}, live view continues."})

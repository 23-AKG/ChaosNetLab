import socket
import json
import click

@click.command()
@click.option('--target', required=True, help='Mininet host (e.g., h1)')
@click.option('--type', 'fault_type', required=True, type=click.Choice(['loss', 'delay', 'down'], case_sensitive=False))
@click.option('--value', required=False, help='e.g., 30% for loss, 100ms for delay')
def inject_fault(target, fault_type, value):
    data = {
        "target": target,
        "type": fault_type,
        "value": value
    }

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('127.0.0.1', 9999))
        sock.send(json.dumps(data).encode())
        response = sock.recv(1024).decode()
        print(response)
        sock.close()
    except Exception as e:
        print(f"❌ Could not connect to Mininet controller: {e}")

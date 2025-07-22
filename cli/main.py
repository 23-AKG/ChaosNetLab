import click
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import subprocess
from injector.injector import inject_fault

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOPOLOGY_DIR = os.path.join(PROJECT_ROOT, "topology")
TESTBED_SCRIPT = os.path.join(PROJECT_ROOT, "testbed", "mininet_launcher.py")

@click.group()
def cli():
    """Network Fault Injection Framework CLI"""
    pass

@cli.command()
@click.option('--topo', required=True, help='Path to topology YAML file')
def launch(topo):
    """Launch the virtual SDN testbed"""
    topo_path = os.path.join(TOPOLOGY_DIR, topo)
    if not os.path.exists(topo_path):
        click.echo(f"❌ Topology file not found: {topo_path}")
        sys.exit(1)

    click.echo(f"🚀 Launching network with {topo}")
    subprocess.run(["sudo", "python3", TESTBED_SCRIPT, topo_path])


@cli.command()
@click.option('--target', required=True, help='Target host or interface (e.g., h1-eth0)')
@click.option('--type', 'fault_type', required=True, type=click.Choice(['loss', 'delay', 'down', 'reset', 'linkdown', 'linkup'], case_sensitive=False))
@click.option('--value', required=False, help='Value (e.g., 30% or 100ms)')
def inject(target, fault_type, value):
    """Inject a fault into a target interface"""
    from injector.injector import inject_fault
    ctx = click.get_current_context()
    ctx.invoke(inject_fault, target=target, fault_type=fault_type, value=value)

@cli.command()
def log():
    """Collect logs/metrics (coming soon)"""
    click.echo("📈 Logging module coming soon...")

if __name__ == '__main__':
    cli()